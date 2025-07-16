from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory, g
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user, fresh_login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
import json
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import tempfile
import sqlite3
from modules.upload_tool import process_upload
from PIL import Image
from modules.word_generator import generate_word_from_template
import logging
import re
import secrets
from io import BytesIO

# Import Stripe configuratie
from modules.stripe_config import (
    create_payment_intent, get_payment_intent, create_customer, 
    get_customer, verify_webhook_signature, get_price_info, is_stripe_configured
)

# Import email configuratie
from modules.email_config import get_smtp_config

def cleanup_uploaded_files():
    """Clean up all files in the uploads directory for the current session."""
    if 'uploads' in session:
        upload_dir = app.config['UPLOAD_FOLDER']
        for filename in session['uploads'].values():
            if filename:  # Skip None values
                if isinstance(filename, list):
                    # Voor id_file: lijst van bestanden
                    for fname in filename:
                        if fname:
                            file_path = os.path.join(upload_dir, fname)
                            try:
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                    logging.info(f"Cleaned up file: {fname}")
                            except Exception as e:
                                logging.error(f"Error deleting file {file_path}: {str(e)}")
                else:
                    # Voor andere bestanden: enkele bestand
                    file_path = os.path.join(upload_dir, filename)
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logging.info(f"Cleaned up file: {filename}")
                    except Exception as e:
                        logging.error(f"Error deleting file {file_path}: {str(e)}")
        session.pop('uploads', None)
        logging.info("Session uploads cleared")

