# parvi-calendar

Tämä repo on toteutettu kokonaan tekoälyllä yhdellä promptilla. Toteutus hakee Sakky-ravintoloiden viikkokohtaiset PDF-ruokalistat, purkaa niistä arkipäivien lounassisällöt ja julkaisee Outlookiin (ja muihin kalenteriohjelmiin) tilattavat `.ics`-kalenterit.

## Miten tämä toimii

1. Skripti `scripts/build_calendar.py` käy jokaisen ravintolan viikot `01..52` läpi ravintolakohtaisista URL-osoitteista.
2. Jokainen PDF puretaan tekstiksi `pdfplumber`-kirjastolla.
3. Päiväotsikot tunnistetaan regexillä:
   - `Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai + dd.mm.`
4. Päiväotsikon jälkeinen teksti kerätään seuraavaan päiväotsikkoon asti ja tallennetaan tapahtuman `DESCRIPTION`-kenttään.
5. Jokaiselle löydetylle päivälle luodaan tapahtuma klo 12:00–13:00 aikavyöhykkeellä `Europe/Helsinki`.
6. Tapahtuman `UID` on muotoa `<restaurant-id>-YYYYMMDD`.
7. Jos sama päivämäärä löytyy useammin kuin kerran, pidetään vain yksi tapahtuma (duplikaatteja ei tule).
8. Vuodenvaihde käsitellään sääntöpohjaisesti kuukauden perusteella.
9. Event title contains the day's menu items (joined with |). Full menu in description.

## Available calendars

- `https://<username>.github.io/<repo>/parvi.ics`
- `https://<username>.github.io/<repo>/loisto.ics`
- `https://<username>.github.io/<repo>/silmu.ics`
- `https://<username>.github.io/<repo>/helmi.ics`
- `https://<username>.github.io/<repo>/helmi-henkilokunta.ics`

Outlook → Add calendar → Subscribe from web → paste chosen URL.

## Ajastus GitHub Actionsilla

Workflow löytyy tiedostosta `.github/workflows/build.yml` ja se ajetaan:
- joka maanantai klo **05:00 UTC**
- manuaalisesti `workflow_dispatch`-triggerillä

Workflow:
- asentaa riippuvuudet `requests` ja `pdfplumber`
- ajaa skriptin `python scripts/build_calendar.py`
- committaa ja pushaa kaikki `*.ics`-tiedostot vain jos sisältö muuttui

## Ota GitHub Pages käyttöön

1. Avaa reposi **Settings → Pages**.
2. Valitse **Source: Deploy from branch**.
3. Valitse branchiksi **main** ja kansioksi **/(root)**.
4. Tallenna.

Koska kalenterit kirjoitetaan repo-rootiin (`parvi.ics`, `loisto.ics`, `silmu.ics`, `helmi.ics`, `helmi-henkilokunta.ics`), GitHub Pages voi palvella ne suoraan.

> Huomio: Outlook ei välttämättä päivitä web-kalentereita heti. Päivityksissä voi olla viivettä.
