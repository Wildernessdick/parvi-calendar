# parvi-calendar

Tämä repo on toteutettu kokonaan tekoälyllä yhdellä promptilla. Toteutus hakee Ravintola Parvin viikkokohtaiset PDF-ruokalistat, purkaa niistä arkipäivien lounassisällöt ja julkaisee Outlookiin (ja muihin kalenteriohjelmiin) tilattavan `.ics`-kalenterin tiedostona `parvi.ics`.

## Miten tämä toimii

1. Skripti `scripts/build_calendar.py` käy viikot `01..52` läpi URL-osoitteista:
   - `https://sakky.fi/ravintola/parvi?action=generate_pdf__VV`
2. Jokainen PDF puretaan tekstiksi `pdfplumber`-kirjastolla.
3. Päiväotsikot tunnistetaan regexillä:
   - `Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai + dd.mm.`
4. Päiväotsikon jälkeinen teksti kerätään seuraavaan päiväotsikkoon asti ja tallennetaan tapahtuman `DESCRIPTION`-kenttään.
5. Jokaiselle löydetylle päivälle luodaan tapahtuma klo 12:00–13:00 aikavyöhykkeellä `Europe/Helsinki`.
6. Tapahtuman `UID` on muotoa `parvi-YYYYMMDD`.
7. Jos sama päivämäärä löytyy useammin kuin kerran, pidetään vain yksi tapahtuma (duplikaatteja ei tule).
8. Vuodenvaihde käsitellään sääntöpohjaisesti kuukauden perusteella.
9. Event title contains the day's menu items (joined with |). Full menu in description.

## Ajastus GitHub Actionsilla

Workflow löytyy tiedostosta `.github/workflows/build.yml` ja se ajetaan:
- joka maanantai klo **05:00 UTC**
- manuaalisesti `workflow_dispatch`-triggerillä

Workflow:
- asentaa riippuvuudet `requests` ja `pdfplumber`
- ajaa skriptin `python scripts/build_calendar.py`
- committaa ja pushaa `parvi.ics`-tiedoston vain jos sisältö muuttui

## Ota GitHub Pages käyttöön

1. Avaa reposi **Settings → Pages**.
2. Valitse **Source: Deploy from branch**.
3. Valitse branchiksi **main** ja kansioksi **/(root)**.
4. Tallenna.

Koska `parvi.ics` kirjoitetaan repo-rootiin, GitHub Pages voi palvella sen suoraan.

## Kalenterin URL

Korvaa placeholderit omilla arvoillasi:

`https://<kayttajanimi>.github.io/<repo>/parvi.ics`

Esimerkki tämän repon nimellä:

`https://<kayttajanimi>.github.io/parvi-calendar/parvi.ics`

## Outlook-tilaus

Outlookissa:

1. **Add calendar**
2. **Subscribe from web**
3. Liitä `.ics`-URL (esim. GitHub Pages -osoite)
4. Tallenna tilaus

> Huomio: Outlook ei välttämättä päivitä web-kalentereita heti. Päivityksissä voi olla viivettä.
