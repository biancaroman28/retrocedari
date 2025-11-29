import re

# -------------------------------------------------------
# 1️⃣ Expresii și funcții de curățare
# -------------------------------------------------------

# scoatem termeni inutili: ETAJ, ETJ, AP, DE LA, CU APA RECE
RE_REMOVE = re.compile(
    r"\b(?:ETAJ|ETJ|AP|DE\s+LA|CU\s+APA\s+RECE)\b",
    flags=re.IGNORECASE
)

def tokens_between_strada_and_sector(seg):
    m_str = re.match(r"(?i)Strada\b", seg)
    if not m_str:
        return None, None, None
    prefix_strada = seg[:m_str.end()]
    rest = seg[m_str.end():]

    m_sector = re.search(r"\bsector\b", rest, flags=re.IGNORECASE)
    if m_sector:
        corp = rest[:m_sector.start()]
        sufix = rest[m_sector.start():]
    else:
        corp = rest
        sufix = ""
    return prefix_strada, corp, sufix


def index_name_bounds(tokens):
    start = None
    for i, t in enumerate(tokens):
        if re.search(r"[A-Za-zĂÂÎȘȚăâîșț]", t):
            start = i
            break
    if start is None:
        return None, None
    end = start
    for j in range(start + 1, len(tokens)):
        if re.fullmatch(r"\d+", tokens[j]):
            break
        end = j
    return start, end


def curata_partea_dupa_strada(text):
    t = RE_REMOVE.sub("", text)
    t = re.sub(r"\s+", " ", t).strip()

    m = re.search(r"\bStrada\b", t, flags=re.IGNORECASE)
    if not m:
        return t

    seg = t[m.start():]
    prefix_strada, corp, sufix = tokens_between_strada_and_sector(seg)
    if prefix_strada is None:
        return t

    tokens = corp.strip().split()
    if not tokens:
        return f"{prefix_strada}{sufix}".strip()

    start_name, end_name = index_name_bounds(tokens)
    if start_name is None:
        return f"{prefix_strada} {corp} {sufix}".strip()

    before_name = tokens[:start_name]
    name_tokens = tokens[start_name:end_name + 1]
    after_name = tokens[end_name + 1:]

    nums_before = [t for t in before_name if t.isdigit()]
    moved_first_num = None

    if len(nums_before) >= 2:
        first_num = nums_before[0]
        last_num = nums_before[-1]
        moved_first_num = first_num
        before_name_clean = [t for t in before_name if not t.isdigit()]
        before_name = before_name_clean + [last_num]

    if moved_first_num:
        after_name = [moved_first_num] + after_name

    seen_num = False
    new_after = []
    for tok in after_name:
        if tok.isdigit():
            if not seen_num:
                new_after.append(tok)
                seen_num = True
        else:
            new_after.append(tok)
    after_name = new_after

    corp_final = " ".join(before_name + name_tokens + after_name).strip()
    return f"{prefix_strada} {corp_final} {sufix}".strip()


def curata_adresa(adresa):
    if ":" in adresa:
        prefix, rest = adresa.split(":", 1)
        rest_curat = curata_partea_dupa_strada(rest)
        return f"{prefix.strip()}: {rest_curat}"
    else:
        return curata_partea_dupa_strada(adresa)


# -------------------------------------------------------
# 2️⃣ Citire / scriere fișiere
# -------------------------------------------------------

input_file = "negasite.txt"
output_file = "negasite_clean.txt"

with open(input_file, "r", encoding="utf-8") as f_in, open(output_file, "w", encoding="utf-8") as f_out:
    for line in f_in:
        line = line.strip()
        if not line:
            continue
        curatat = curata_adresa(line)
        f_out.write(curatat + "\n")

print(f"✅ Fișierul '{output_file}' a fost generat cu succes!")