# Configureer logging
logging.basicConfig(
    filename='app_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Laad environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-please-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# SMTP configuratie
config = get_smtp_config()
SMTP_SERVER = config['server']
SMTP_PORT = config['port']
SMTP_USERNAME = config['user']
SMTP_PASSWORD = config['password']
SMTP_FROM = os.getenv('SMTP_FROM') or SMTP_USERNAME

# Zorg dat upload directory bestaat
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class voor Flask-Login
class User(UserMixin):
    def __init__(self, id, email, name=None, vergunningnummer=None, terms_accepted=False, privacy_accepted=False, terms_accepted_date=None, privacy_accepted_date=None):
        self.id = id
        self.email = email
        self.name = name
        self.vergunningnummer = vergunningnummer
        self.terms_accepted = terms_accepted
        self.privacy_accepted = privacy_accepted
        self.terms_accepted_date = terms_accepted_date
        self.privacy_accepted_date = privacy_accepted_date

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(
            user['id'], 
            user['email'], 
            user['name'], 
            user['vergunningnummer'],
            user['terms_accepted'],
            user['privacy_accepted'],
            user['terms_accepted_date'],
            user['privacy_accepted_date']
        )
    return None

# JWT token decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get('jwt_token')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User(data['user_id'], data['email'], data['name'], data['vergunningnummer'], data['terms_accepted'], data['privacy_accepted'], data['terms_accepted_date'], data['privacy_accepted_date'])
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

def generate_pdf(form_data, uploaded_files):
    # Maak een tijdelijk bestand voor de PDF met een duidelijke naam
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    pdf_filename = f"aanvraag_beveiligingspas_{timestamp}.pdf"
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
    
    # Maak de PDF
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    
    # Voeg content toe
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Aanvraag Beveiligingspas")
    
    y = height - 100
    c.setFont("Helvetica", 12)
    
    # Persoonlijke gegevens
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Persoonlijke gegevens")
    y -= 30
    c.setFont("Helvetica", 12)
    
    for key, value in form_data.items():
        if key.startswith('voornaam') or key.startswith('achternaam') or key.startswith('geboorte'):
            c.drawString(50, y, f"{key.replace('_', ' ').title()}: {value}")
            y -= 20
    
    # Contactgegevens
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Contactgegevens")
    y -= 30
    c.setFont("Helvetica", 12)
    
    for key, value in form_data.items():
        if key in ['email', 'telefoon', 'adres', 'postcode', 'plaats']:
            c.drawString(50, y, f"{key.replace('_', ' ').title()}: {value}")
            y -= 20
    
    # Werkgever gegevens
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Werkgever gegevens")
    y -= 30
    c.setFont("Helvetica", 12)
    
    for key, value in form_data.items():
        if key.startswith('bedrijf'):
            c.drawString(50, y, f"{key.replace('_', ' ').title()}: {value}")
            y -= 20
    
    # Bijgevoegde documenten
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Bijgevoegde documenten")
    y -= 30
    c.setFont("Helvetica", 12)
    
    for file in uploaded_files:
        c.drawString(50, y, os.path.basename(file))
        y -= 20
    
    c.save()
    return pdf_path

def send_email(to_email, subject, body, attachments=None, reply_to=None, bcc=None, html_body=None, logo_path=None, logo_cid=None, user_id=None, form_data_id=None):
    # Genereer unieke email ID voor tracking
    email_id = secrets.token_urlsafe(32)
    
    msg = MIMEMultipart('related')
    alt = MIMEMultipart('alternative')
    
    # Verbeterde email headers voor betere deliverability
    msg['From'] = f"ATK-WPBR Tool <{SMTP_FROM}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['X-Mailer'] = 'ATK-WPBR Tool v2.0'
    msg['X-Priority'] = '3'
    msg['X-MSMail-Priority'] = 'Normal'
    msg['Importance'] = 'Normal'
    
    # Reply-To header instellen
    if reply_to:
        msg['Reply-To'] = reply_to
        # Voeg duidelijke vermelding toe aan email body voor Korpscheftaken
        reply_notice = f"\n\n---\nAntwoord op deze email wordt verwacht op: {reply_to}"
        body += reply_notice
        if html_body:
            reply_notice_html = f'<hr><p><strong>Antwoord op deze email wordt verwacht op:</strong> <a href="mailto:{reply_to}">{reply_to}</a></p>'
            html_body += reply_notice_html
    
    if bcc:
        msg['Bcc'] = bcc
    
    # Voeg tracking pixel toe aan HTML body
    if html_body:
        tracking_pixel = f'<img src="{url_for("email_tracking_pixel", email_id=email_id, _external=True)}" width="1" height="1" style="display:none;" />'
        html_body = html_body.replace('</body>', f'{tracking_pixel}</body>')
        if '</body>' not in html_body:
            html_body += tracking_pixel
    
    alt.attach(MIMEText(body, 'plain', 'utf-8'))
    if html_body:
        alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(alt)
    
    if attachments:
        for file_path in attachments:
            with open(file_path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                msg.attach(part)
    
    # Voeg logo inline toe als cid-image
    if logo_path and logo_cid:
        from email.mime.image import MIMEImage
        with open(logo_path, 'rb') as img:
            mime_img = MIMEImage(img.read())
            mime_img.add_header('Content-ID', f'<{logo_cid}>')
            mime_img.add_header('Content-Disposition', 'inline', filename=os.path.basename(logo_path))
            msg.attach(mime_img)
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            recipients = [to_email]
            if bcc:
                if isinstance(bcc, str):
                    recipients.append(bcc)
                else:
                    recipients.extend(bcc)
            
            # Logging voor debugging
            logging.info(f"E-mail From: {msg['From']}")
            logging.info(f"E-mail To: {to_email}")
            logging.info(f"E-mail Reply-To: {reply_to}")
            logging.info(f"E-mail Bcc: {bcc}")
            logging.info(f"E-mail ID: {email_id}")
            logging.info(f"E-mail Subject: {subject}")
            
            server.sendmail(SMTP_FROM, recipients, msg.as_string())
            
            # Sla email tracking op in database
            conn = get_db_connection()
            conn.execute('''INSERT INTO email_tracking 
                           (email_id, to_email, subject, user_id, form_data_id) 
                           VALUES (?, ?, ?, ?, ?)''', 
                        (email_id, to_email, subject, user_id, form_data_id))
            conn.commit()
            conn.close()
            
        return True
    except Exception as e:
        import traceback
        logging.error(f"Error sending email: {e}\n{traceback.format_exc()}")
        print(f"Error sending email: {e}\n{traceback.format_exc()}")
        return False

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('form'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not (email and password):
            return jsonify({'success': False, 'message': 'Vul alle velden in.'})
            
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['hashed_password'], password):
            if not user['email_verified']:
                return jsonify({
                    'success': False, 
                    'message': 'Je e-mailadres is nog niet geverifieerd. Controleer je inbox voor de verificatie-e-mail.'
                })
            login_user(User(
                user['id'], 
                user['email'], 
                user['name'], 
                user['vergunningnummer'],
                user['terms_accepted'],
                user['privacy_accepted'],
                user['terms_accepted_date'],
                user['privacy_accepted_date']
            ))
            return jsonify({'success': True, 'redirect': url_for('form')})
        else:
            return jsonify({'success': False, 'message': 'Ongeldige inloggegevens.'})
            
    return render_template('login.html')

# --- User database helpers ---
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        vergunningnummer TEXT,
        terms_accepted BOOLEAN DEFAULT 0,
        privacy_accepted BOOLEAN DEFAULT 0,
        terms_accepted_date TIMESTAMP,
        privacy_accepted_date TIMESTAMP,
        telefoon TEXT,
        is_paid_user BOOLEAN DEFAULT 0,
        email_verified BOOLEAN DEFAULT 0,
        verification_token TEXT,
        verification_token_expires TIMESTAMP,
        stripe_customer_id TEXT,
        subscription_status TEXT DEFAULT 'inactive',
        subscription_expires TIMESTAMP
    )''')
    
    # Email tracking tabel voor lees- en ontvangstbevestiging
    conn.execute('''CREATE TABLE IF NOT EXISTS email_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_id TEXT UNIQUE NOT NULL,
        to_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        delivered_at TIMESTAMP,
        read_at TIMESTAMP,
        read_count INTEGER DEFAULT 0,
        user_id INTEGER,
        form_data_id TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Betalingsinformatie tabel
    conn.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        stripe_payment_intent_id TEXT UNIQUE NOT NULL,
        stripe_customer_id TEXT,
        amount INTEGER NOT NULL,
        currency TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    conn.commit()
    conn.close()

init_db()

def check_vergunningnummer(vergunningnummer, wpbr_lijst):
    # wpbr_lijst: lijst van dicts met o.a. 'Vergunning nummer'
    vergunningnummers = {item.get('Vergunning nummer', '').upper() for item in wpbr_lijst}
    return vergunningnummer.upper() in vergunningnummers

def send_verification_email(email, token):
    """Send verification email to user."""
    msg = MIMEMultipart()
    msg['From'] = 'noreply@atk-wpbr.nl'
    msg['To'] = email
    msg['Subject'] = 'Verifieer je e-mailadres - ATK-WPBR Tool'
    
    verification_url = url_for('verify_email', token=token, _external=True)
    
    body = f"""
    Beste gebruiker,
    
    Bedankt voor je registratie bij de ATK-WPBR Tool. Om je account te activeren, klik op onderstaande link:
    
    {verification_url}
    
    Deze link is 24 uur geldig.
    
    Met vriendelijke groet,
    Team ATK-WPBR
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASSWORD'))
            server.send_message(msg)
        return True
    except Exception as e:
        logging.error(f"Error sending verification email: {str(e)}")
        return False

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        vergunningnummer = data.get('vergunningnummer', '').strip().upper()
        
        if not (name and email and password and vergunningnummer):
            return jsonify({'success': False, 'message': 'Vul alle verplichte velden in.'})
            
        # Valideer vergunningnummer
        match = re.match(r'^(ND|BD|HBD|HND|PAC|PGW|POB|VTC)([0-9]{1,5})$', vergunningnummer, re.IGNORECASE)
        if not match:
            return jsonify({'success': False, 'message': 'Vul een geldig vergunningnummer in (bijv. ND06250).'})
            
        type_part = match.group(1)
        num_part = match.group(2).zfill(5)
        vergunningnummer_norm = f"{type_part}{num_part}"
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user:
            conn.close()
            return jsonify({'success': False, 'message': 'Dit e-mailadres is al geregistreerd.'})
            
        hashed_pw = generate_password_hash(password)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Generate verification token
        verification_token = secrets.token_urlsafe(32)
        token_expires = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            conn.execute('''INSERT INTO users 
                (name, email, hashed_password, vergunningnummer, telefoon, terms_accepted, privacy_accepted, 
                terms_accepted_date, privacy_accepted_date, is_paid_user, email_verified, verification_token, 
                verification_token_expires) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (name, email, hashed_pw, vergunningnummer_norm, None, True, True, current_time, current_time, 0, 
                False, verification_token, token_expires))
            conn.commit()
            
            # Send verification email
            if send_verification_email(email, verification_token):
                return jsonify({
                    'success': True, 
                    'message': 'Registratie succesvol. Er is een verificatie-e-mail verzonden naar je e-mailadres.'
                })
            else:
                # If email sending fails, delete the user and return error
                conn.execute('DELETE FROM users WHERE email = ?', (email,))
                conn.commit()
                return jsonify({
                    'success': False, 
                    'message': 'Er is een fout opgetreden bij het verzenden van de verificatie-e-mail. Probeer het later opnieuw.'
                })
        except Exception as e:
            logging.error(f"Error in registration: {str(e)}")
            return jsonify({'success': False, 'message': 'Er is een fout opgetreden bij het registreren.'})
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/verify-email/<token>')
def verify_email(token):
    conn = get_db_connection()
    try:
        # Find user with this token
        user = conn.execute('''
            SELECT * FROM users 
            WHERE verification_token = ? 
            AND verification_token_expires > datetime('now')
            AND email_verified = 0
        ''', (token,)).fetchone()
        
        if user:
            # Update user as verified
            conn.execute('''
                UPDATE users 
                SET email_verified = 1, 
                    verification_token = NULL, 
                    verification_token_expires = NULL 
                WHERE id = ?
            ''', (user['id'],))
            conn.commit()
            flash('Je e-mailadres is geverifieerd. Je kunt nu inloggen.', 'success')
        else:
            flash('Ongeldige of verlopen verificatielink.', 'error')
    except Exception as e:
        logging.error(f"Error in email verification: {str(e)}")
        flash('Er is een fout opgetreden bij het verifiëren van je e-mailadres.', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    cleanup_uploaded_files()
    logout_user()
    return redirect(url_for('index'))

KORPSCHEFTAKEN = {
    "Noord-Nederland": ["ATK.WPBR.korpscheftaken.noord-nederland@politie.nl"],
    "Oost-Nederland": [
        "ATK.WPBR-gelderland-midden.korpscheftaken.oost-nederland@politie.nl",
        "ATK.WPBR-gelderland-zuid.korpscheftaken.oost-nederland@politie.nl",
        "ATK.WPBR-twente.korpscheftaken.oost-nederland@politie.nl",
        "ATK.WPBR-noordoost-gelderland.korpscheftaken.oost-nederland@politie.nl",
        "ATK.WPBR-ijsselland.korpscheftaken.oost-nederland@politie.nl",
    ],
    "Midden-Nederland": ["ATK.WPBR.korpscheftaken.midden-nederland@politie.nl"],
    "Noord-Holland": ["ATK.WPBR.korpscheftaken.noord-holland@politie.nl"],
    "Amsterdam": ["ATK.WPBR.korpscheftaken.amsterdam@politie.nl"],
    "Den Haag": ["ATK.WPBR.korpscheftaken.den-haag@politie.nl"],
    "Rotterdam": ["ATK.WPBR.korpscheftaken.rotterdam@politie.nl"],
    "Zeeland - West-Brabant": ["ATK.WPBR.korpscheftaken.zeeland-west-brabant@politie.nl"],
    "Oost-Brabant": ["ATK.WPBR.korpscheftaken.oost-brabant@politie.nl"],
    "Limburg": ["ATK.WPBR.korpscheftaken.limburg@politie.nl"],
    "TEST": [
        "guus.bongaerts@live.nl",
        "guus@praesidion.nl",
        "snuushco@gmail.com",
    ],
}

SESSION_TIMEOUT_MINUTES = 30
ADMIN_EMAIL = 'snuushco@gmail.com'  # Deze admin blijft altijd ingelogd

@app.before_request
def check_session_timeout():
    if current_user.is_authenticated:
        last_activity = session.get('last_activity')
        if last_activity:
            last_activity = datetime.fromisoformat(last_activity)
            if datetime.now() - last_activity > timedelta(minutes=30):
                cleanup_uploaded_files()
                logout_user()
                flash('Uw sessie is verlopen. Log opnieuw in om door te gaan.', 'warning')
                return redirect(url_for('login'))
        session['last_activity'] = datetime.now().isoformat()

@app.teardown_request
def cleanup_on_request_end(exception=None):
    """Clean up uploaded files when the request ends with an error."""
    if exception is not None:
        cleanup_uploaded_files()

@app.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    edit_mode = False
    if request.method == 'GET' and request.args.get('edit') == '1':
        edit_mode = True
    if request.method == 'POST':
        try:
            print('DEBUG: POST ontvangen op /form, redirect naar /controle')
            # Sla alle form data en uploads tijdelijk op in session
            form_data = request.form.to_dict()
            session['form_data'] = form_data
            uploads = {}
            
            # Toegestane bestandstypen
            ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf', 'docx'}
            
            def allowed_file(filename):
                return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
            
            # Haal bestaande uploads op (voor behoud bij wijzigen)
            existing_uploads = session.get('uploads', {})
            
            # Verwerk client-side uploads
            # Speciaal voor id_file: altijd als lijst opslaan
            if 'id_file' in request.files:
                id_files = request.files.getlist('id_file')
                id_paths = []
                for file in id_files:
                    if file and file.filename:
                        if not allowed_file(file.filename):
                            cleanup_uploaded_files()  # Clean up on validation error
                            flash(f'Ongeldig bestandstype voor ID: {file.filename}. Toegestane types: {", ".join(ALLOWED_EXTENSIONS)}', 'error')
                            return render_template('form.html', korpscheftaken=json.dumps(KORPSCHEFTAKEN), form_data=form_data, uploads=existing_uploads, edit_mode=edit_mode)
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(file_path)
                        id_paths.append(filename)
                if id_paths:
                    uploads['id_file'] = id_paths
                elif 'id_file' in existing_uploads:
                    uploads['id_file'] = existing_uploads['id_file']
            
            # Overige uploads (enkelvoudig)
            all_upload_keys = [
                'pasfoto_file', 'handtekening_file', 'svpb_file', 'horeca_file', 'voetbal_file',
                'logo_file', 'straf_belgie_file', 'fuhrung_file', 'straf_herkomst_file', 'pv_file'
            ]
            
            for key in all_upload_keys:
                file = request.files.get(key)
                if file and file.filename:
                    if not allowed_file(file.filename):
                        cleanup_uploaded_files()  # Clean up on validation error
                        flash(f'Ongeldig bestandstype voor {key}: {file.filename}. Toegestane types: {", ".join(ALLOWED_EXTENSIONS)}', 'error')
                        return render_template('form.html', korpscheftaken=json.dumps(KORPSCHEFTAKEN), form_data=form_data, uploads=existing_uploads, edit_mode=edit_mode)
                    
                    filename = secure_filename(file.filename)
                    
                    # Resize voor pasfoto, handtekening en logo
                    if key in ['pasfoto_file', 'handtekening_file', 'logo_file']:
                        image_type = (
                            'pasfoto' if key == 'pasfoto_file' else
                            'handtekening' if key == 'handtekening_file' else
                            'bedrijfslogo' if key == 'logo_file' else None
                        )
                        if image_type:
                            file.stream.seek(0)
                            result = process_upload(file, image_type)
                            if not result['success']:
                                cleanup_uploaded_files()  # Clean up on error
                                flash(f"Fout bij verwerken van {key}: {result['error']}", 'error')
                                return render_template('form.html', korpscheftaken=json.dumps(KORPSCHEFTAKEN), form_data=form_data, uploads=existing_uploads, edit_mode=edit_mode)
                            # Sla geresizede afbeelding op met _resized in de naam
                            name, ext = os.path.splitext(filename)
                            resized_filename = f"{name}_resized{ext}"
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], resized_filename)
                            fmt = 'JPEG' if ext in ['.jpg', '.jpeg'] else 'PNG'
                            result['image'].save(file_path, format=fmt)
                            uploads[key] = resized_filename
                            continue
                    
                    # Standaard opslaan voor andere uploads (met originele naam)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    uploads[key] = filename
                elif key in existing_uploads:
                    uploads[key] = existing_uploads[key]
            
            session['uploads'] = uploads
            return redirect(url_for('controle'))
            
        except Exception as e:
            cleanup_uploaded_files()  # Clean up on any error
            logging.error(f"Error in form submission: {str(e)}")
            flash('Er is een fout opgetreden bij het verwerken van het formulier.', 'error')
            return redirect(url_for('form'))
    
    # GET: altijd leeg formulier, behalve bij wijzigen
    if request.method == 'GET' and request.args.get('edit') == '1':
        form_data = session.get('form_data', {})
        # Bij wijzigen: toon geen uploads (deze zijn al opgeschoond door /wijzigen route)
        uploads = {}
        return render_template('form.html', korpscheftaken=json.dumps(KORPSCHEFTAKEN), form_data=form_data, uploads=uploads, edit_mode=True)
    else:
        session.pop('form_data', None)
        session.pop('uploads', None)
        form_data = {}
    
    return render_template('form.html', korpscheftaken=json.dumps(KORPSCHEFTAKEN), form_data=form_data, uploads={}, edit_mode=False)

@app.route('/controle', methods=['GET', 'POST'])
@login_required
def controle():
    form_data = session.get('form_data', {})
    uploads = session.get('uploads', {}) or {}
    user_email = session.get('user_email', '')
    logging.info(f"User email from session: {user_email}")
    if request.method == 'POST':
        # Bij definitief verzenden: stuur alles door naar /verzenden
        return redirect(url_for('verzenden'))

    # Bereid de bevestigingsinformatie voor
    bevestiging_info = {
        'naam': f"{form_data.get('voornamen', '')} {form_data.get('achternaam', '')}",
        'afdeling': form_data.get('afdeling_select', ''),
        'email_afdeling': form_data.get('email_opties_select', ''),
        'datum': datetime.now().strftime('%d-%m-%Y %H:%M'),
        'aantal_bijlagen': len(uploads),
        'Kopie wordt verstuurd naar': user_email
    }
    logging.info(f"Bevestiging info: {bevestiging_info}")

    # --- Uploads voorbereiden voor controlepagina ---
    uploads_clean = {}
    resized_keys = ['pasfoto_file', 'handtekening_file', 'logo_file']
    preview_exts = ['.jpg', '.jpeg', '.png']
    previews = []
    # Definieer alle mogelijke upload keys
    all_upload_keys = [
        'id_file', 'pasfoto_file', 'handtekening_file', 'svpb_file', 'horeca_file', 'voetbal_file',
        'logo_file', 'straf_belgie_file', 'fuhrung_file', 'straf_herkomst_file', 'pv_file'
    ]
    for key in all_upload_keys:
        val = uploads.get(key)
        if not val:
            continue
        # Zorg dat elke upload als lijst wordt opgeslagen in uploads_clean
        if isinstance(val, list):
            uploads_clean[key] = []
            for v in val:
                orig = v
                clean = orig
                if key in resized_keys:
                    for prefix in ['pasfoto_file_', 'handtekening_file_', 'logo_file_']:
                        if clean.startswith(prefix):
                            clean = clean[len(prefix):]
                    name, ext = os.path.splitext(clean)
                    clean = f"{name}_resized{ext}"
                else:
                    for prefix in ['id_file_', 'svpb_file_', 'horeca_file_', 'voetbal_file_', 'straf_belgie_file_', 'fuhrung_file_', 'straf_herkomst_file_', 'pv_file_']:
                        if clean.startswith(prefix):
                            clean = clean[len(prefix):]
                uploads_clean[key].append({'filename': clean, 'orig': orig})
                if os.path.splitext(clean)[1].lower() in preview_exts:
                    previews.append(orig)
        else:
            # Converteer enkelvoudige uploads naar een lijst
            orig = val
            clean = orig
            if key in resized_keys:
                for prefix in ['pasfoto_file_', 'handtekening_file_', 'logo_file_']:
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):]
                name, ext = os.path.splitext(clean)
                clean = f"{name}_resized{ext}"
            else:
                for prefix in ['id_file_', 'svpb_file_', 'horeca_file_', 'voetbal_file_', 'straf_belgie_file_', 'fuhrung_file_', 'straf_herkomst_file_', 'pv_file_']:
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):]
            uploads_clean[key] = [{'filename': clean, 'orig': orig}]
            if os.path.splitext(clean)[1].lower() in preview_exts:
                previews.append(orig)
    resized_success = any(k in uploads for k in resized_keys)

    # Verzamel info van geresizede afbeeldingen (naam, orig_size, resized_size)
    resized_files_info = []
    for k in resized_keys:
        v = uploads.get(k)
        if v:
            # Zoek het bestand in de uploads-map en haal afmetingen op
            if isinstance(v, list):
                for fname in v:
                    info = {'filename': fname, 'orig_size': None, 'resized_size': None}
                    # Zoek info in uploads_clean
                    for entry in uploads_clean.get(k, []):
                        if entry['filename'] == fname or entry['orig'] == fname:
                            info['orig_size'] = entry.get('orig_size')
                            info['resized_size'] = entry.get('resized_size')
                    # Probeer afmetingen uit bestand te halen als niet aanwezig
                    if not info['resized_size']:
                        try:
                            from PIL import Image
                            im = Image.open(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                            info['resized_size'] = im.size
                        except Exception:
                            pass
                    resized_files_info.append(info)
            else:
                fname = v
                info = {'filename': fname, 'orig_size': None, 'resized_size': None}
                # Zoek info in uploads_clean
                entries = uploads_clean.get(k, [])
                for entry in entries:
                    if entry['filename'] == fname or entry['orig'] == fname:
                        info['orig_size'] = entry.get('orig_size')
                        info['resized_size'] = entry.get('resized_size')
                # Probeer afmetingen uit bestand te halen als niet aanwezig
                if not info['resized_size']:
                    try:
                        from PIL import Image
                        im = Image.open(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                        info['resized_size'] = im.size
                    except Exception:
                        pass
                resized_files_info.append(info)

    # Verzamel bestandsnamen van geresizede afbeeldingen
    resized_files = []
    for k in resized_keys:
        v = uploads.get(k)
        if v:
            if isinstance(v, list):
                resized_files.extend(v)
            else:
                resized_files.append(v)

    # --- Word-template mapping (zoals bij verzenden) ---
    template_data = {
        "bedrijfsnaam": form_data.get("bedrijfsnaam", ""),
        "straat_bedrijf": form_data.get("straat_bedrijf", ""),
        "postcode_bedrijf": form_data.get("postcode_bedrijf", ""),
        "plaats_bedrijf": form_data.get("plaats_bedrijf", ""),
        "vergunning_type": form_data.get("vergunning_type", ""),
        "vergunning_nummer": form_data.get("vergunning_nummer", ""),
        "email_bedrijf": form_data.get("email_bedrijf", ""),
        "telefoon_bedrijf": form_data.get("telefoon_bedrijf", ""),
        "bsn": form_data.get("bsn", ""),
        "voorvoegsel": form_data.get("voorvoegsel", ""),
        "achternaam": form_data.get("achternaam", ""),
        "voornamen": form_data.get("voornamen", ""),
        "geboortedatum": form_data.get("geboortedatum", ""),
        "geboorteplaats": form_data.get("geboorteplaats", ""),
        "geboorteland": form_data.get("geboorteland", ""),
        "straat_medewerker": form_data.get("straat_medewerker", ""),
        "huisnummer": form_data.get("huisnummer", ""),
        "postcode_medewerker": form_data.get("postcode_medewerker", ""),
        "woonplaats": form_data.get("woonplaats_medewerker", ""),
        "telefoon_medewerker": form_data.get("telefoon_medewerker", ""),
        "email_medewerker": form_data.get("email_medewerker", ""),
        "svpb_nummer": form_data.get("svpb_nummer", ""),
        "in_opleiding": "ja" if form_data.get("in_opleiding") in ["on", True, "ja"] else "",
        "certificaat_winkelsurveillant": "☒" if form_data.get("certificaat_winkelsurveillant") in ["on", True, "ja"] else "",
        "persoonsbeveiliger": "ja" if form_data.get("persoonsbeveiliger") in ["on", True, "ja"] else "",
        "naam_contactpersoon": form_data.get("naam_contactpersoon", ""),
        "plaats_ondertekening": form_data.get("plaats_ondertekening", ""),
        # Uitbreiding voor alle placeholders uit het screenshot:
        "is_opsporingsambtenaar": "ja" if form_data.get("is_opsporingsambtenaar") in ["on", True, "ja"] else "",
        "sinds": form_data.get("sinds", ""),
        "organisatie": form_data.get("organisatie", ""),
        "functie": form_data.get("functie", ""),
        "functie_gediplomeerd": form_data.get("functie_gediplomeerd", ""),
        "certificaat_persoonsbeveiliger": "ja" if form_data.get("certificaat_persoonsbeveiliger") in ["on", True, "ja"] else "",
        "latere_begindatum": form_data.get("latere_begindatum", ""),
        "einddatum_svpb": form_data.get("einddatum_svpb", ""),
        # Type aanvraag (let op exacte waarde)
        "eerste_aanvraag": "☒" if form_data.get("type_aanvraag") in ["eerste_aanvraag", "Eerste aanvraag"] else "",
        "verlenging_aanvraag": "☒" if form_data.get("type_aanvraag") in ["verlenging_aanvraag", "Verlenging/herscreening"] else "",
        "vervanging_aanvraag": "☒" if form_data.get("type_aanvraag") in ["vervanging_aanvraag", "Vervanging legitimatiebewijs (vermissing/diefstal)"] else "",
        # Bijlagen (checkboxen, direct uit form_data)
        "bijlagen_id": "☒" if form_data.get("id") else "",
        "bijlagen_pasfoto": "☒" if form_data.get("pasfoto") else "",
        "bijlagen_handtekening": "☒" if form_data.get("handtekening") else "",
        "bijlagen_svpb": "☒" if form_data.get("svpb") else "",
        "bijlagen_horeca": "☒" if form_data.get("horeca") else "",
        "bijlagen_voetbal": "☒" if form_data.get("voetbal") else "",
        "bijlagen_logo": "☒" if form_data.get("logo") else "",
        "bijlagen_straf_belgie": "☒" if form_data.get("straf_belgie") else "",
        "bijlagen_fuhrung": "☒" if form_data.get("fuhrung") else "",
        "bijlagen_straf_herkomst": "☒" if form_data.get("straf_herkomst") else "",
        "bijlagen_pv": "☒" if form_data.get("pv") else "",
        "bijlagen_certificaat_winkelsurveillant": "☒" if form_data.get("certificaat_winkelsurveillant") in ["on", True, "ja"] else "",
        "datum_aanvraag": form_data.get("datum_aanvraag", ""),
    }
    # Genereer Word-document en sla pad op in sessie
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'atk_template.docx')
    # Genereer bestandsnaam met vaste waarde en achternaam
    achternaam = form_data.get('achternaam', '')
    word_filename = f"241209 Nieuw Aanvraagformulier {achternaam}.docx"
    word_path = os.path.join(app.config['UPLOAD_FOLDER'], word_filename)
    
    # Genereer Word document
    generate_word_from_template(template_data, template_path, word_path)
    session['word_output_path'] = word_path

    return render_template('controle.html', form_data=form_data, uploads=uploads_clean, bevestiging_info=bevestiging_info, previews=previews, resized_success=resized_success, resized_files_info=resized_files_info)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        return 'Bestand niet gevonden of al verwijderd.', 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/verzenden', methods=['POST'])
@login_required
def verzenden():
    try:
        # Get form data from session
        form_data = session.get('form_data', {})
        if not form_data:
            flash('Geen formuliergegevens gevonden.', 'error')
            return redirect(url_for('form'))

        # Get uploaded files from session
        uploaded_files = session.get('uploads', {})
        if not uploaded_files:
            flash('Geen bestanden gevonden.', 'error')
            return redirect(url_for('form'))

        # Genereer unieke form data ID
        form_data_id = secrets.token_urlsafe(16)
        
        # Prepare email content
        afdeling_email = form_data.get('email_opties_select', '')
        user_email = session.get('user_email', '')
        
        # Email naar afdeling Korpscheftaken
        subject = f"Aanvraag Beveiligingspas - {form_data.get('voornamen', '')} {form_data.get('achternaam', '')}"
        
        # HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Aanvraag Beveiligingspas</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                .section {{ margin-bottom: 20px; }}
                .footer {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 12px; }}
                .reply-notice {{ background-color: #e3f2fd; padding: 15px; border-left: 4px solid #2196f3; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Aanvraag Beveiligingspas</h2>
                    <p><strong>Datum:</strong> {datetime.now().strftime('%d-%m-%Y %H:%M')}</p>
                </div>
                
                <div class="section">
                    <h3>Persoonlijke gegevens</h3>
                    <p><strong>Medewerker:</strong> {form_data.get('voornamen', '')} {form_data.get('achternaam', '')}</p>
                    <p><strong>Bedrijf:</strong> {form_data.get('bedrijfsnaam', '')}</p>
                    <p><strong>Vergunningnummer:</strong> {form_data.get('vergunning_type', '')} {form_data.get('vergunning_nummer', '')}</p>
                    <p><strong>Datum aanvraag:</strong> {form_data.get('datum_aanvraag', '')}</p>
                    <p><strong>Type aanvraag:</strong> {form_data.get('type_aanvraag', '')}</p>
                    <p><strong>Afdeling:</strong> {form_data.get('afdeling_select', '')}</p>
                </div>
                
                <div class="section">
                    <h3>Bijlagen</h3>
                    <ul>
        """
        
        # Voeg bijlagen toe aan email body
        for key, files in uploaded_files.items():
            if files:
                if isinstance(files, list):
                    for file in files:
                        html_body += f"<li>{key}: {file}</li>"
                else:
                    html_body += f"<li>{key}: {files}</li>"
        
        html_body += f"""
                    </ul>
                </div>
                
                <div class="reply-notice">
                    <p><strong>⚠️ Belangrijk:</strong> Antwoord op deze email wordt verwacht op: <a href="mailto:{user_email}">{user_email}</a></p>
                </div>
                
                <div class="footer">
                    <p>Deze aanvraag is automatisch gegenereerd door de ATK-WPBR Tool.</p>
                    <p>Met vriendelijke groet,<br>ATK-WPBR Tool</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text body
        body = f"""
        Aanvraag Beveiligingspas
        ========================
        
        Datum: {datetime.now().strftime('%d-%m-%Y %H:%M')}
        
        Persoonlijke gegevens:
        ----------------------
        Medewerker: {form_data.get('voornamen', '')} {form_data.get('achternaam', '')}
        Bedrijf: {form_data.get('bedrijfsnaam', '')}
        Vergunningnummer: {form_data.get('vergunning_type', '')} {form_data.get('vergunning_nummer', '')}
        Datum aanvraag: {form_data.get('datum_aanvraag', '')}
        Type aanvraag: {form_data.get('type_aanvraag', '')}
        Afdeling: {form_data.get('afdeling_select', '')}
        
        Bijlagen:
        ---------
        {', '.join([str(f) for f in uploaded_files.values() if f])}
        
        ---
        BELANGRIJK: Antwoord op deze email wordt verwacht op: {user_email}
        ---
        
        Deze aanvraag is automatisch gegenereerd door de ATK-WPBR Tool.
        
        Met vriendelijke groet,
        ATK-WPBR Tool
        """
        
        # Prepare attachments
        attachments = []
        for key, files in uploaded_files.items():
            if files:
                if isinstance(files, list):
                    for file in files:
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
                        if os.path.exists(file_path):
                            attachments.append(file_path)
                else:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], files)
                    if os.path.exists(file_path):
                        attachments.append(file_path)
        
        # Send email to afdeling Korpscheftaken
        email_sent = send_email(
            to_email=afdeling_email,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=attachments,
            reply_to=user_email,
            user_id=current_user.id,
            form_data_id=form_data_id
        )
        
        if not email_sent:
            flash('Er is een fout opgetreden bij het verzenden van de email.', 'error')
            return redirect(url_for('controle'))
        
        # Send confirmation email to user
        confirmation_subject = "Bevestiging aanvraag Beveiligingspas"
        confirmation_body = f"""
        Bevestiging aanvraag Beveiligingspas
        ===================================
        
        Beste {form_data.get('voornamen', '')} {form_data.get('achternaam', '')},
        
        Uw aanvraag voor een beveiligingspas is succesvol verzonden naar de afdeling Korpscheftaken.
        
        Details van uw aanvraag:
        ------------------------
        - Medewerker: {form_data.get('voornamen', '')} {form_data.get('achternaam', '')}
        - Bedrijf: {form_data.get('bedrijfsnaam', '')}
        - Vergunningnummer: {form_data.get('vergunning_type', '')} {form_data.get('vergunning_nummer', '')}
        - Afdeling: {form_data.get('afdeling_select', '')}
        - Datum verzending: {datetime.now().strftime('%d-%m-%Y %H:%M')}
        - Verzonden naar: {afdeling_email}
        
        U ontvangt een reactie van de afdeling Korpscheftaken zodra uw aanvraag is verwerkt.
        
        Met vriendelijke groet,
        ATK-WPBR Tool
        """
        
        confirmation_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Bevestiging aanvraag</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4caf50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; text-align: center; }}
                .section {{ margin-bottom: 20px; }}
                .details {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; }}
                .footer {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>✅ Bevestiging aanvraag Beveiligingspas</h2>
                    <p>Uw aanvraag is succesvol verzonden</p>
                </div>
                
                <div class="section">
                    <p>Beste {form_data.get('voornamen', '')} {form_data.get('achternaam', '')},</p>
                    <p>Uw aanvraag voor een beveiligingspas is succesvol verzonden naar de afdeling Korpscheftaken.</p>
                </div>
                
                <div class="section">
                    <h3>Details van uw aanvraag:</h3>
                    <div class="details">
                        <p><strong>Medewerker:</strong> {form_data.get('voornamen', '')} {form_data.get('achternaam', '')}</p>
                        <p><strong>Bedrijf:</strong> {form_data.get('bedrijfsnaam', '')}</p>
                        <p><strong>Vergunningnummer:</strong> {form_data.get('vergunning_type', '')} {form_data.get('vergunning_nummer', '')}</p>
                        <p><strong>Afdeling:</strong> {form_data.get('afdeling_select', '')}</p>
                        <p><strong>Datum verzending:</strong> {datetime.now().strftime('%d-%m-%Y %H:%M')}</p>
                        <p><strong>Verzonden naar:</strong> {afdeling_email}</p>
                    </div>
                </div>
                
                <div class="section">
                    <p>U ontvangt een reactie van de afdeling Korpscheftaken zodra uw aanvraag is verwerkt.</p>
                </div>
                
                <div class="footer">
                    <p>Met vriendelijke groet,<br>ATK-WPBR Tool</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send confirmation email
        confirmation_sent = send_email(
            to_email=user_email,
            subject=confirmation_subject,
            body=confirmation_body,
            html_body=confirmation_html,
            user_id=current_user.id,
            form_data_id=form_data_id
        )
        
        # Store email tracking info in session for bevestiging page
        session['last_email_id'] = form_data_id
        session['email_sent_to'] = afdeling_email
        session['confirmation_sent'] = confirmation_sent
        
        # After successful submission, clean up the files
        cleanup_uploaded_files()
        
        # Clear form data from session
        session.pop('form_data', None)
        
        return redirect(url_for('bevestiging'))
    except Exception as e:
        logging.error(f"Error in verzenden: {str(e)}")
        flash('Er is een fout opgetreden bij het verzenden van het formulier.', 'error')
        return redirect(url_for('form'))

@app.route('/bevestiging')
@login_required
def bevestiging():
    # Haal eerst de form_data op voordat we deze verwijderen
    form_data = session.get('form_data', {})
    
    # Verwijder nu pas de uploads en form_data
    uploads = session.pop('uploads', {})
    for v in uploads.values():
        if isinstance(v, list):
            for f in v:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], f)
                if os.path.exists(file_path):
                    os.remove(file_path)
        else:
            if v:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], v)
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    # Verwijder form_data uit sessie
    session.pop('form_data', None)
    
    # Haal email tracking informatie op
    email_tracking_info = {}
    last_email_id = session.get('last_email_id')
    if last_email_id:
        try:
            conn = get_db_connection()
            tracking = conn.execute('''SELECT * FROM email_tracking 
                                     WHERE form_data_id = ? AND user_id = ? 
                                     ORDER BY sent_at DESC''', 
                                      (last_email_id, current_user.id)).fetchall()
            conn.close()
            
            if tracking:
                email_tracking_info = {
                    'main_email': {
                        'sent_at': tracking[0]['sent_at'],
                        'delivered_at': tracking[0]['delivered_at'],
                        'read_at': tracking[0]['read_at'],
                        'read_count': tracking[0]['read_count']
                    },
                    'confirmation_email': {
                        'sent_at': tracking[1]['sent_at'] if len(tracking) > 1 else None,
                        'delivered_at': tracking[1]['delivered_at'] if len(tracking) > 1 else None,
                        'read_at': tracking[1]['read_at'] if len(tracking) > 1 else None,
                        'read_count': tracking[1]['read_count'] if len(tracking) > 1 else 0
                    }
                }
        except Exception as e:
            logging.error(f"Error getting email tracking info: {str(e)}")
    
    # Bereid de bevestigingsinformatie voor
    bevestiging_info = {
        'naam': f"{form_data.get('voornamen', '')} {form_data.get('achternaam', '')}",
        'afdeling': form_data.get('afdeling_select', ''),
        'email_afdeling': form_data.get('email_opties_select', ''),
        'datum': datetime.now().strftime('%d-%m-%Y %H:%M'),
        'aantal_bijlagen': len(uploads),
        'Kopie wordt verstuurd naar': session.get('user_email', ''),
        'email_tracking': email_tracking_info,
        'email_sent_to': session.get('email_sent_to', ''),
        'confirmation_sent': session.get('confirmation_sent', False)
    }
    
    # Clear email tracking session data
    session.pop('last_email_id', None)
    session.pop('email_sent_to', None)
    session.pop('confirmation_sent', None)
    
    return render_template('bevestiging.html', bevestiging=bevestiging_info)

@app.route('/download_word')
@login_required
def download_word():
    word_path = session.get('word_output_path')
    if not word_path or not os.path.exists(word_path):
        flash('Geen Word-bestand beschikbaar voor download.', 'error')
        return redirect(url_for('controle'))
    return send_from_directory(
        directory=os.path.dirname(word_path),
        path=os.path.basename(word_path),
        as_attachment=True
    )

@app.before_request
def log_request_info():
    logging.info(f"REQUEST: {request.method} {request.path} - form: {request.form.to_dict()} - args: {request.args.to_dict()} - files: {[f for f in request.files]}")

@app.after_request
def log_response_info(response):
    logging.info(f"RESPONSE: {request.method} {request.path} - status: {response.status_code}")
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    error_msg = f"ERROR: {request.method} {request.path} - {e}\n{traceback.format_exc()}"
    logging.error(error_msg)
    return f"Er is een interne fout opgetreden: {str(e)}", 500

# Voeg toe na app = Flask(__name__)
from datetime import datetime
app.jinja_env.globals.update(now=lambda: datetime.now())

@app.route('/profiel')
@login_required
def profiel():
    return render_template('profiel.html')

@app.route('/wpbr.json')
def serve_wpbr_json():
    return send_from_directory(os.path.dirname(__file__), 'wpbr.json')

@app.route('/profiel/update', methods=['POST'])
@login_required
def profiel_update():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    if not name or not email:
        return jsonify({'success': False, 'message': 'Naam en e-mailadres mogen niet leeg zijn.'})
    conn = get_db_connection()
    try:
        # Controleer of e-mailadres al bestaat bij een andere gebruiker
        user = conn.execute('SELECT * FROM users WHERE email = ? AND id != ?', (email, current_user.id)).fetchone()
        if user:
            conn.close()
            return jsonify({'success': False, 'message': 'Dit e-mailadres is al in gebruik.'})
        conn.execute('UPDATE users SET name = ?, email = ? WHERE id = ?', (name, email, current_user.id))
        conn.commit()
        conn.close()
        # Update current_user direct
        current_user.name = name
        current_user.email = email
        return jsonify({'success': True, 'message': 'Gegevens succesvol bijgewerkt.'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'Fout bij opslaan: {e}'})

@app.route('/profiel/wachtwoord', methods=['POST'])
@login_required
def profiel_wachtwoord():
    data = request.get_json()
    current_pw = data.get('currentPassword', '').strip()
    new_pw = data.get('newPassword', '').strip()
    if not current_pw or not new_pw:
        return jsonify({'success': False, 'message': 'Vul alle velden in.'})
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (current_user.id,)).fetchone()
    if not user or not check_password_hash(user['hashed_password'], current_pw):
        conn.close()
        return jsonify({'success': False, 'message': 'Huidig wachtwoord is onjuist.'})
    if len(new_pw) < 8:
        conn.close()
        return jsonify({'success': False, 'message': 'Nieuw wachtwoord moet minimaal 8 tekens zijn.'})
    hashed_pw = generate_password_hash(new_pw)
    conn.execute('UPDATE users SET hashed_password = ? WHERE id = ?', (hashed_pw, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Wachtwoord succesvol gewijzigd.'})

@app.route('/beta')
def beta():
    return render_template('landingspagina.html')

@app.route('/beta/register', methods=['POST'])
def beta_register():
    data = request.get_json()
    bedrijf = data.get('bedrijf', '').strip()
    vergunningnummer = data.get('vergunningnummer', '').strip().upper()
    email = data.get('email', '').strip()
    telefoon = data.get('telefoon', '').strip()  # mag leeg zijn
    password = data.get('password', '')
    terms_accepted = data.get('terms_accepted')
    privacy_accepted = data.get('privacy_accepted')
    # Maak telefoon optioneel
    if not (bedrijf and vergunningnummer and email and password):
        return jsonify({'success': False, 'message': 'Vul alle verplichte velden in.'})
    if not (terms_accepted and privacy_accepted):
        return jsonify({'success': False, 'message': 'U moet akkoord gaan met de Gebruikersovereenkomst en Privacyverklaring.'})
    import re
    match = re.match(r'^(ND|BD|HBD|HND|PAC|PGW|POB|VTC)([0-9]{1,5})$', vergunningnummer, re.IGNORECASE)
    if not match:
        return jsonify({'success': False, 'message': 'Vul een geldig vergunningnummer in (bijv. ND06250).'})
    type_part = match.group(1).upper()
    num_part = match.group(2).zfill(5)
    vergunningnummer_norm = f"{type_part}{num_part}"
    # WPBR-koppeling
    try:
        with open(os.path.join(os.path.dirname(__file__), 'wpbr.json'), 'r', encoding='utf-8') as f:
            wpbr_lijst = json.load(f)
    except Exception:
        return jsonify({'success': False, 'message': 'WPBR-register niet beschikbaar.'})
    bedrijfObj = next((item for item in wpbr_lijst if (item.get('Vergunning nummer','').upper() == vergunningnummer_norm)), None)
    if not bedrijfObj:
        return jsonify({'success': False, 'message': 'Dit vergunningnummer is niet gevonden in het WPBR-register van Justis.'})
    # Database: voeg kolom telefoon en akkoordvelden toe indien nodig
    conn = get_db_connection()
    try:
        conn.execute('ALTER TABLE users ADD COLUMN telefoon TEXT')
        conn.execute('ALTER TABLE users ADD COLUMN terms_accepted BOOLEAN DEFAULT 0')
        conn.execute('ALTER TABLE users ADD COLUMN privacy_accepted BOOLEAN DEFAULT 0')
        conn.execute('ALTER TABLE users ADD COLUMN terms_accepted_date TIMESTAMP')
        conn.execute('ALTER TABLE users ADD COLUMN privacy_accepted_date TIMESTAMP')
        conn.execute('ALTER TABLE users ADD COLUMN is_paid_user BOOLEAN DEFAULT 0')
    except Exception:
        pass
    # Check op bestaand e-mail of vergunningnummer
    user = conn.execute('SELECT * FROM users WHERE email = ? OR vergunningnummer = ?', (email, vergunningnummer_norm)).fetchone()
    if user:
        conn.close()
        return jsonify({'success': False, 'message': 'Dit e-mailadres of vergunningnummer is al geregistreerd.'})
    hashed_pw = generate_password_hash(password)
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('INSERT INTO users (name, email, hashed_password, vergunningnummer, telefoon, terms_accepted, privacy_accepted, terms_accepted_date, privacy_accepted_date, is_paid_user) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (bedrijf, email, hashed_pw, vergunningnummer_norm, telefoon, True, True, current_time, current_time, 0))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Bedankt voor je aanmelding. We nemen spoedig contact op.'})

@app.route('/gebruikersovereenkomst')
def gebruikersovereenkomst():
    return render_template('gebruikersovereenkomst.html')

@app.route('/privacyverklaring')
def privacyverklaring():
    return render_template('privacyverklaring.html')

@app.route('/cleanup', methods=['POST'])
@login_required
def cleanup():
    """Cleanup endpoint voor client-side cleanup calls."""
    try:
        cleanup_uploaded_files()
        return jsonify({'success': True, 'message': 'Uploads opgeschoond'})
    except Exception as e:
        logging.error(f"Error in cleanup endpoint: {str(e)}")
        return jsonify({'success': False, 'message': 'Fout bij opschonen'}), 500

def send_feedback_email(user_data, feedback_data):
    """Send feedback email to support."""
    msg = MIMEMultipart()
    msg['From'] = 'noreply@atk-wpbr.nl'
    msg['To'] = 'support@atk-wpbr.nl'
    msg['Subject'] = f'Feedback ATK-WPBR Tool - Beoordeling: {feedback_data["rating"]}/5'
    
    # Create email body with user details and feedback
    body = f"""
    Nieuwe feedback ontvangen van de ATK-WPBR Tool:
    
    Gebruikersgegevens:
    ----------------
    Naam: {user_data['name']}
    E-mail: {user_data['email']}
    Vergunningnummer: {user_data['vergunningnummer']}
    Bedrijf: {user_data.get('bedrijf', 'Niet opgegeven')}
    
    Feedback:
    --------
    Beoordeling: {feedback_data['rating']}/5 sterren
    
    Opmerkingen:
    {feedback_data['feedback_text'] if feedback_data['feedback_text'] else 'Geen opmerkingen'}
    
    Deze feedback is automatisch verzonden via het feedbackformulier op de bevestigingspagina.
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASSWORD'))
            server.send_message(msg)
        return True
    except Exception as e:
        logging.error(f"Error sending feedback email: {str(e)}")
        return False

@app.route('/feedback', methods=['POST'])
@login_required
def feedback():
    """Handle feedback form submission."""
    try:
        data = request.get_json()
        rating = data.get('rating')
        feedback_text = data.get('feedback_text', '').strip()
        
        if not rating:
            return jsonify({'success': False, 'message': 'Selecteer een beoordeling.'})
            
        # Get user data from database
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (current_user.id,)).fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'message': 'Gebruiker niet gevonden.'})
            
        # Prepare user data for email
        user_data = {
            'name': user['name'],
            'email': user['email'],
            'vergunningnummer': user['vergunningnummer'],
            'bedrijf': user.get('bedrijf', 'Niet opgegeven')
        }
        
        # Prepare feedback data
        feedback_data = {
            'rating': rating,
            'feedback_text': feedback_text
        }
        
        # Send feedback email
        if send_feedback_email(user_data, feedback_data):
            return jsonify({'success': True, 'message': 'Bedankt voor je feedback!'})
        else:
            return jsonify({'success': False, 'message': 'Er is een fout opgetreden bij het versturen van je feedback.'})
            
    except Exception as e:
        logging.error(f"Error processing feedback: {str(e)}")
        return jsonify({'success': False, 'message': 'Er is een fout opgetreden bij het verwerken van je feedback.'})

