import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import logging
from modules.email_config import get_smtp_config

# Laad environment variables
load_dotenv()

# Configureer logging
logging.basicConfig(level=logging.INFO)

# SMTP configuratie
config = get_smtp_config()
SMTP_SERVER = config['server']
SMTP_PORT = config['port']
SMTP_USERNAME = config['user']
SMTP_PASSWORD = config['password']
SMTP_FROM = os.getenv('SMTP_FROM') or SMTP_USERNAME

def test_email_config():
    """Test de email configuratie en verstuur een test email"""
    
    print("=== Email Configuratie Test ===")
    print(f"SMTP Server: {SMTP_SERVER}")
    print(f"SMTP Port: {SMTP_PORT}")
    print(f"SMTP Username: {SMTP_USERNAME}")
    print(f"SMTP From: {SMTP_FROM}")
    print(f"SMTP Password: {'***' if SMTP_PASSWORD else 'NIET INGESTELD'}")
    
    if not all([SMTP_USERNAME, SMTP_PASSWORD]):
        print("\n❌ Email configuratie is niet compleet!")
        print("Zorg ervoor dat de volgende environment variables zijn ingesteld:")
        print("- SMTP_USERNAME of SMTP_USER")
        print("- SMTP_PASSWORD")
        print("- SMTP_FROM (optioneel, gebruikt anders SMTP_USERNAME)")
        return False
    
    # Test 1: Verbinding testen
    print("\n=== Test 1: SMTP Verbinding ===")
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            print("✅ SMTP verbinding succesvol!")
    except Exception as e:
        print(f"❌ SMTP verbinding gefaald: {e}")
        return False
    
    # Test 2: Test email versturen naar eigen adres
    print("\n=== Test 2: Test Email naar Eigen Adres ===")
    test_email = SMTP_USERNAME  # Verstuur naar eigen adres
    
    msg = MIMEMultipart()
    msg['From'] = f"ATK-WPBR Tool <{SMTP_FROM}>"
    msg['To'] = test_email
    msg['Subject'] = 'Test Email Configuratie - ATK-WPBR Tool'
    msg['X-Mailer'] = 'ATK-WPBR Tool v2.0'
    msg['X-Priority'] = '3'
    msg['X-MSMail-Priority'] = 'Normal'
    msg['Importance'] = 'Normal'
    
    body = """
    Dit is een test email om de email configuratie van de ATK-WPBR Tool te controleren.
    
    Als je deze email ontvangt, werkt de basis email configuratie correct.
    
    Met vriendelijke groet,
    ATK-WPBR Tool
    """
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [test_email], msg.as_string())
            print(f"✅ Test email succesvol verzonden naar: {test_email}")
    except Exception as e:
        print(f"❌ Test email verzending gefaald: {e}")
        return False
    
    # Test 3: Test email met Reply-To header (zoals naar Korpscheftaken)
    print("\n=== Test 3: Test Email met Reply-To Header (Korpscheftaken Simulatie) ===")
    
    msg2 = MIMEMultipart()
    msg2['From'] = f"ATK-WPBR Tool <{SMTP_FROM}>"
    msg2['To'] = test_email
    msg2['Reply-To'] = 'test-reply@atk-wpbr.nl'
    msg2['Subject'] = 'Test Email met Reply-To - ATK-WPBR Tool'
    msg2['X-Mailer'] = 'ATK-WPBR Tool v2.0'
    msg2['X-Priority'] = '3'
    msg2['X-MSMail-Priority'] = 'Normal'
    msg2['Importance'] = 'Normal'
    
    body2 = """
    Dit is een test email met een Reply-To header om te controleren of email spoofing werkt.
    
    Reply-To: test-reply@atk-wpbr.nl
    From: ATK-WPBR Tool <{from_email}>
    
    Als je deze email ontvangt en de Reply-To header correct is ingesteld, 
    zou Korpscheftaken ook emails kunnen ontvangen met een aangepaste Reply-To.
    
    ---
    BELANGRIJK: Antwoord op deze email wordt verwacht op: test-reply@atk-wpbr.nl
    ---
    
    Met vriendelijke groet,
    ATK-WPBR Tool
    """.format(from_email=SMTP_FROM)
    
    msg2.attach(MIMEText(body2, 'plain', 'utf-8'))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [test_email], msg2.as_string())
            print(f"✅ Test email met Reply-To succesvol verzonden naar: {test_email}")
            print("📧 Controleer je inbox voor beide test emails")
    except Exception as e:
        print(f"❌ Test email met Reply-To verzending gefaald: {e}")
        return False
    
    # Test 4: Test HTML email template
    print("\n=== Test 4: Test HTML Email Template ===")
    
    msg3 = MIMEMultipart('related')
    alt = MIMEMultipart('alternative')
    msg3['From'] = f"ATK-WPBR Tool <{SMTP_FROM}>"
    msg3['To'] = test_email
    msg3['Subject'] = 'Test HTML Email Template - ATK-WPBR Tool'
    msg3['X-Mailer'] = 'ATK-WPBR Tool v2.0'
    msg3['X-Priority'] = '3'
    msg3['X-MSMail-Priority'] = 'Normal'
    msg3['Importance'] = 'Normal'
    msg3['Reply-To'] = 'test-reply@atk-wpbr.nl'
    
    html_body = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test HTML Email</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
            .reply-notice { background-color: #e3f2fd; padding: 15px; border-left: 4px solid #2196f3; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Test HTML Email Template</h2>
                <p>Dit is een test van de verbeterde email template</p>
            </div>
            
            <p>Deze email test de nieuwe HTML template met styling en Reply-To functionaliteit.</p>
            
            <div class="reply-notice">
                <p><strong>⚠️ Belangrijk:</strong> Antwoord op deze email wordt verwacht op: <a href="mailto:test-reply@atk-wpbr.nl">test-reply@atk-wpbr.nl</a></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    alt.attach(MIMEText("Test HTML Email Template - ATK-WPBR Tool", 'plain', 'utf-8'))
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg3.attach(alt)
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [test_email], msg3.as_string())
            print(f"✅ Test HTML email template succesvol verzonden naar: {test_email}")
    except Exception as e:
        print(f"❌ Test HTML email template verzending gefaald: {e}")
        return False
    
    print("\n=== Email Configuratie Test Voltooid ===")
    print("✅ Alle tests succesvol!")
    print("\nAanbevelingen:")
    print("1. Controleer je inbox voor alle test emails")
    print("2. Als je de emails ontvangt, werkt de configuratie correct")
    print("3. De verbeterde email headers en Reply-To functionaliteit zijn nu actief")
    print("4. Als Korpscheftaken problemen heeft met gespoofde emails:")
    print("   - Alle emails worden nu via aanvraag@atk-wpbr.nl verzonden")
    print("   - Reply-To adres wordt duidelijk vermeld in de email body")
    print("   - Verbeterde email headers voor betere deliverability")
    
    return True

if __name__ == "__main__":
    test_email_config() 