import requests
import logging

# Vervang deze URL door de echte download-URL van het WPBR-register (JSON)
WPBR_URL = "https://www.justis.nl/open-registers/wpbr-register.json"
OUTPUT_FILE = "wpbr.json"

logging.basicConfig(level=logging.INFO)

def download_wpbr_json():
    try:
        response = requests.get(WPBR_URL, timeout=30)
        response.raise_for_status()
        with open(OUTPUT_FILE, "wb") as f:
            f.write(response.content)
        logging.info(f"WPBR-register succesvol gedownload naar {OUTPUT_FILE}")
    except Exception as e:
        logging.error(f"Fout bij downloaden WPBR-register: {e}")

if __name__ == "__main__":
    download_wpbr_json() 