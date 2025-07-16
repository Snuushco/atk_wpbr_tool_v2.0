from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
from .upload_tool import validate_and_resize_image

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Voeg mapping van key naar label toe
BIJLAGE_LABELS = {
    'id': 'Kleurenkopie identiteitsbewijs medewerker',
    'pasfoto': 'Pasfoto medewerker',
    'handtekening': 'Handtekening los',
    'svpb': 'SVPB verklaring',
    'horeca': 'Diploma Horecaportier',
    'voetbal': 'Certificaat Voetbalsteward',
    'logo': 'Logo organisatie',
    'straf_belgie': 'Verklaring uit strafregister (België)',
    'fuhrung': 'Führungszeugnis (Duitsland)',
    'straf_herkomst': 'Verklaring uit strafregister (herkomst)',
    'pv': 'PV aangifte diefstal/bewijs van vermissing',
}

@router.post("/upload-id")
async def upload_id(
    files: list[UploadFile] = File(..., description="Voor- en/of achterzijde van ID-kaart of paspoort"),
    types: list[str] = Form(..., description="Type per bestand: pasfoto, handtekening, bedrijfslogo, id")
):
    if not files or len(files) == 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Upload minimaal één bestand."})
    if len(files) != len(types):
        return JSONResponse(status_code=400, content={"status": "error", "message": "Voor elk bestand moet een type worden opgegeven."})

    saved_files = []
    # Mapping van frontend type naar backend type
    type_mapping = {
        'logo': 'bedrijfslogo',
        'pasfoto': 'pasfoto',
        'handtekening': 'handtekening',
    }
    for file, image_type in zip(files, types):
        ext = os.path.splitext(file.filename)[1].lower()
        label = BIJLAGE_LABELS.get(image_type, image_type)
        # Voor id-bestanden mag ook pdf
        if image_type == "id":
            allowed_ext = {'.jpg', '.jpeg', '.png', '.pdf'}
        elif image_type == "pasfoto":
            allowed_ext = {'.jpg', '.jpeg', '.png'}
        else:
            allowed_ext = {'.jpg', '.jpeg', '.png'}
        if ext not in allowed_ext:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Fout bij upload van '{label}' (bestand: {file.filename}): Ongeldig bestandstype: {ext}. Alleen {', '.join(allowed_ext).upper()} toegestaan."})
        contents = await file.read()
        if len(contents) == 0:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Fout bij upload van '{label}' (bestand: {file.filename}): Bestand is leeg."})
        if len(contents) > MAX_FILE_SIZE:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Fout bij upload van '{label}' (bestand: {file.filename}): Bestandsgrootte is te groot. Maximaal 10MB toegestaan."})
        # Zet type om indien nodig
        backend_type = type_mapping.get(image_type, image_type)
        try:
            try:
                optimized, resized = validate_and_resize_image(contents, backend_type, file.filename)
            except Exception as e:
                raise Exception(f"Bestand is geen geldige afbeelding: {e}")
        except Exception as e:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Fout bij upload van '{label}' (bestand: {file.filename}): {e}"})
        save_filename = file.filename
        if resized:
            name, ext2 = os.path.splitext(file.filename)
            save_filename = f"{name}_resized{ext2}"
        save_path = os.path.join(UPLOAD_DIR, save_filename)
        with open(save_path, 'wb') as f:
            f.write(optimized)
        saved_files.append(save_filename)
    return {"status": "success", "filenames": saved_files} 