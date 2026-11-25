"""Review actual official HTML captures; never attest account entitlements.

This pure module receives retrieval bytes/metadata from an external reader. It
does not fetch pages or approve execution. Missing JS-rendered terms, conflicting
claims and unsupported source layouts defer rather than become zero-cost proof.
"""

from datetime import datetime, timedelta
import hashlib
from html.parser import HTMLParser
import json
import re

from scripts.c22_selected.trial_costs import build_trial_policy

OFFICIAL_URLS = {
    "tariff": "https://www.exness.com/standard-accounts/",
    "swap": "https://get.exness.help/hc/en-us/articles/360014709151-About-swap",
    "calendar": "https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours",
}
_CLAIMS = {
    "commission_per_lot": 0.0, "commission_unit": "USD_per_lot_round_trip",
    "mt5_swap_unit": "POINTS", "triple_weekday_mt5": 3, "weekend_regular_factor": 0,
    "summer_rollover_utc_hour": 21, "winter_rollover_utc_hour": 22,
    "calendar_formula": "REGULAR_POINTS_NY17_WED3_WEEKEND0_V1",
}


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("source_aware_utc_required")
    return stamp


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _text(value):
    return " ".join(value.replace("\u2013", "-").replace("\u2014", "-").split())


class _Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.rows = []
        self.stack = []
        self.headings = []
        self.heading = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        hidden = tag in {"script", "style", "noscript", "template"} or any(
            key == "hidden" or (key == "aria-hidden" and value == "true")
            or (key == "style" and re.search(
                r"display\s*:\s*none|visibility\s*:\s*(hidden|collapse)|opacity\s*:\s*0(?:\s|;|$)", value or "", re.I))
            for key, value in attrs)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}:
            self.stack.append((tag, hidden))
        if any(flag for _, flag in self.stack):
            return
        if re.fullmatch("h[1-6]", tag):
            self.heading = (int(tag[1]), len(self.parts))
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            self.cell = []

    def handle_endtag(self, tag):
        hidden = any(flag for _, flag in self.stack)
        if not hidden:
            if re.fullmatch("h[1-6]", tag) and self.heading is not None:
                level, start = self.heading
                self.headings.append((level, start, len(self.parts), " ".join(self.parts[start:])))
                self.heading = None
            if tag in {"td", "th"} and self.row is not None and self.cell is not None:
                self.row.append(_text(" ".join(self.cell)))
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.rows.append(self.row)
                self.row = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        if any(flag for _, flag in self.stack):
            return
        value = _text(data)
        if value:
            self.parts.append(value)
            if self.cell is not None:
                self.cell.append(value)


def _claims_match(role, body):
    doc = _Document()
    doc.feed(body.decode("utf-8", errors="strict"))
    flat = " ".join(doc.parts)
    if role == "tariff":
        starts = [heading for heading in doc.headings if heading[3] == "Trading accounts: Standard"]
        if len(starts) != 1:
            raise ValueError("source_claims_missing")
        _, _, start, _ = starts[0]
        end = min((position for _, position, _, title in doc.headings
                   if position >= start and title != "Standard"),
                  default=len(doc.parts))
        section = doc.parts[start:end]
        values = {section[i + 1] for i, item in enumerate(section[:-1]) if item == "Commission"}
        values.update(match.group(1) for item in section
                      if (match := re.fullmatch(r"Commission\s*:\s*(.+)", item)))
        if not values:
            raise ValueError("source_claims_missing")
        if values != {"No commission"}:
            raise ValueError("source_claims_changed_or_ambiguous")
    elif role == "swap":
        rows = [row for row in doc.rows if row and row[0].lower() == "metals (commodities)"]
        expected = ["Metals (commodities)", "21:00 GMT+0 (summer) / 22:00 GMT+0 (winter), Mon-Fri",
                    "Wednesday", "None weekdays; not applied Sat-Sun"]
        if not rows or "MetaTrader platforms calculate them in points" not in flat:
            raise ValueError("source_claims_missing")
        if any([row[0].lower(), *row[1:]] != [expected[0].lower(), *expected[1:]] for row in rows):
            raise ValueError("source_claims_changed_or_ambiguous")
        if "changes in the swap schedule due to public/bank holidays" not in flat:
            raise ValueError("source_holiday_limitation_missing")
    else:
        expected = {
            "Summer": ["Summer", "Second Sunday in March", "First Sunday in November"],
            "Winter": ["Winter", "First Sunday in November", "Second Sunday in March"],
        }
        rows = [row for row in doc.rows if row and row[0] in expected]
        if ("Instrument trading hours" not in flat or "Most instruments follow US DST" not in flat
                or not all(any(row == value for row in rows) for value in expected.values())):
            raise ValueError("source_claims_missing")
        if any(row != expected[row[0]] for row in rows):
            raise ValueError("source_claims_changed_or_ambiguous")


