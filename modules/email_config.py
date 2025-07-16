import os
from dotenv import load_dotenv

def get_smtp_config():
    load_dotenv()
    return {
        'server': os.getenv('SMTP_SERVER', 'smtp.strato.com'),
        'port': int(os.getenv('SMTP_PORT', 587)),
        'user': os.getenv('SMTP_USER', 'aanvraag@atk-wpbr.nl'),
        'password': os.getenv('SMTP_PASSWORD', 'VUL_HIER_HET_WACHTWOORD_IN'),
    } 