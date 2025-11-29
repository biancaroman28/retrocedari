from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os, time

# Folder pentru salvare HTML
OUT_DIR = 'responses/'
os.makedirs(OUT_DIR, exist_ok=True)

# Fișier pentru dosarele sărite
SKIPPED_FILE = "skipped.txt"

TO_REDOWNLOAD = [
    234
]

# Setări Chrome
chrome_options = Options()
chrome_options.add_argument("--disable-gpu")

# Calea către ChromeDriver
driver_path = "/usr/local/bin/chromedriver"

driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
driver.set_page_load_timeout(200)  # maxim 40 secunde pentru încărcarea paginii

for i in TO_REDOWNLOAD:  # RANGE modificabil
    try:
        driver.get("https://www3.pmb.ro/l10")

        print(f"\n👉 Deschide CAPTCHA și rezolvă-l pentru dosarul {i}.")

        # Așteaptă input-ul maxim 20 secunde
        inp = WebDriverWait(driver, 200).until(
            EC.visibility_of_element_located((By.ID, "numar_dosar"))
        )

        # Completează inputul
        inp.clear()
        inp.send_keys(str(i))

        # Apasă butonul
        submit = driver.find_element(
            By.XPATH,
            "/html/body/div[1]/div/div/div/div[2]/div[2]/div[2]/div/div/div[1]/div/div/div[1]/div[1]/form/div/button"
        )
        submit.click()
        time.sleep(2)

        # Salvează HTML-ul
        html = driver.page_source
        with open(os.path.join(OUT_DIR, f"{i}.html"), "w", encoding="utf-8") as f:
            f.write(html)

        print(f"HTML dosar {i} salvat.")

    except Exception as e:
        print(f"Dosar {i} sărit din cauza erorii: {e}")
        with open(SKIPPED_FILE, "a") as f:
            f.write(str(i) + "\n")
        continue

print("\nToate dosarele au fost procesate.")
input("Apasă Enter ca să închizi Chrome...")
driver.quit()
