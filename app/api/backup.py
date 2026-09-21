import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.backup_service import (
    export_database_to_dict,
    encrypt_backup,
    decrypt_backup,
    import_database_from_dict,
    wipe_database
)
from app.services.db_harmonizer import harmonize_database_records
from app.seed_data import run_seed

router = APIRouter(prefix="/backup", tags=["Gestión y Respaldo de Datos"])

@router.get("/export")
def export_backup(passphrase: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Descarga una copia completa de la base de datos en formato JSON con fecha y hora en el nombre.
    Si se proporciona una contraseña ('passphrase'), la copia se cifra con AES-256-GCM.
    """
    data = export_database_to_dict(db)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"cac-elrocho-backup-{timestamp}.json"

    if passphrase and passphrase.strip():
        data = encrypt_backup(data, passphrase.strip())
        filename = f"cac-elrocho-backup-{timestamp}.enc.json"

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/import")
async def import_backup(
    file: UploadFile = File(...),
    passphrase: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Restaura la base de datos a partir de un archivo JSON (plano o cifrado con contraseña).
    """
    try:
        content = await file.read()
        payload = json.loads(content.decode("utf-8"))

        if payload.get("format") == "cac-elrocho-encrypted":
            if not passphrase or not passphrase.strip():
                raise HTTPException(status_code=400, detail="Este archivo está cifrado. Introduce la contraseña de descifrado.")
            payload = decrypt_backup(payload, passphrase.strip())

        import_database_from_dict(db, payload)
        try:
            harmonize_database_records(db)
        except Exception:
            pass
        return {
            "status": "success",
            "message": f"Datos restaurados con éxito ({len(payload.get('informes', []))} informes importados)."
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo de importación: {str(e)}")

@router.post("/wipe")
def clear_all_data(confirm: bool = False, db: Session = Depends(get_db)):
    """
    Vacía de forma irreversible todas las analíticas de la base de datos
    para que el usuario comience con una aplicación 100% limpia.
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Debes confirmar explícitamente la acción de borrado.")
    
    wipe_database(db)
    return {
        "status": "success",
        "message": "Base de datos vaciada con éxito. Lista para incorporar tus analíticas privadas."
    }

@router.post("/reset-demo")
def reset_to_demo(db: Session = Depends(get_db)):
    """
    Restablece los datos demostrativos sintéticos de prueba.
    """
    wipe_database(db)
    run_seed(db)
    return {
        "status": "success",
        "message": "Datos demostrativos restablecidos con éxito."
    }
