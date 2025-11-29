import csv
import time
import requests
import re

# Funcția ta de normalizare
def normalize_address(address):
    address = re.sub(r'(?i)(?<![A-ZĂÂÎȘȚa-zăâîșț])G-RAL(?![A-ZĂÂÎȘȚa-zăâîșț])', '', address)
    address = re.sub(r'(?i)(?<![A-ZĂÂÎȘȚa-zăâîșț])BIS(?![A-ZĂÂÎȘȚa-zăâîșț])', '', address)
    address = re.sub(r'(?i)(?<![A-ZĂÂÎȘȚa-zăâîșț])SNIC(?![A-ZĂÂÎȘȚa-zăâîșț])', '', address)

    replacements = {
        r'(?i)\bS(TRA?D?A?)?\.?\b': 'Strada',
        r'(?i)\bIN(TR(ARE|\.?)?)?\b|\bIN\b': 'Intrarea',
        r'(?i)\bFUND(ATURA?|AT|A|\.?)\b|\bFUNDA\.?\b': 'Fundatura',
        r'(?i)\bB([- ]?DUL|D|UL|UL\.?|ULUI|DULUI|ULEVARD|ULEVARDUL)?\.?\b': 'Bulevardul',
        r'(?i)\bCAL(EA)?\.?\b|\bCALE\.?\b': 'Calea',
        r'(?i)\bS(OS(EAUA?)?|OSEA)?\.?\b': 'Soseaua',
        r'(?i)\bAL(EE?A?)?\.?\b': 'Aleea',
        r'(?i)\bPREL(UNGIREA?)?\.?\b': 'Prelungirea',
        r'(?i)\bCOM(UNA?|\.?)\b|\bCO\b': 'Comuna',
        r'(?i)\bCART(IER(UL)?|\.?)\b|\bCAR\b': 'Cartierul',
        r'(?i)\bSAT(UL)?\.?\b': 'Satul',
        r'(?i)\bPIA(TA)?\.?\b': 'Piata',
        r'(?i)\bDRUM(UL)?\.?\b|\bDR\b': 'Drumul',
        r'(?i)\bZONA?\.?\b': 'Zona',
        r'(?i)\bMOS(IA)?\.?\b': 'Mosia',
        r'(?i)\bPARC(UL)?\.?\b': 'Parcul',
        r'(?i)\bLOCALIT(ATEA)?\.?\b|\bLOC\b': 'Localitatea'
    }

    normalized = address.strip()
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized)

    normalized = re.sub(r'(?i)(Strada|Bulevardul|Calea|Soseaua|Aleea|Intrarea|Fundatura|Comuna|Cartierul|Satul|Piata|Drumul|Zona|Mosia|Parcul|Prelungirea|Localitatea)\.', r'\1', normalized)
    normalized = re.sub(r'(?i)(Strada|Bulevardul|Calea|Soseaua|Aleea|Intrarea|Fundatura|Comuna|Cartierul|Satul|Piata|Drumul|Zona|Mosia|Parcul|Prelungirea|Localitatea)([A-ZĂÂÎȘȚ])', r'\1 \2', normalized)
    normalized = re.sub(r'\b([A-ZĂÂÎȘȚ])\.\s*', '', normalized)
    normalized = re.sub(r'[,:.]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)

    fn_match = re.search(r'(?i)\bFN\s*\((\d+)\)', normalized)
    if fn_match:
        normalized = re.sub(r'(?i)\bFN\s*\(\d+\)', fn_match.group(1), normalized)
    normalized = re.sub(r'\([^)]*\)', '', normalized)
    normalized = re.sub(r'(?i)\bFN\b', 'FN', normalized)
    normalized = re.sub(r'(?i)\b(nr|numar|nrul|numarul)\b', 'nr', normalized)

    nr_fn = bool(re.search(r'(?i)\bnr\s*[:.]*\s*FN\b', normalized))
    match_nr = re.search(r'(?i)\bnr\s*[:.]*\s*([\d]+)', normalized)
    first_nr = match_nr.group(1) if match_nr else None

    match_parcela = re.search(r'(?i)\bPARCELA\s*([A-Z0-9]+)\b', normalized)
    if match_parcela:
        parcela_raw = match_parcela.group(1)
        parcela_num = re.match(r'\d+', parcela_raw)
        parcela_num = parcela_num.group(0) if parcela_num else None
    else:
        parcela_num = None

    normalized = re.sub(r'(?i)\bnr\s*[:.]*\s*[^,]*', '', normalized)
    normalized = re.sub(r'(?i)\bPARC(ELA)?\s*[A-Z0-9]*', '', normalized)

    if nr_fn and parcela_num:
        add_number = parcela_num
    elif first_nr:
        add_number = first_nr
    else:
        add_number = None

    if add_number:
        normalized = re.sub(r'(?i)(Strada|Bulevardul|Calea|Soseaua|Aleea|Intrarea|Fundatura|Comuna|Cartierul|Satul|Piata|Drumul|Zona|Mosia|Parcul|Prelungirea|Localitatea)([^0-9]*)',
                            r'\1\2 ' + add_number + ' ', normalized, 1)

    sector_match = re.search(r'(?i)\bsector\s*:?\.?\s*(\d+)', address)
    if sector_match:
        sector = sector_match.group(1)
        if sector != '0':
            normalized += f" sector {sector}"

    tokens = normalized.split()
    if tokens:
        prefix = tokens[0]
        filtered_tokens = [prefix]
        for t in tokens[1:]:
            if re.fullmatch(r'\d+[A-Z]*', t) or t.isupper() or t.lower() == 'sector':
                filtered_tokens.append(t)
        normalized = ' '.join(filtered_tokens)

    normalized = re.sub(r'\s+', ' ', normalized).strip()
    normalized = re.sub(r',\s*$', '', normalized)

    if not re.search(r'(?i)\bbucuresti\b$', normalized):
        normalized += ' bucuresti'

    return normalized

import csv
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
import requests
import os
import time

geolocator = Nominatim(user_agent="geo_csv_script")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

input_file = 'dosare.csv'
output_file = 'dosare_geocode.csv'
negasite_file = 'negasite.txt'

# Determină de la ce linie să continuăm
start_line = 1
if os.path.exists(output_file):
    with open(output_file, newline='', encoding='utf-8') as f_out:
        reader_out = csv.reader(f_out)
        rows = list(reader_out)
        if len(rows) > 1:
            start_line = len(rows)

with open(input_file, newline='', encoding='utf-8') as csvfile_in, \
     open(output_file, 'a', newline='', encoding='utf-8') as csvfile_out, \
     open(negasite_file, 'a', encoding='utf-8') as f_neg:

    reader = csv.DictReader(csvfile_in)
    fieldnames = reader.fieldnames + ['latitude', 'longitude']
    writer = csv.DictWriter(csvfile_out, fieldnames=fieldnames)

    if start_line == 1:
        writer.writeheader()

    for i, row in enumerate(reader, start=1):
        if i < start_line:
            continue

        address = row.get('Adresa contemporană', '').strip()
        if not address:
            print(f"Linia {i}: Adresa goală")
            f_neg.write("Linia {}: Adresă goală\n".format(i))
            row['latitude'] = ''
            row['longitude'] = ''
        else:
            normalized_address = normalize_address(address)
            retries = 5  # încercări multiple în caz de cădere rețea
            while retries > 0:
                try:
                    location = geocode(normalized_address)
                    if location:
                        row['latitude'] = location.latitude
                        row['longitude'] = location.longitude
                        print(f"Linia {i}: {normalized_address} -> {location.latitude}, {location.longitude}")
                    else:
                        row['latitude'] = ''
                        row['longitude'] = ''
                        f_neg.write(f"Linia {i}: {normalized_address}\n")
                        print(f"Linia {i}: {normalized_address} -> NEGASIT")
                    break  # am terminat cu succes
                except (GeocoderUnavailable, GeocoderTimedOut, requests.exceptions.ConnectionError) as e:
                    retries -= 1
                    print(f"Linia {i}: Eroare rețea, mai încerc {retries} -> {normalized_address}")
                    time.sleep(5)
                except Exception as e:
                    row['latitude'] = ''
                    row['longitude'] = ''
                    f_neg.write(f"Linia {i}: {normalized_address} (eroare: {e})\n")
                    print(f"Linia {i}: {normalized_address} -> EROARE: {e}")
                    break

        writer.writerow(row)  # salvăm imediat progresul
        csvfile_out.flush()
        f_neg.flush()
