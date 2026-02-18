#!/usr/bin/env python3
"""Rakenna Ravintola Parvin viikkopdf:istä Outlookiin tilattava iCalendar-tiedosto."""

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

# Etsitään päiväotsikot muodossa "Maanantai 23.2." jne.
DAY_HEADER_RE = re.compile(
    r"(?i)(Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai)\s+(\d{1,2})\.(\d{1,2})\."
)


@dataclass
class CalendarEvent:
    """Yksi lounastapahtuma kalenterissa."""

    date: dt.date
    summary: str
    description: str



def fetch_pdf(week: int) -> bytes | None:
    """Lataa yksittäisen viikon PDF:n sisällön tavuina."""
    url = BASE_URL.format(week=week)
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (parvi-calendar)"},
        )
        response.raise_for_status()
        if len(response.content) < 500:
            return None
    except requests.RequestException:
        return None

    content_type = response.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
        return None

    return response.content



def extract_text(pdf_bytes: bytes) -> str:
    """Pura PDF:n koko tekstisisältö yhteen merkkijonoon."""
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)
    return "\n".join(text_parts)



def infer_year(day: int, month: int, today: dt.date) -> int:
    """Päättele vuosi vuodenvaihteen yli annettujen sääntöjen mukaan."""
    year = today.year
    current_month = today.month

    if month < current_month - 6:
        year += 1
    elif month > current_month + 6:
        year -= 1

    # Varmistetaan, että päiväys on aidosti validi (esim. karkausvuosi).
    dt.date(year, month, day)
    return year



def normalize_text(text: str) -> str:
    """Siivoa kuvaus yhdenmukaiseen, luettavaan muotoon."""
    lines = [line.strip() for line in text.splitlines()]
    cleaned = [line for line in lines if line]
    return "\n".join(cleaned)



def make_summary_from_description(description: str) -> str:
    """Muodosta tapahtuman otsikko päivän ruokalistariveistä."""
    blocked_terms = [
        "lounashinta",
        "vierailijat",
        "korttimaksut",
        "powered by tcpdf",
        "www.tcpdf.org",
    ]

    filtered_lines: list[str] = []
    for raw_line in description.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.lower()
        if any(term in lowered for term in blocked_terms):
            continue
        if "€" in line or "/hlö" in lowered:
            continue

        filtered_lines.append(line)

    if not filtered_lines:
        return SUMMARY

    summary = " | ".join(filtered_lines)
    if len(summary) > 180:
        return summary[:177] + "…"
    return summary



def parse_events(text: str, today: dt.date) -> list[CalendarEvent]:
    """Löydä viikonpäivät ja niiden ruokalistat tekstistä."""
    print("---- DEBUG TEXT SAMPLE ----")
    print(text[:1000])
    print("---- DEBUG MATCH COUNT ----", len(list(DAY_HEADER_RE.finditer(text))))

    matches = list(DAY_HEADER_RE.finditer(text))

    # Tyhjän/epävalidin PDF:n tunnistus: ei yhtään päivän otsikkoa.
    if not matches:
        return []

    events: list[CalendarEvent] = []

    for idx, match in enumerate(matches):
        day = int(match.group(2))
        month = int(match.group(3))

        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        description = normalize_text(text[start:end])

        # Jos kuvaus puuttuu kokonaan, lisätään silti tapahtuma tyhjällä kuvauksella.
        year = infer_year(day=day, month=month, today=today)
        event_date = dt.date(year, month, day)

        events.append(
            CalendarEvent(
                date=event_date,
                summary=make_summary_from_description(description),
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
    """Rakenna iCalendar-tiedoston sisältö CRLF-rivinvaihdoilla."""
    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//parvi-calendar//MVP//FI",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Ravintola Parvi Lounas",
        "X-WR-TIMEZONE:Europe/Helsinki",
    ]

    for event in sorted(events, key=lambda ev: ev.date):
        day_str = event.date.strftime("%Y%m%d")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:parvi-{day_str}",
                f"DTSTAMP:{now_utc}",
                f"DTSTART;TZID={TIMEZONE}:{day_str}T120000",
                f"DTEND;TZID={TIMEZONE}:{day_str}T130000",
                f"SUMMARY:{escape_ics(event.summary)}",
                f"DESCRIPTION:{escape_ics(event.description)}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"



def build_calendar() -> str:
    """Lataa viikot 1..52, parsii tapahtumat ja palauttaa ICS-sisällön."""
    today = dt.date.today()

    # Dedup: yksi tapahtuma per päivämäärä. Myöhemmin loopissa löytyvä voittaa.
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

        for event in week_events:
            events_by_date[event.date] = event

    return build_ics(list(events_by_date.values()))



def main() -> None:
    ics_content = build_calendar()
    OUTPUT_FILE.write_text(ics_content, encoding="utf-8", newline="")
    print(f"Kirjoitettu {OUTPUT_FILE} ({len(ics_content)} merkkiä)")


if __name__ == "__main__":
    main()
