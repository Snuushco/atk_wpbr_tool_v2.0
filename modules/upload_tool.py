"""
Module met upload- en image processing functies voor Flask backend.
Bevat geen Streamlit of UI-code.
"""
import os
from PIL import Image
import io
from datetime import datetime
import smtplib
from email.message import EmailMessage
from modules.email_config import get_smtp_config

# Zet requirements op module-niveau zodat deze overal beschikbaar is
requirements = {
    'pasfoto': {'min': (276, 355), 'max': (551, 709)},
    'handtekening': {'min': (354, 108), 'max': (945, 287)},
    'bedrijfslogo': {'min': (315, 127), 'max': (945, 382)},
}

def validate_and_resize_image(contents, image_type, filename):
    if image_type not in requirements:
        raise ValueError('Ongeldig afbeeldingstype.')
    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()
        image = Image.open(io.BytesIO(contents))
    except Exception:
        raise ValueError('Bestand is geen geldige afbeelding.')
    min_w, min_h = requirements[image_type]['min']
    max_w, max_h = requirements[image_type]['max']
    width, height = image.size
    # Schaal naar min als kleiner, maar niet groter dan max
    new_w, new_h = width, height
    if width < min_w or height < min_h:
        scale = max(min_w/width, min_h/height)
        new_w, new_h = int(width*scale), int(height*scale)
    if new_w > max_w or new_h > max_h:
        scale = min(max_w/new_w, max_h/new_h)
        new_w, new_h = int(new_w*scale), int(new_h*scale)
    if (new_w, new_h) != (width, height):
        image = image.resize((new_w, new_h), Image.LANCZOS)
    return image

def process_upload(file, image_type):
    """
    Valideer en resize een uploadbestand. Return dict met 'success', 'image' (PIL), 'error' (str), 'orig_size' (tuple), 'resized_size' (tuple), 'min_size', 'max_size'.
    """
    try:
        contents = file.read()
        if len(contents) == 0:
            return {'success': False, 'error': 'Bestand is leeg.'}
        # Originele afmetingen uitlezen
        orig_image = Image.open(io.BytesIO(contents))
        orig_size = orig_image.size
        image = validate_and_resize_image(contents, image_type, file.name)
        resized_size = image.size
        min_size = requirements[image_type]['min']
        max_size = requirements[image_type]['max']
        return {
            'success': True,
            'image': image,
            'error': None,
            'filename': file.name,
            'orig_size': orig_size,
            'resized_size': resized_size,
            'min_size': min_size,
            'max_size': max_size
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_image_email(to_email, image, filename, smtp_config=None):
    msg = EmailMessage()
    msg['Subject'] = 'Geresizede afbeelding van ATK-WPBR Tool'
    msg['From'] = 'aanvraag@atk-wpbr.nl'
    msg['To'] = to_email
    msg.set_content('In de bijlage vindt u de geresizede afbeelding.\n\nMogelijk gemaakt door de ATK-WPBR Tool.\n\nhttps://atk-wpbr.nl')
    # Opslaan als bytes
    img_bytes = io.BytesIO()
    ext = os.path.splitext(filename)[1].lower()
    fmt = 'JPEG' if ext in ['.jpg', '.jpeg'] else 'PNG'
    image.save(img_bytes, format=fmt)
    img_bytes.seek(0)
    maintype = 'image'
    subtype = 'jpeg' if fmt == 'JPEG' else 'png'
    msg.add_attachment(img_bytes.read(), maintype=maintype, subtype=subtype, filename=filename)
    # Dummy SMTP-config als niet opgegeven
    if smtp_config is None:
        smtp_config = get_smtp_config()
    try:
        with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
            server.starttls()
            server.login(smtp_config['user'], smtp_config['password'])
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e) 