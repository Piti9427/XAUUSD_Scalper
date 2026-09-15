"""Notifier-only TradingView relay. This module has no broker execution dependency."""

from datetime import datetime, timezone
import asyncio
import hmac
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, field_validator, model_validator


class AlertV2(BaseModel):
    schema_version: Literal["2"]
    secret: str
    event_id: str
    setup_id: str
    event: Literal["SIMULATED_SETUP", "SIMULATED_ENTRY", "SIMULATED_TP1", "SIMULATED_TP2", "SIMULATED_STOP", "SIMULATED_CANCEL"]
    simulation: bool
    symbol: Literal["XAUUSD"]
    timeframe: Literal["M15"]
    engine: Literal["SMC", "TSS", "GSS", "CONFLUENCE"]
    contributors: list[Literal["SMC", "TSS", "GSS"]]
    direction: Literal["long", "short"]
    event_time_utc: datetime
    message: str

    @field_validator("event_time_utc")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event_time_utc must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def simulated_only(self):
        if not self.simulation:
            raise ValueError("notifier relay accepts simulation events only")
        return self


def create_alert_relay(auth_token: str, notifier: Any) -> FastAPI:
    app = FastAPI(title="Pine Master Pro Notifier Relay", version="2")
    seen: set[str] = set()
    in_flight: set[str] = set()
    dedupe_lock = asyncio.Lock()

    @app.post("/api/v2/alerts", status_code=status.HTTP_202_ACCEPTED)
    async def alerts(alert: AlertV2):
        if not hmac.compare_digest(alert.secret, auth_token):
            raise HTTPException(status_code=401, detail="invalid secret")
        async with dedupe_lock:
            if alert.event_id in seen or alert.event_id in in_flight:
                return {"status": "duplicate", "event_id": alert.event_id}
            in_flight.add(alert.event_id)
        try:
            await notifier.send_message(alert.message)
        except Exception:
            async with dedupe_lock:
                in_flight.discard(alert.event_id)
            raise
        async with dedupe_lock:
            in_flight.discard(alert.event_id)
            seen.add(alert.event_id)
        return {"status": "accepted", "event_id": alert.event_id}

    return app