@app.route('/wijzigen')
@login_required
def wijzigen():
    """Route voor het wijzigen van het formulier - verwijdert uploads uit sessie."""
    try:
        # Cleanup uploads uit sessie en server
        cleanup_uploaded_files()
        
        # Behoud alleen de form data
        form_data = session.get('form_data', {})
        
        # Redirect naar formulier in edit mode zonder uploads
        return redirect(url_for('form', edit=1))
        
    except Exception as e:
        logging.error(f"Error in wijzigen route: {str(e)}")
        flash('Er is een fout opgetreden bij het wijzigen van het formulier.', 'error')
        return redirect(url_for('controle'))

@app.route('/email-tracking/<email_id>')
def email_tracking_pixel(email_id):
    """Tracking pixel voor email leesbevestiging."""
    try:
        conn = get_db_connection()
        # Update read_at en increment read_count
        conn.execute('''UPDATE email_tracking 
                       SET read_at = CURRENT_TIMESTAMP, read_count = read_count + 1 
                       WHERE email_id = ?''', (email_id,))
        conn.commit()
        conn.close()
        
        # Return 1x1 transparent GIF
        gif_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        return BytesIO(gif_data).read(), 200, {'Content-Type': 'image/gif'}
    except Exception as e:
        logging.error(f"Error in email tracking pixel: {str(e)}")
        # Return empty response on error
        return '', 204

