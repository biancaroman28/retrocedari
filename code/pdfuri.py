import pandas as pd
import os
import re

# 1. Citește CSV-ul
df = pd.read_csv("dosare_geocode_grupate_regex.csv")

# 2. Funcție pentru extragerea numărului de dosar din "Dosar PMB"
def extract_dosar_id(x):
    try:
        return str(x).split("/")[0].strip()
    except:
        return None

# 3. Funcție pentru extragerea tuturor perechilor (DPG, Dată)
def extract_dpg_date_pairs(text):
    if pd.isna(text):
        return []
    pattern = r"DPG[: ]+(\d+)[, ]+Dat[ăa][: ]+(\d{4}-\d{2}-\d{2})"
    return re.findall(pattern, text)

# 4. Creăm temporar câmpurile necesare pentru potrivire
df["_Dosar_ID"] = df["Dosar PMB"].apply(extract_dosar_id)
df["_DPG_pairs"] = df.apply(
    lambda row: extract_dpg_date_pairs(str(row["Soluție"])) +
                extract_dpg_date_pairs(str(row["Istorie acte"])),
    axis=1
)

# 5. Inițializăm coloana finală cu PDF-uri
df["Pdf_nume"] = ""

# 6. Parcurgem PDF-urile și facem potrivirea
pdf_folder = "pdfs"

for fname in os.listdir(pdf_folder):
    if not fname.endswith(".pdf"):
        continue

    try:
        dosar, dpg, data_ext = fname.split("_")
        data_pdf = data_ext.replace(".pdf", "")
    except:
        continue

    # Găsim liniile corespunzătoare aceluiași dosar
    subset = df[df["_Dosar_ID"] == dosar]

    for idx, row in subset.iterrows():
        if (dpg, data_pdf) in row["_DPG_pairs"]:
            if df.at[idx, "Pdf_nume"] == "":
                df.at[idx, "Pdf_nume"] = fname
            else:
                df.at[idx, "Pdf_nume"] += ";" + fname

# 🟢 7. Adăugăm coloana Pdf_valid după regula corectă:
#    - dacă Pdf_nume e gol → False
#    - altfel, dacă există cel puțin un pdf al cărui număr de dosar (primul număr din numele fișierului) <= 17033 → True
#    - altfel → False

CUTOFF_DOSAR = 17033

def check_valid(pdf_cell):
    if not isinstance(pdf_cell, str) or pdf_cell.strip() == "":
        return False
    for pdf_name in pdf_cell.split(";"):
        pdf_name = pdf_name.strip()
        # extrage primul număr (dosarul) înainte de primul underscore
        try:
            dosar_nr = int(pdf_name.split("_", 1)[0])
        except ValueError:
            continue
        if dosar_nr <= CUTOFF_DOSAR:
            return True
    return False

df["Pdf_valid"] = df["Pdf_nume"].apply(check_valid)


# 8. Ștergem coloanele temporare
df = df.drop(columns=["_Dosar_ID", "_DPG_pairs"])

# 9. Salvăm CSV-ul final
df.to_csv("dosare_geocode_cu_pdfuri.csv", index=False)

print("Gata!")
