import pandas as pd
import time
import re
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import os
import sys

# ---------------- CONFIG ----------------
CSV_PATH = "dosare_geocode_cu_pdfuri.csv"
TXT_INPUT = "negasite_clean.txt"
TXT_FAILED = "negasite2.txt"
USER_AGENT = "geo_updater_pmb/1.0"
# ----------------------------------------

# Încarcă CSV-ul complet
df = pd.read_csv(CSV_PATH)

# Încarcă progresul din negasite2.txt (dacă există)
processed_lines = set()
if os.path.exists(TXT_FAILED):
    with open(TXT_FAILED, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith(("DONE:", "FAIL:", "ERROR:")):
                num = re.findall(r"\d+", line)
                if num:
                    processed_lines.add(int(num[0]))

# Inițializează geolocatorul
geolocator = Nominatim(user_agent=USER_AGENT)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# Citește toate liniile din fișierul negasite_clean.txt
with open(TXT_INPUT, "r", encoding="utf-8") as f:
    lines = f.readlines()

total = len(lines)
out = open(TXT_FAILED, "a", encoding="utf-8")

print(f"🚀 Începem procesarea ({total} adrese totale)...\n")

# Parcurgem toate adresele
for idx, line in enumerate(lines, start=1):
    # Extrage linia și adresa
    match = re.match(r"Linia\s+(\d+):\s*(.*)", line.strip(), flags=re.IGNORECASE)
    if not match:
        continue

    linie_idx = int(match.group(1))
    adresa = match.group(2).strip()

    # Sărim dacă a fost deja procesată
    if linie_idx in processed_lines:
        continue

    # Afișare progres în terminal
    progress = idx / total * 100
    sys.stdout.write(f"\r⏳ {idx}/{total} ({progress:.1f}%) — Linia {linie_idx}: {adresa[:60]}...")
    sys.stdout.flush()

    try:
        location = geocode(f"{adresa}, București, România")
        if location:
            lat, lon = location.latitude, location.longitude
            print(f"\n✅ Găsit: {adresa} -> ({lat:.6f}, {lon:.6f})")

            # Actualizează CSV-ul (scădem 1 pentru a compensa headerul)
            row_idx = linie_idx - 1
            if 0 <= row_idx < len(df):
                df.at[row_idx, "latitude"] = lat
                df.at[row_idx, "longitude"] = lon
                df.to_csv(CSV_PATH, index=False)  # salvăm imediat
                out.write(f"DONE: Linia {linie_idx}: {adresa} -> ({lat:.6f}, {lon:.6f})\n")
            else:
                print(f"⚠️  Linia {linie_idx} e în afara limitelor CSV-ului.")
                out.write(f"ERROR: Linia {linie_idx}: {adresa} — index invalid\n")

        else:
            print(f"\n❌ Nu s-au găsit coordonate pentru: {adresa}")
            out.write(f"FAIL: Linia {linie_idx}: {adresa}\n")

    except Exception as e:
        print(f"\n⚠️  Eroare la linia {linie_idx}: {e}")
        out.write(f"ERROR: Linia {linie_idx}: {adresa} — {e}\n")

    out.flush()
    processed_lines.add(linie_idx)
    time.sleep(1)  # pauză pentru a respecta limita Nominatim

# Salvare finală
df.to_csv(CSV_PATH, index=False)
out.close()
print("\n🏁 Proces complet! CSV actualizat și 'negasite2.txt' generat.")
