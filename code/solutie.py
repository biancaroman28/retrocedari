import pandas as pd
import re

# 1. Încarcă CSV-ul
df = pd.read_csv("dosare_geocode.csv")

# 2. Funcție care extrage partea de după ultima virgulă (Soluția)
def extrage_solutie(text):
    try:
        # Ia tot ce vine după ultima virgulă și scoate spațiile
        return text.split(',')[-1].strip()
    except:
        return None

# 3. Aplicăm funcția pe coloana "Soluție"
df["Solutie_string"] = df["Soluție"].apply(extrage_solutie)

# 4. Salvăm înapoi CSV-ul (sau alt fișier ca să nu strici originalul)
df.to_csv("dosare_geocode_cu_solutie.csv", index=False)

print("✅ Gata! Am creat coloana 'Solutie_string'.")
