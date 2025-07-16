import smtplib
from email.message import EmailMessage
import mimetypes
import os
from dotenv import load_dotenv
import logging
from modules.email_config import get_smtp_config

load_dotenv()

def send_email_smtp(sender, recipient, subject, body, attachments, smtp_server=None, smtp_port=None, smtp_user=None, smtp_password=None):
    try:
        # Haal SMTP settings uit .env als niet opgegeven
        config = get_smtp_config()
        smtp_server = smtp_server or config['server']
        smtp_port = int(smtp_port or config['port'])
        smtp_user = smtp_user or config['user']
        smtp_password = smtp_password or config['password']
        smtp_use_tls = os.getenv("SMTP_USE_TLS", "True").lower() in ("1", "true", "yes")

        msg = EmailMessage()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg['Bcc'] = sender  # Automatische BCC naar afzender
        msg.set_content(body)

        for file_path in attachments:
            if not os.path.isfile(file_path):
                continue
            ctype, encoding = mimetypes.guess_type(file_path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            with open(file_path, 'rb') as f:
                file_data = f.read()
                file_name = os.path.basename(file_path)
                msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=file_name)

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:
        logging.error(f"Fout bij verzenden e-mail: {exc}")
        return False

# Stub voor Resend API (implementatie afhankelijk van gekozen provider)
def send_email_resend(sender, recipient, subject, body, attachments, api_key):
    raise NotImplementedError("Resend API integratie nog niet geïmplementeerd.") 