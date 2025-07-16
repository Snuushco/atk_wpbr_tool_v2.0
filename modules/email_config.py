import os
from dotenv import load_dotenv
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

def decrypt_aes(ciphertext_b64, key_b64):
    ciphertext = base64.b64decode(ciphertext_b64)
    key = base64.b64decode(key_b64)
    iv = ciphertext[:16]
    ct = ciphertext[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ct) + decryptor.finalize()
    # PKCS7 unpad
    pad_len = padded_plaintext[-1]
    plaintext = padded_plaintext[:-pad_len]
    return plaintext.decode('utf-8')

def encrypt_aes(plaintext, key_b64):
    """
    Encrypt plaintext (str) with AES CBC using base64-encoded key (16, 24, of 32 bytes).
    Returns base64-encoded IV + ciphertext. Gebruik dit om SMTP_PASSWORD veilig in de .env te zetten.
    """
    from cryptography.hazmat.primitives import padding
    import os
    import base64
    key = base64.b64decode(key_b64)
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode('utf-8')) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode('utf-8')

def get_smtp_config():
    load_dotenv()
    smtp_password_enc = os.getenv('SMTP_PASSWORD')
    smtp_key = os.getenv('SMTP_KEY')
    if smtp_password_enc and smtp_key:
        try:
            password = decrypt_aes(smtp_password_enc, smtp_key)
        except Exception:
            password = 'VUL_HIER_HET_WACHTWOORD_IN'
    else:
        password = os.getenv('SMTP_PASSWORD', 'VUL_HIER_HET_WACHTWOORD_IN')
    return {
        'server': os.getenv('SMTP_SERVER', 'smtp.strato.com'),
        'port': int(os.getenv('SMTP_PORT', 587)),
        'user': os.getenv('SMTP_USER', 'aanvraag@atk-wpbr.nl'),
        'password': password,
    } 