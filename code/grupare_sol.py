import pandas as pd
import re

# 1. Încarcă CSV
df = pd.read_csv("dosare_geocode_cu_solutie.csv")

def classify_solution_regex(sol):
    if pd.isna(sol):
        return "NONE"
    sol = sol.strip()

    # Transformă tot în lowercase pentru comparații corecte
    sol_lower = sol.lower()

    # 🔹 1. Restituire (orice formă care conține "restit")
    if re.search(r"restit", sol_lower):
        return "Restituire"

    # 🔹 2. Despăgubiri / compensații (MRE, MCP, masuri reparatorii, compensare)
    if re.search(r"\bmre\b", sol_lower) or \
       re.search(r"\bmcp\b", sol_lower) or \
       re.search(r"masuri", sol_lower) or \
       re.search(r"compens", sol_lower):
        return "Compensare/Despagubiri"

    # 🔹 3. Respins / negative (respins, resp., se respinge, RN)
    if re.search(r"resp", sol_lower) or re.search(r"\brn\b", sol_lower):
        return "Respins/Negativ"

    # 🔹 4. Revocare / anulare
    if re.search(r"revoc", sol_lower) or re.search(r"anul", sol_lower):
        return "Revocare/Anulare"

    # 🔹 5. Declinare / transfer (declinare competență, DJCL, transmis ANRP/AVAS)
    if re.search(r"declin", sol_lower) or \
       re.search(r"djcl", sol_lower) or \
       re.search(r"transmis", sol_lower):
        return "Declinare/Transfer"

    # 🔹 dacă nu se potrivește în niciun grup – rămâne cum e
    return sol

# Aplicăm funcția pe coloană
df["Solutie_grup"] = df["Solutie_string"].apply(classify_solution_regex)

# Salvăm rezultatul
df.to_csv("dosare_geocode_grupate_regex.csv", index=False)

print("✅ Clasificare făcută pe baza regex. Noul fișier este 'dosare_geocode_grupate_regex.csv'.")
