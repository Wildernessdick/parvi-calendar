#!/usr/bin/env python3
"""
Rakenna Ravintola Parvin viikkopdf:istä Outlookiin tilattava iCalendar-tiedosto.
"""

from __future__ import annotations

import datetime as dt
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import requests

BASE_URL = "https://sakky.fi/ravintola/parvi?action=generate_pdf__{week:02d}"
OUTPUT_FILE = Path("parvi.ics")
TIMEZONE = "Europe/Helsinki"
SUMMARY = "Lounas – Ravintola Parvi"

# Päiväotsikot PDF:ssä:
# "Maanantai 23.2." jne.
DAY_HEADER_RE = re.compile(
    r"(?im)^\s*(Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai)\s+(\d{1,2})\.(\d{1,2})\.\s*$"
)


@dataclass(frozen=True)
class CalendarEvent:
    date: dt.date
    summary: str
    description: str


def fetch_pdf(week: int) -> bytes | None:
    """Lataa yksittäisen viikon PDF:n."""
    url = BASE_URL.format(week=week)
    try:
        response = requests.get(
            url,
            timeout=25,
            headers={"User-Agent": "Mozilla/5.0 (parvi-calendar)"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    content_type = response.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
        return None

    # Joissain tilanteissa serveri voi palauttaa tyhjän/turhan pienen PDF:n
    if len(response.content) < 1500:
        return None

    return response.content


def extract_text(pdf_bytes: bytes) -> str:
    """Pura PDF:n koko tekstisisältö yhteen merkkijonoon."""
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(page_text)
    return "\n".join(parts)


def infer_year(day: int, month: int, today: dt.date) -> int:
    """
    Päättele vuosi vuodenvaihteen yli.

    Sääntö:
    - jos parsed_month < current_month - 6 -> year + 1
    - jos parsed_month > current_month + 6 -> year - 1
    """
    year = today.year
    current_month = today.month

    if month < current_month - 6:
        year += 1
    elif month > current_month + 6:
        year -= 1

    # Validointi (karkausvuodet ym.)
    dt.date(year, month, day)
    return year


def normalize_text(text: str) -> str:
    """Siivoa kuvaus luettavaan muotoon."""
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = [ln for ln in lines if ln]
    return "\n".join(cleaned)


def parse_events(text: str, today: dt.date) -> list[CalendarEvent]:
    """Löydä päivän otsikot ja niiden ruokalistat."""
    matches = list(DAY_HEADER_RE.finditer(text))

    # Tyhjän/epävalidin PDF:n tunnistus
    if not matches:
        return []

    events: list[CalendarEvent] = []
    for idx, m in enumerate(matches):
        day = int(m.group(2))
        month = int(m.group(3))

        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        description = normalize_text(text[start:end])

        year = infer_year(day=day, month=month, today=today)
        event_date = dt.date(year, month, day)

        events.append(
            CalendarEvent(
                date=event_date,
                summary=SUMMARY,
                description=description,
            )
        )

    return events


def escape_ics(value: str) -> str:
    """Pakollinen iCalendar-escape tekstikentille."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def build_ics(events: list[CalendarEvent]) -> str:
    """Rakenna iCalendar-sisältö CRLF-riveillä."""
    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//parvi-calendar//MVP//FI",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Ravintola Parvi Lounas",
        "X-WR-TIMEZONE:Europe/Helsinki",
    ]

    for ev in sorted(events, key=lambda e: e.date):
        day_str = ev.date.strftime("%Y%m%d")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:parvi-{day_str}",
                f"DTSTAMP:{now_utc}",
                f"DTSTART;TZID={TIMEZONE}:{day_str}T120000",
                f"DTEND;TZID={TIMEZONE}:{day_str}T130000",
                f"SUMMARY:{escape_ics(ev.summary)}",
                f"DESCRIPTION:{escape_ics(ev.description)}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_calendar() -> str:
    """Lataa viikot 1..52, parsii tapahtumat ja palauttaa ICS."""
    today = dt.date.today()

    # Dedup: yksi tapahtuma per päivämäärä (myöhemmin löytyvä voittaa).
    events_by_date: dict[dt.date, CalendarEvent] = {}

    for week in range(1, 53):
        pdf_bytes = fetch_pdf(week)
        if not pdf_bytes:
            continue

        try:
            text = extract_text(pdf_bytes)
        except Exception:
            continue

        week_events = parse_events(text=text, today=today)
        if not week_events:
            continue

        for ev in week_events:
            events_by_date[ev.date] = ev

    return build_ics(list(events_by_date.values()))


def main() -> None:
    ics_content = build_calendar()
    OUTPUT_FILE.write_text(ics_content, encoding="utf-8", newline="")
    print(f"Kirjoitettu {OUTPUT_FILE} ({len(ics_content)} merkkiä)")


if __name__ == "__main__":
    main()
