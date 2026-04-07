#!/usr/bin/env python3
"""Generate Outlook-compatible ICS calendars for Sakky restaurants."""

from __future__ import annotations

import datetime as dt
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import requests

LOCAL_TZ = "Europe/Helsinki"
DEFAULT_TITLE = "Lounas – Ravintola"

RESTAURANT_SOURCES = [
    {
        "id": "parvi",
        "display_name": "Ravintola Parvi",
        "pdf_url": "https://sakky.fi/ravintola/parvi?action=generate_pdf__{week:02d}",
    },
    {
        "id": "loisto",
        "display_name": "Ravintola Loisto",
        "pdf_url": "https://sakky.fi/ravintola/loisto?action=generate_pdf__{week:02d}",
    },
    {
        "id": "silmu",
        "display_name": "Ravintola Silmu",
        "pdf_url": "https://sakky.fi/ravintola/ravintola-silmu?action=generate_pdf__{week:02d}",
    },
    {
        "id": "helmi",
        "display_name": "Ravintola Helmi",
        "pdf_url": "https://sakky.fi/ravintola/ravintola-helmi?action=generate_pdf__{week:02d}",
    },
    {
        "id": "helmi-henkilokunta",
        "display_name": "Ravintola Helmi (Henkilökunta ja vieraat)",
        "pdf_url": "https://sakky.fi/ravintola/ravintola-helmi-henkilokunta-ja-vieraat?action=generate_pdf__{week:02d}",
    },
]

WEEKDAY_HEADER = re.compile(
    r"(?i)(Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai)\s+(\d{1,2})\.(\d{1,2})\."
)

VTIMEZONE_HELSINKI = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Helsinki",
    "X-LIC-LOCATION:Europe/Helsinki",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0300",
    "TZNAME:EEST",
    "DTSTART:19700329T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0300",
    "TZOFFSETTO:+0200",
    "TZNAME:EET",
    "DTSTART:19701025T040000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


@dataclass
class LunchEvent:
    date: dt.date
    title: str
    details: str



def download_week_pdf(url_template: str, week: int) -> bytes | None:
    try:
        resp = requests.get(
            url_template.format(week=week),
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (parvi-calendar)"},
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    if len(resp.content) < 500:
        return None

    ctype = resp.headers.get("Content-Type", "")
    if "pdf" not in ctype.lower() and not resp.content.startswith(b"%PDF"):
        return None

    return resp.content



def extract_pdf_text(pdf_bytes: bytes) -> str:
    chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                chunks.append(page_text)
    return "\n".join(chunks)



def resolve_year(day: int, month: int, today: dt.date) -> int:
    year = today.year
    if month < today.month - 6:
        year += 1
    elif month > today.month + 6:
        year -= 1
    dt.date(year, month, day)
    return year



def clean_multiline_text(raw: str) -> str:
    return "\n".join(line.strip() for line in raw.splitlines() if line.strip())



def build_event_title(details: str) -> str:
    deny = [
        "lounashinta",
        "vierailijat",
        "korttimaksut",
        "powered by tcpdf",
        "www.tcpdf.org",
    ]

    keep: list[str] = []
    for line in details.splitlines():
        line = line.strip()
        if not line:
            continue

        low = line.lower()
        if any(token in low for token in deny):
            continue
        if "€" in line or "/hlö" in low:
            continue

        keep.append(line)

    if not keep:
        return DEFAULT_TITLE

    title = " | ".join(keep)
    if len(title) > 180:
        return f"{title[:177]}…"
    return title



def parse_events_from_text(text: str, today: dt.date) -> list[LunchEvent]:
    matches = list(WEEKDAY_HEADER.finditer(text))
    if not matches:
        return []

    result: list[LunchEvent] = []
    for idx, match in enumerate(matches):
        day = int(match.group(2))
        month = int(match.group(3))

        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        details = clean_multiline_text(text[start:end])

        year = resolve_year(day, month, today)
        event_date = dt.date(year, month, day)

        result.append(LunchEvent(date=event_date, title=build_event_title(details), details=details))

    return result



def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )



def render_ics(events: list[LunchEvent], restaurant_id: str, restaurant_name: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//parvi-calendar//MVP//FI",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{restaurant_name}",
        "X-WR-TIMEZONE:Europe/Helsinki",
    ]
    lines.extend(VTIMEZONE_HELSINKI)

    for event in sorted(events, key=lambda x: x.date):
        ds = event.date.strftime("%Y%m%d")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{restaurant_id}-{ds}",
                f"DTSTAMP:{stamp}",
                f"DTSTART;TZID={LOCAL_TZ}:{ds}T120000",
                f"DTEND;TZID={LOCAL_TZ}:{ds}T130000",
                f"SUMMARY:{ics_escape(event.title)}",
                f"DESCRIPTION:{ics_escape(event.details)}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"



def build_all_calendars() -> None:
    today = dt.date.today()

    for source in RESTAURANT_SOURCES:
        events_by_date: dict[dt.date, LunchEvent] = {}

        for week in range(1, 53):
            pdf = download_week_pdf(source["pdf_url"], week)
            if not pdf:
                continue

            try:
                text = extract_pdf_text(pdf)
            except Exception:
                continue

            events = parse_events_from_text(text, today)
            for event in events:
                events_by_date[event.date] = event

        payload = render_ics(
            list(events_by_date.values()),
            restaurant_id=source["id"],
            restaurant_name=source["display_name"],
        )
        out = Path(f"{source['id']}.ics")
        out.write_text(payload, encoding="utf-8", newline="")
        print(f"Wrote {out} ({len(payload)} chars)")


if __name__ == "__main__":
    build_all_calendars()