def review_source_captures(captures, *, now):
    """Return validated published assumptions or finite, role-specific blockers.

    Captures require original actual request/retrieval dates, exact approved URL,
    HTTP200 HTML and matching bytes/hash. A clean hash alone never proves terms.
    No raw upstream error or untrusted URL appears in the returned diagnostics.
    """
    now = _utc(now)
    records, blockers = {}, {}
    captures = captures if isinstance(captures, dict) else {}
    for role, source in OFFICIAL_URLS.items():
        code = "source_capture_missing_or_malformed"
        try:
            item = captures[role]
            started, received = _utc(item["requested_utc"]), _utc(item["retrieved_utc"])
            code = "source_capture_invalid_or_stale"
            if not (started <= received <= now and now - received <= timedelta(hours=24)
                    and received - started <= timedelta(minutes=5)
                    and item["source"] == item["final_url"] == source
                    and type(item["http_status"]) is int and item["http_status"] == 200
                    and item["content_type"].lower().split(";")[0].strip() == "text/html"):
                raise ValueError(code)
            body = item["body"]
            if not isinstance(body, bytes) or not 0 < len(body) <= 4 * 1024 * 1024:
                raise ValueError("source_capture_body_invalid")
            digest = hashlib.sha256(body).hexdigest()
            if digest != item["content_sha256"]:
                raise ValueError("source_capture_hash_mismatch")
            records[role] = dict(source=source, requested_utc=started.isoformat(),
                checked_utc=received.isoformat(), content_sha256=digest, bytes=len(body), http_status=200)
            code = "source_claims_missing"
            _claims_match(role, body)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as error:
            allowed = {"source_capture_invalid_or_stale", "source_capture_body_invalid",
                "source_capture_hash_mismatch", "source_claims_missing",
                "source_claims_changed_or_ambiguous", "source_holiday_limitation_missing",
                "source_aware_utc_required"}
            blockers[role] = str(error) if type(error) is ValueError and str(error) in allowed else code
    packet = dict(version=1, reviewed_utc=now.isoformat(), sources=records, blockers=blockers,
        status="DEFERRED" if blockers else "VALIDATED_PUBLISHED_ASSUMPTIONS",
        claims=dict(_CLAIMS) if not blockers else {}, execution_authorized=False,
        swap_entitlement="UNKNOWN", economic_qualification="COST_INCONCLUSIVE",
        broker_holiday_exceptions_verified=False, account_tariff_entitlement="NOT_ATTESTED")
    packet["packet_sha256"] = _hash(packet)
    return packet


def sources_for_policy(packet, captures, *, now):
    """Consume exactly reviewed bytes; never replace checked time with now."""
    try:
        now = _utc(now)
        reviewed = _utc(packet["reviewed_utc"])
        valid = review_source_captures(captures, now=now)
        if not (reviewed <= now and now - reviewed <= timedelta(hours=24)
                and packet["status"] == valid["status"] == "VALIDATED_PUBLISHED_ASSUMPTIONS"):
            raise ValueError("source_packet_invalid_or_stale")
        original = review_source_captures(captures, now=reviewed)
        if original != packet:
            raise ValueError("source_packet_binding_changed")
        return {role: dict(source=item["source"], checked_utc=item["checked_utc"],
                           content_sha256=item["content_sha256"], packet_sha256=packet["packet_sha256"])
                for role, item in packet["sources"].items()}
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError("source_packet_invalid_or_stale") from error


def build_source_bound_policy(broker_bytes, packet, captures, *, now):
    """Reuse the native builder/calendar; output remains non-authorizing."""
    return build_trial_policy(broker_bytes, now=now,
                              sources=sources_for_policy(packet, captures, now=now))
