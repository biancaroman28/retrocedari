import os
import re
import pandas as pd
from bs4 import BeautifulSoup

# === CONFIG ===
INPUT_FOLDER = "responses"   # folderul unde ai fișierele HTML
OUTPUT_FILE = "dosare.csv"
MAX_FILES = 43287
PROGRESS_STEP = 2000

def clean_text(text):
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else "NONE"

def parse_dosar(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    # --- verifică dacă dosar anulat ---
    if "Dosar anulat" in html_content:
        return []

    rows = []

    # --- pentru fiecare bloc "Dosar PMB" ---
    for dosar_card in soup.find_all("h5", class_="card-title"):
        if "Dosar PMB" not in dosar_card.get_text():
            continue

        dosar_block = dosar_card.find_parent("div", class_="card-body")

        nr_dosar, data_dosar, solicitanti, notificare, adrese, solutie, istorie_acte = \
            "NONE", "NONE", [], "NONE", [], "NONE", "NONE"

        # === Număr + Data dosar ===
        spans = dosar_block.find_all("span", class_="btn")
        for span in spans:
            txt = span.get_text(strip=True)
            if txt.startswith("Număr:"):
                nr_dosar = txt.replace("Număr:", "").strip() or "NONE"
            elif txt.startswith("Data:"):
                data_dosar = txt.replace("Data:", "").strip() or "NONE"

        dosar_id = f"{nr_dosar} / {data_dosar}".strip(" /") or "NONE"

        # === Notificare PMB ===
        col_div = dosar_block.find_parent("div", class_="col-sm-6")
        notif_col = None
        if col_div:
            row_div = col_div.find_parent("div", class_="row")
            if row_div:
                siblings = row_div.find_all("div", class_="col-sm-6")
                for sib in siblings:
                    if sib is not col_div and "Notificare" in sib.get_text():
                        notif_col = sib
                        break

        if notif_col:
            spans = notif_col.find_all("span", class_="btn")
            notif_nr, notif_date = "NONE", "NONE"
            for span in spans:
                txt = span.get_text(strip=True)
                if txt.startswith("Număr:"):
                    notif_nr = txt.replace("Număr:", "").strip() or "NONE"
                elif txt.startswith("Data:"):
                    notif_date = txt.replace("Data:", "").strip() or "NONE"
            notificare = f"{notif_nr} / {notif_date}".strip(" /") or "NONE"

        # === Solicitanti ===
        sol_block = dosar_block.find_next("h5", string=lambda t: t and "Solicitan" in t)
        if sol_block:
            ol = sol_block.find_next("ol")
            if ol:
                solicitanti = [clean_text(li.get_text()) for li in ol.find_all("li")]
        if not solicitanti:
            solicitanti = ["NONE"]

        # === Adrese ===
        adr_block = dosar_block.find_next("h5", string=lambda t: t and "Adrese" in t)
        if adr_block:
            ol = adr_block.find_next("ol")
            if ol:
                for li in ol.find_all("li"):
                    adresa_raw = clean_text(li.get_text())

                    adresa_contemp, adresa_istoric, tip_proprietate = adresa_raw, "NONE", "NONE"

                    if "(Istoric:" in adresa_raw:
                        before, rest = adresa_raw.split("(Istoric:", 1)
                        if ")" in rest:
                            istorica, after = rest.split(")", 1)
                            adresa_contemp = clean_text(before + after)
                            adresa_istoric = clean_text(istorica)

                    tip_match = re.search(r"\(([^)]+)\)\s*$", adresa_contemp)
                    if tip_match:
                        tip_proprietate = tip_match.group(1)
                        adresa_contemp = re.sub(r"\(\s*" + re.escape(tip_proprietate) + r"\s*\)\s*$", "", adresa_contemp).strip()

                    adrese.append((adresa_contemp or "NONE", adresa_istoric, tip_proprietate))

        if not adrese:
            adrese = [("NONE", "NONE", "NONE")]

        # === Soluția ===
        sol_block = dosar_block.find_next("h5", string=lambda t: t and "Soluția la dosar" in t)
        if sol_block:
            parent = sol_block.find_parent("div", class_="card-body")
            spans = parent.find_all("span", class_="btn")
            solutie_parts = [clean_text(sp.get_text()) for sp in spans if clean_text(sp.get_text()) != ""]
            if solutie_parts:
                solutie = ", ".join(solutie_parts)

            # === Istorie acte ===
            istorie_ul = parent.find("ul", role="list")
            if istorie_ul:
                acte = [clean_text(li.get_text()) for li in istorie_ul.find_all("li")]
                if acte:
                    istorie_acte = "; ".join(acte)

        # === Compunem rânduri (una per adresă) ===
        for adresa_contemp, adresa_istoric, tip_proprietate in adrese:
            rows.append({
                "Dosar PMB": dosar_id,
                "Solicitant": "; ".join(solicitanti),
                "Notificare PMB": notificare,
                "Adresa contemporană": adresa_contemp,
                "Adresa istorică": adresa_istoric,
                "Tip proprietate": tip_proprietate,
                "Soluție": solutie,
                "Istorie acte": istorie_acte,
                "Mai multe adrese": "DA" if len(adrese) > 1 else "NU"
            })

    return rows


# === Procesare fișiere ===
all_rows = []
for i in range(1, MAX_FILES + 1):
    file_path = os.path.join(INPUT_FOLDER, f"{i}.html")
    if not os.path.exists(file_path):
        continue

    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    rows = parse_dosar(html)
    all_rows.extend(rows)

    if i % PROGRESS_STEP == 0:
        print(f"✅ Procesate {i} fișiere...")

# === Export CSV ===
df = pd.DataFrame(all_rows)
df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"✅ Exportat {len(df)} rânduri în {OUTPUT_FILE}")
