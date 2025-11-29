# acte_interne_resume.py
import asyncio
import pandas as pd
import os
import re
from datetime import datetime
from urllib.parse import urljoin
from playwright.async_api import async_playwright

CSV_PATH = "dosare.csv"
OUTPUT_DIR = "pdfs"
BASE_URL = "https://acteinterne.pmb.ro/legis"
ERROR_LOG = "erori.txt"
PROCESATE_LOG = "procesate.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === CONFIG pentru reluare ===
START_ROW = 1438 # de unde vrei să începi (index 0-based, deci 96 = linia 97)
# sau poți să pui START_DOSAR = "77" și să folosești extract_dosar_number

# ==== utilitare ====
def sanitize_filename(name: str) -> str:
    name = re.sub(r"[^\w\-.]", "_", name)
    return name[:200]

def parse_year_from_iso(iso_date: str):
    if not iso_date:
        return None
    try:
        return datetime.fromisoformat(iso_date).year
    except Exception:
        return None

def normalize_date(date_str: str):
    if not date_str:
        return None
    s = date_str.strip()
    formats = ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y")
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    m = re.search(r"(\d{2}/\d{2}/\d{4})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
        except Exception:
            pass
    m = re.search(r"(\d{2}-\d{2}-\d{4})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d-%m-%Y").date().isoformat()
        except Exception:
            pass
    return None

def extract_dosar_number(dosar_text: str) -> str:
    if not dosar_text:
        return "DOSAR_UNKNOWN"
    m = re.match(r"^\s*(\d+)", str(dosar_text))
    if m:
        return m.group(1)
    cleaned = re.split(r"[\/\s]", str(dosar_text).strip())[0]
    cleaned = re.sub(r"[^\w\-\.]", "_", cleaned)
    return cleaned or "DOSAR_UNKNOWN"

def extract_all_dpgs(text: str):
    if not text or str(text).strip().upper() == "NONE":
        return []
    text = str(text)
    pattern = re.compile(
        r"DPG[:\s]*([0-9]+)(?:[^;\n\r]*?Dat[ăa][:]?\s*"
        r"([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4}|[0-9]{4}/[0-9]{2}/[0-9]{2}|[0-9]{2}-[0-9]{2}-[0-9]{4}))?",
        flags=re.IGNORECASE,
    )
    results = []
    for m in pattern.finditer(text):
        dpg = m.group(1)
        date_raw = m.group(2) if m.group(2) else None
        date_iso = normalize_date(date_raw) if date_raw else None
        year = parse_year_from_iso(date_iso) if date_iso else None
        results.append({"dpg": dpg, "date_raw": date_raw, "date_iso": date_iso, "year": year})
    return results

async def download_pdf_from_page(new_page, base_url, target_name):
    await new_page.wait_for_load_state("domcontentloaded")
    try:
        await new_page.wait_for_load_state("networkidle", timeout=2000)
    except Exception:
        pass
    current_url = new_page.url
    pdf_url = None
    if current_url.lower().endswith(".pdf"):
        pdf_url = current_url
    else:
        embed = await new_page.query_selector("embed[type='application/pdf'], iframe[src*='.pdf']")
        if embed:
            src = await embed.get_attribute("src")
            if src:
                pdf_url = urljoin(current_url, src)
        if not pdf_url:
            anchors = await new_page.query_selector_all("a")
            for a in anchors:
                href = (await a.get_attribute("href")) or ""
                txt = (await a.inner_text()).strip()
                if ".pdf" in href.lower():
                    pdf_url = urljoin(current_url, href)
                    break
                if "vezi documentul" in txt.lower():
                    try:
                        async with new_page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
                            await a.click()
                    except Exception:
                        pass
                    if new_page.url.lower().endswith(".pdf"):
                        pdf_url = new_page.url
                        break
                    embed2 = await new_page.query_selector("embed[type='application/pdf'], iframe[src*='.pdf']")
                    if embed2:
                        src2 = await embed2.get_attribute("src")
                        if src2:
                            pdf_url = urljoin(new_page.url, src2)
                            break
    if not pdf_url:
        return None
    try:
        resp = await new_page.request.get(pdf_url)
        if resp.ok:
            data = await resp.body()
            filename = sanitize_filename(target_name)
            path = os.path.join(OUTPUT_DIR, filename)
            with open(path, "wb") as f:
                f.write(data)
            return path
    except Exception as e:
        return None
    return None

async def search_and_download_for_dpg(page, context, dpg_nr, date_iso, dosar_num, processed_set, solicitant):
    key = (dpg_nr, date_iso)
    if key in processed_set:
        return
    if not date_iso:
        return
    year = parse_year_from_iso(date_iso)
    if not year:
        return
    processed_set.add(key)
    try:
        await page.goto(BASE_URL)
        await page.fill("input[name='nr']", str(dpg_nr))
        await page.fill("input[name='data_aprob']", str(year))
        await page.click("form[name='cauta'] input[type='submit'], form[name='cauta'] button")
    except Exception as e:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[ERR] Formular {dpg_nr}/{year} Dosar {dosar_num}: {e}\n")
        return
    try:
        await page.wait_for_selector("a", timeout=10000)
    except Exception:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[WARN] Nu au apărut linkuri {dpg_nr}/{year} Dosar {dosar_num}\n")
        return
    anchors = await page.query_selector_all("a")
    found = False
    for a in anchors:
        try:
            text = (await a.inner_text()).strip()
        except Exception:
            text = ""
        tupper = text.upper()
        if tupper.startswith("DISPOZITIE") or tupper.startswith("DL10"):
            found = True
            try:
                async with context.expect_page() as new_page_info:
                    await a.click()
                new_page = await new_page_info.value
                target_name = f"{dosar_num}_{dpg_nr}_{date_iso}.pdf"
                saved = await download_pdf_from_page(new_page, new_page.url, target_name)
                if saved:
                    with open(PROCESATE_LOG, "a", encoding="utf-8") as f:
                        f.write(f"{dosar_num},{dpg_nr},{date_iso},{target_name}\n")
                else:
                    with open(ERROR_LOG, "a", encoding="utf-8") as f:
                        f.write(f"[WARN] Nu am găsit PDF link '{text}' DPG {dpg_nr}/{year} Dosar {dosar_num}\n")
                try:
                    await new_page.close()
                except Exception:
                    pass
            except Exception as e:
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write(f"[ERR] Problema tab link '{text}' DPG {dpg_nr}/{year} Dosar {dosar_num}: {e}\n")
    if not found:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[INFO] Nu s-au găsit DISPOZITIE/DL10 pentru {dpg_nr}/{year} Dosar {dosar_num}\n")

# ==== flux principal ====
async def main():
    df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8").fillna("")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        processed = set()

        for idx, row in df.iterrows():
            if idx < START_ROW:
                continue  # sari peste ce e deja procesat

            dosar_text = row.get("Dosar PMB", "")
            dosar_num = extract_dosar_number(dosar_text)
            solicitant = row.get("Solicitant", "").strip() or "SOLICITANT_UNKNOWN"
            solutie = row.get("Soluție", "")
            istorie = row.get("Istorie acte", "")

            dpgs = []
            dpgs += extract_all_dpgs(solutie)
            dpgs += extract_all_dpgs(istorie)
            if not dpgs:
                continue

            seen_local = set()
            for entry in dpgs:
                dpg_nr = entry["dpg"]
                date_iso = entry["date_iso"]
                if (dpg_nr, date_iso) in seen_local:
                    continue
                seen_local.add((dpg_nr, date_iso))
                await search_and_download_for_dpg(page, context, dpg_nr, date_iso, dosar_num, processed, solicitant)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
