"""Bounded HTTP delivery. Outbox owns retry; HTTP never submits broker orders."""

import json
import time
from queue import Queue, Empty
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class HttpDelivery:
    def _perform(self, request, outcome):
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read(65537)
                if len(body) > 65536:
                    raise ValueError("delivery_response_too_large")
            outcome.put((body, None, 0))
        except HTTPError as exc:
            try:
                delay = min(300, max(2, float(exc.headers.get("Retry-After", "2"))))
            except (TypeError, ValueError):
                delay = 2
            exc.close()
            outcome.put((None, RuntimeError("delivery_http_error"), delay))
        except Exception:
            outcome.put((None, RuntimeError("delivery_transport_error"), 2))

    def _post(self, request):
        """Bound wall time even during DNS/header/body trickles; one worker maximum.

        Workers perform HTTP only, never SQLite or broker calls. An indefinitely
        stuck transport keeps its outbox pending rather than spawning more threads.
        """
        if time.monotonic() < getattr(self, "retry_at", 0):
            raise RuntimeError("delivery_retry_deferred")
        key = (request.full_url, request.data)
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.is_alive():
            raise RuntimeError("delivery_in_flight")
        if worker is None or self._request_key != key:
            self._request_key = key
            self._outcome = Queue(maxsize=1)
            self._worker = Thread(target=self._perform, args=(request, self._outcome), daemon=True)
            self._worker.start()
        try:
            body, error, delay = self._outcome.get(timeout=self.timeout)
        except Empty:
            self.retry_at = time.monotonic() + 2
            raise RuntimeError("delivery_wall_deadline") from None
        self._worker = None
        if error is not None:
            self.retry_at = time.monotonic() + delay
            raise error
        return body


class TelegramDelivery(HttpDelivery):
    def __init__(self, token, chat_id, *, base_url="https://api.telegram.org", timeout=2):
        self.url = f"{base_url}/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.timeout = timeout

    def __call__(self, event):
        # Include stable ID: Telegram has no idempotency key. Lost acknowledgement
        # can duplicate messages; it cannot cause another financial mutation.
        body = json.dumps(dict(chat_id=self.chat_id, text=json.dumps(event, sort_keys=True)))
        request = Request(
            self.url, data=body.encode(), headers={"Content-Type": "application/json"}
        )
        result = json.loads(self._post(request))
        if result.get("ok") is not True:
            raise ValueError("telegram_acknowledgement_missing")


class HealthDelivery(HttpDelivery):
    def __init__(self, url, *, timeout=2):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def __call__(self, event):
        result = event["result"]
        url = self.url + ("/fail" if result.get("critical") else "")
        # Only operational fields; account credentials never enter ping body.
        body = json.dumps(
            {
                k: result.get(k)
                for k in ("captured_utc", "status", "position_protection", "critical")
            }
        ).encode()
        if self._post(Request(url, data=body)).strip() != b"OK":
            raise ValueError("health_acknowledgement_missing")
