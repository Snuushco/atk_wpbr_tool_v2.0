SMTP_PASSWORD veilig opslaan in .env
====================================

1. Genereer een AES-sleutel (bijvoorbeeld 32 bytes voor AES-256):
   >>> import os, base64
   >>> print(base64.b64encode(os.urandom(32)).decode())

2. Zet deze sleutel als SMTP_KEY in je .env (deel deze nooit publiek!):
   SMTP_KEY=... (base64 string)

3. Encrypt je SMTP-wachtwoord:
   >>> from modules.email_config import encrypt_aes
   >>> encrypted = encrypt_aes('JOUW_WACHTWOORD', 'JOUW_SMTP_KEY_BASE64')
   >>> print(encrypted)

4. Zet de output als SMTP_PASSWORD in je .env:
   SMTP_PASSWORD=... (base64 string)

5. De app zal automatisch SMTP_PASSWORD decrypten met SMTP_KEY.

Let op: Bewaar SMTP_KEY veilig en deel deze nooit in de repo of online build! 