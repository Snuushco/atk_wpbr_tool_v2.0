import logging
from PIL import Image
import os
from io import BytesIO
from .upload_tool import validate_and_resize_image

def validate_and_resize_image(image_bytes, image_type, filename):
    # Log basisinformatie
    logging.info(f"Image processing: {filename}, type={image_type}, size={len(image_bytes)} bytes")
    # Definieer de eisen per type
    requirements = {
        'pasfoto': {'min': (276, 355), 'max': (551, 709)},
        'handtekening': {'min': (354, 108), 'max': (945, 287)},
        'bedrijfslogo': {'min': (315, 127), 'max': (945, 382)},
    }
    if image_type not in requirements:
        logging.error(f"Ongeldig afbeeldingstype: {image_type}")
        raise ValueError('Ongeldig afbeeldingstype.')

    min_size = requirements[image_type]['min']
    max_size = requirements[image_type]['max']

    # Open de afbeelding
    try:
        bio = BytesIO(image_bytes)
        img = Image.open(bio)
        img.verify()  # Check of het echt een afbeelding is
        bio.seek(0)
        img = Image.open(bio)  # Open opnieuw voor bewerking
    except Exception as e:
        logging.error(f"Fout bij openen afbeelding {filename}: {e}")
        raise ValueError(f'Bestand is geen geldige afbeelding: {e}')

    # Controleer formaat
    if img.format not in ['JPEG', 'JPG', 'PNG']:
        logging.error(f"Ongeldig formaat {img.format} voor {filename}")
        raise ValueError('Alleen JPG of PNG toegestaan.')

    # Bepaal nieuwe grootte (binnen min/max, aspect ratio behouden)
    width, height = img.size
    min_w, min_h = min_size
    max_w, max_h = max_size

    # Schaal naar min als kleiner, maar niet groter dan max
    new_w, new_h = width, height
    if width < min_w or height < min_h:
        scale = max(min_w/width, min_h/height)
        new_w, new_h = int(width*scale), int(height*scale)
    if new_w > max_w or new_h > max_h:
        scale = min(max_w/new_w, max_h/new_h)
        new_w, new_h = int(new_w*scale), int(new_h*scale)
    resized = (new_w, new_h) != (width, height)
    if resized:
        img = img.resize((new_w, new_h), Image.LANCZOS)
        logging.info(f"Afbeelding {filename} resized van {width}x{height} naar {new_w}x{new_h}")

    # Opslaan als geoptimaliseerd bestand (zelfde extensie)
    output = BytesIO()
    ext = 'JPEG' if img.format in ['JPEG', 'JPG'] else 'PNG'
    img.save(output, format=ext, optimize=True, quality=85)
    output.seek(0)
    return output.read(), resized 