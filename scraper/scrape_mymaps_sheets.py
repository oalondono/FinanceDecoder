#!/usr/bin/env python3
"""
scrape_mymaps_sheets.py
-----------------------
Download every Google Sheets workbook referenced in a **Google My Maps** KML
file and save it as  <STATE>_<City_With_Underscores>.xlsx

Usage examples
  python scrape_mymaps_sheets.py 1AbCdEfGhIJkLmNoP
  python scrape_mymaps_sheets.py "https://www.google.com/maps/d/viewer?mid=1AbCdEfGhIJkLmNoP"
"""

import html
import re
import string
import sys
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

# ───────────────────────── configuration ──────────────────────────
TIMEOUT = 30                               # seconds for HTTP requests
OUT_DIR = Path("downloaded_xls")           # output folder
OUT_DIR.mkdir(exist_ok=True, parents=True)

# 50-state lookup (keys are lower-cased state names)
STATE_ABBR = {
    'alabama':'AL','alaska':'AK','arizona':'AZ','arkansas':'AR','california':'CA',
    'colorado':'CO','connecticut':'CT','delaware':'DE','florida':'FL','georgia':'GA',
    'hawaii':'HI','idaho':'ID','illinois':'IL','indiana':'IN','iowa':'IA','kansas':'KS',
    'kentucky':'KY','louisiana':'LA','maine':'ME','maryland':'MD','massachusetts':'MA',
    'michigan':'MI','minnesota':'MN','mississippi':'MS','missouri':'MO','montana':'MT',
    'nebraska':'NE','nevada':'NV','new hampshire':'NH','new jersey':'NJ',
    'new mexico':'NM','new york':'NY','north carolina':'NC','north dakota':'ND',
    'ohio':'OH','oklahoma':'OK','oregon':'OR','pennsylvania':'PA','rhode island':'RI',
    'south carolina':'SC','south dakota':'SD','tennessee':'TN','texas':'TX','utah':'UT',
    'vermont':'VT','virginia':'VA','washington':'WA','west virginia':'WV',
    'wisconsin':'WI','wyoming':'WY',
}

# ───────────────────────── helpers ─────────────────────────────────
def map_id_from_arg(arg: str) -> str:
    """Return raw map-ID whether the user passed it plain or inside a URL."""
    if arg.startswith("http"):
        qs = parse_qs(urlparse(arg).query)
        mid = qs.get("mid", [None])[0] or qs.get("mid%3D", [None])[0]
        if not mid:
            sys.exit("Could not find a ‘mid=…’ parameter in the URL you supplied.")
        return mid
    return arg

def fetch_kml(map_id: str) -> str:
    url = f"https://www.google.com/maps/d/kml?forcekml=1&mid={map_id}"
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text

# regex for any docs.google.com URL (greedy up to first delim)
DOCS_RX = re.compile(r"https?://docs\.google\.com/[^\s\"'<>]+", re.I)

def extract_sheets_and_names(kml_text: str):
    """
    Return a list of (sheet_url, placemark_name) tuples.
    placemark_name is the <name> tag text, e.g. 'Bullhead City, Arizona'.
    """
    root = ET.fromstring(kml_text)
    hits = []

    for pm in root.findall('.//{*}Placemark'):
        name_el = pm.find('{*}name')
        place_name = name_el.text.strip() if name_el is not None else "Unknown"

        # Description may live in <description> or ExtendedData->Data->value.
        blob = ""
        desc_el = pm.find('.//{*}description')
        if desc_el is not None and desc_el.text:
            blob = desc_el.text
        else:
            val_el = pm.find('.//{*}ExtendedData/{*}Data/{*}value')
            blob = val_el.text if val_el is not None else ""

        if not blob:
            continue

        for raw in DOCS_RX.findall(blob):
            url = urllib.parse.unquote(html.unescape(raw))
            if "spreadsheets" in url:
                hits.append((url, place_name))
                break          # assume max one sheet per placemark

    return hits

def to_excel_url(sheet_url: str) -> str:
    """
    Convert any public Google Sheets URL to an .xlsx export link.
    """
    m = re.search(r"/d/([A-Za-z0-9_-]+)", sheet_url)
    if not m:
        raise ValueError(f"Un-recognised Sheets URL: {sheet_url}")
    file_id = m.group(1)
    return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"

# translations for city slug
PUNCT_TBL = str.maketrans('', '', string.punctuation)

def safe_filename(placemark_name: str) -> str:
    """
    'Bullhead City, Arizona' → 'AZ_Bullhead_City.xlsx'
    Falls back to 'XX_City' if state not in dict.
    """
    city_part, _, state_part = placemark_name.partition(',')
    city = city_part.strip()
    state = state_part.strip().lower()

    abbrev = STATE_ABBR.get(state, (state[:2] or "XX").upper())

    # remove accents, punctuation; spaces → _
    city_ascii = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode()
    city_clean = city_ascii.translate(PUNCT_TBL).replace(' ', '_') or "UnknownCity"

    return f"{abbrev}_{city_clean}.xlsx"

# ───────────────────────── main routine ────────────────────────────
def main(arg: str):
    mid = map_id_from_arg(arg)
    print("Fetching KML for map-ID:", mid)
    kml = fetch_kml(mid)
    print("KML size:", len(kml), "bytes")

    sheet_items = extract_sheets_and_names(kml)
    print("Sheets found:", len(sheet_items))
    if not sheet_items:
        print("No Google Sheets links found; exiting.")
        return

    for sheet_url, placename in sheet_items:
        try:
            xlsx_url = to_excel_url(sheet_url)
            resp = requests.get(xlsx_url, timeout=TIMEOUT)
            resp.raise_for_status()

            fname = OUT_DIR / safe_filename(placename)
            fname.write_bytes(resp.content)
            print(f" ✔ {fname.name:35} {len(resp.content):,} bytes")
        except Exception as exc:
            print(f" ✖ {placename} ({sheet_url}): {exc}")

# ───────────────────────── CLI entry-point ─────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scrape_mymaps_sheets.py <MAP_ID or My-Maps URL>")
    main(sys.argv[1])