@app.route('/email-delivered/<email_id>')
def email_delivered(email_id):
    """Callback voor email ontvangstbevestiging (DMARC/SPF)."""
    try:
        conn = get_db_connection()
        # Update delivered_at timestamp
        conn.execute('''UPDATE email_tracking 
                       SET delivered_at = CURRENT_TIMESTAMP 
                       WHERE email_id = ?''', (email_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error in email delivered callback: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/email-status/<email_id>')
@login_required
def email_status(email_id):
    """API endpoint om email status op te halen."""
    try:
        conn = get_db_connection()
        tracking = conn.execute('''SELECT * FROM email_tracking 
                                 WHERE email_id = ? AND user_id = ?''', 
                              (email_id, current_user.id)).fetchone()
        conn.close()
        
        if tracking:
            return jsonify({
                'email_id': tracking['email_id'],
                'to_email': tracking['to_email'],
                'subject': tracking['subject'],
                'sent_at': tracking['sent_at'],
                'delivered_at': tracking['delivered_at'],
                'read_at': tracking['read_at'],
                'read_count': tracking['read_count']
            })
        else:
            return jsonify({'error': 'Email not found'}), 404
    except Exception as e:
        logging.error(f"Error getting email status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/betaal')
@login_required
def betaal():
    if current_user.is_authenticated and getattr(current_user, 'is_paid_user', False):
        flash('Je hebt al toegang tot de tool.', 'success')
        return redirect(url_for('form'))
    price_info = get_price_info()
    return render_template(
        'betaal.html',
        price_info=price_info,
        stripe_public_key=os.getenv('STRIPE_PUBLISHABLE_KEY'),
        current_user=current_user
    )

@app.route('/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent_route():
    data = request.get_json()
    user_id = current_user.id
    email = current_user.email
    name = current_user.name
    # Maak Stripe customer aan indien niet aanwezig
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    stripe_customer_id = user['stripe_customer_id']
    if not stripe_customer_id:
        customer, err = create_customer(email=email, name=name)
        if not customer:
            return jsonify({'success': False, 'message': f'Fout bij aanmaken Stripe klant: {err}'}), 400
        stripe_customer_id = customer['id']
        conn.execute('UPDATE users SET stripe_customer_id = ? WHERE id = ?', (stripe_customer_id, user_id))
        conn.commit()
    conn.close()
    # Maak payment intent aan
    metadata = {'user_id': user_id, 'email': email}
    intent, err = create_payment_intent(metadata=metadata)
    if not intent:
        return jsonify({'success': False, 'message': f'Fout bij aanmaken betaling: {err}'}), 400
    # Sla payment intent op in payments tabel
    conn = get_db_connection()
    conn.execute('''INSERT OR IGNORE INTO payments (user_id, stripe_payment_intent_id, stripe_customer_id, amount, currency, status, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (user_id, intent['id'], stripe_customer_id, intent['amount'], intent['currency'], intent['status'], json.dumps(metadata)))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'client_secret': intent['client_secret']})

@app.route('/payment-success')
@login_required
def payment_success():
    payment_intent_id = request.args.get('payment_intent_id')
    if not payment_intent_id:
        flash('Geen payment_intent_id opgegeven.', 'error')
        return redirect(url_for('betaal'))
    # Controleer status bij Stripe
    intent = get_payment_intent(payment_intent_id)
    if not intent or intent['status'] != 'succeeded':
        flash('Betaling niet succesvol of niet gevonden.', 'error')
        return redirect(url_for('betaal'))
    # Markeer gebruiker als betaald
    conn = get_db_connection()
    conn.execute('UPDATE users SET is_paid_user = 1, subscription_status = ?, subscription_expires = ? WHERE id = ?',
        ('active', (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S'), current_user.id))
    conn.execute('UPDATE payments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE stripe_payment_intent_id = ?',
        ('succeeded', payment_intent_id))
    conn.commit()
    conn.close()
    flash('Betaling succesvol! Je hebt nu toegang tot de tool.', 'success')
    return redirect(url_for('form'))

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    event, err = verify_webhook_signature(payload, sig_header)
    if not event:
        logging.error(f"Stripe webhook signature error: {err}")
        return 'Invalid signature', 400
    # Verwerk relevante Stripe events
    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        payment_intent_id = intent['id']
        metadata = intent.get('metadata', {})
        user_id = metadata.get('user_id')
        # Update payment en gebruiker
        conn = get_db_connection()
        conn.execute('UPDATE payments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE stripe_payment_intent_id = ?',
            ('succeeded', payment_intent_id))
        if user_id:
            conn.execute('UPDATE users SET is_paid_user = 1, subscription_status = ?, subscription_expires = ? WHERE id = ?',
                ('active', (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        conn.close()
        logging.info(f"PaymentIntent {payment_intent_id} succeeded, user {user_id} geactiveerd.")
    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
        payment_intent_id = intent['id']
        conn = get_db_connection()
        conn.execute('UPDATE payments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE stripe_payment_intent_id = ?',
            ('failed', payment_intent_id))
        conn.commit()
        conn.close()
        logging.info(f"PaymentIntent {payment_intent_id} failed.")
    # Andere events kunnen hier worden toegevoegd
    return '', 200

if __name__ == '__main__':
    app.run(host='localhost', port=8000, debug=True) 