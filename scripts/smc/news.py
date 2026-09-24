from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from scripts.smc.types import Position, OrderIntentType


@dataclass(frozen=True)
class NewsEvent:
    time: datetime
    currency: str
    impact: str
    name: str


class NewsManager:
    """
    Manages economic news events and foundation BaselinePlay news gates:
    blackout blocks new/pending risk; open positions keep SL/TP (no pre-news BE/exit).
    """

    def is_in_blackout(
        self,
        current_time: datetime,
        events: List[NewsEvent],
        window_mins: int = 30,
        filter_currency: str = "USD",
        filter_impact: str = "HIGH",
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if current_time falls within window_mins before or after
        any high-impact USD economic news event.
        """
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time = current_time.astimezone(timezone.utc)

        for event in events:
            if event.currency == filter_currency and event.impact == filter_impact:
                ev_time = event.time
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=timezone.utc)
                else:
                    ev_time = ev_time.astimezone(timezone.utc)

                diff_seconds = (current_time - ev_time).total_seconds()
                diff_minutes = abs(diff_seconds) / 60.0

                if diff_minutes <= window_mins:
                    return True, event.name

        return False, None

    def new_risk_allowed(
        self,
        current_time: datetime,
        events: Optional[List[NewsEvent]],
        *,
        schedule_known: bool,
        window_mins: int = 30,
        filter_currency: str = "USD",
        filter_impact: str = "HIGH",
    ) -> Tuple[bool, str]:
        """
        Foundation BaselinePlay admission gate for new/pending exposure.

        Unknown or stale news schedules block new risk. Existing positions are
        not force-closed or moved to BE by this method (unlike Legacy ADR-010).
        """
        if not schedule_known or events is None:
            return False, "unknown_or_stale_news_schedule"
        in_blackout, name = self.is_in_blackout(
            current_time,
            events,
            window_mins=window_mins,
            filter_currency=filter_currency,
            filter_impact=filter_impact,
        )
        if in_blackout:
            return False, f"news_blackout:{name}"
        return True, "ok"

    def should_cancel_pending(
        self,
        current_time: datetime,
        events: Optional[List[NewsEvent]],
        *,
        schedule_known: bool,
        window_mins: int = 30,
        filter_currency: str = "USD",
        filter_impact: str = "HIGH",
    ) -> Tuple[bool, str]:
        """
        Pending cancellation shares the new-risk news gate (scenario 18).

        Does not force-close open positions — BaselinePlay holds through news
        without pre-news BE/exit unless a separate Legacy path is enabled.
        """
        allowed, reason = self.new_risk_allowed(
            current_time,
            events,
            schedule_known=schedule_known,
            window_mins=window_mins,
            filter_currency=filter_currency,
            filter_impact=filter_impact,
        )
        if allowed:
            return False, "ok"
        return True, reason

    def evaluate_pre_news_position(
        self,
        current_time: datetime,
        events: List[NewsEvent],
        position: Position,
        current_price: float,
        pre_window_mins: int = 15,
        filter_currency: str = "USD",
        filter_impact: str = "HIGH",
    ) -> Optional[OrderIntentType]:
        """
        Foundation BaselinePlay (Issue #1 scenario 18): hold existing positions
        through news with their original SL/TP.

        Returns None always — no pre-news BE and no forced exit. ADR-010 legacy
        MOVE_SL_TO_BE / CLOSE_MARKET behavior is intentionally not applied here.
        Risk halt and TIME_EXIT remain separate policies.
        """
        _ = (
            current_time,
            events,
            position,
            current_price,
            pre_window_mins,
            filter_currency,
            filter_impact,
        )
        return None

    def parse_calendar_items(
        self, raw_items: List[dict], target_country: str = "USD", target_impact: str = "HIGH"
    ) -> List[NewsEvent]:
        """
        Parses raw calendar JSON items into NewsEvent dataclasses,
        normalizing all timezone offsets to UTC.
        """
        events: List[NewsEvent] = []
        for item in raw_items:
            country = str(item.get("country", "")).upper()
            impact = str(item.get("impact", "")).upper()
            date_str = item.get("date")

            if country == target_country and impact == target_impact and date_str:
                try:
                    dt = datetime.fromisoformat(date_str)
                    # Convert to UTC
                    if dt.tzinfo is None:
                        utc_dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        utc_dt = dt.astimezone(timezone.utc)

                    events.append(
                        NewsEvent(
                            time=utc_dt,
                            currency=country,
                            impact=impact,
                            name=str(item.get("title", "Economic Event")),
                        )
                    )
                except (ValueError, TypeError):
                    continue

        return events

    def fetch_forexfactory_calendar(
        self,
        cache_path: str = "data/news_cache.json",
        cache_ttl_hours: int = 24,
        timeout_seconds: int = 10,
    ) -> List[NewsEvent]:
        """
        Downloads the weekly economic calendar feed from ForexFactory
        with automatic disk caching and fallback.
        """
        import os
        import json

        # Check local cache first
        if os.path.exists(cache_path):
            try:
                mtime = os.path.getmtime(cache_path)
                age_hours = (datetime.now().timestamp() - mtime) / 3600.0
                if age_hours < cache_ttl_hours:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    return self.parse_calendar_items(cached_data)
            except Exception:
                pass

        # Fetch fresh data from ForexFactory
        try:
            import requests

            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            resp = requests.get(url, timeout=timeout_seconds)
            if resp.status_code == 200:
                raw_data = resp.json()
                # Save cache
                try:
                    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(raw_data, f)
                except Exception:
                    pass
                return self.parse_calendar_items(raw_data)
        except Exception:
            pass

        # Fallback to existing cache if fresh fetch failed
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return self.parse_calendar_items(json.load(f))
            except Exception:
                pass

        return []
