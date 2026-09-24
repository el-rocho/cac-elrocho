import os
import json
import base64
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app import __version__
from app.models import Paciente, Informe, Analito, Medicion, AuditoriaRango

def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Deriva una clave de 256 bits mediante PBKDF2 con 100,000 iteraciones."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    return kdf.derive(passphrase.encode('utf-8'))

def encrypt_backup(data_dict: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    """Cifra el diccionario de respaldo con AES-256-GCM y sal aleatoria."""
    salt = os.urandom(16)
    key = derive_key(passphrase, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    
    plaintext = json.dumps(data_dict, ensure_ascii=False).encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    return {
        "format": "cac-elrocho-encrypted",
        "version": "1.0",
        "kdf": "PBKDF2HMAC-SHA256",
        "iterations": 100000,
        "salt": base64.b64encode(salt).decode('ascii'),
        "nonce": base64.b64encode(nonce).decode('ascii'),
        "ciphertext": base64.b64encode(ciphertext).decode('ascii')
    }

def decrypt_backup(payload: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    """Descifra el respaldo previamente cifrado con la contraseña del usuario."""
    if payload.get("format") != "cac-elrocho-encrypted":
        raise ValueError("El archivo no tiene el formato de cifrado válido de cac-elrocho.")
    
    try:
        salt = base64.b64decode(payload["salt"])
        nonce = base64.b64decode(payload["nonce"])
        ciphertext = base64.b64decode(payload["ciphertext"])
        
        key = derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))
    except Exception:
        raise ValueError("Contraseña incorrecta o archivo de copia de seguridad dañado.")

def export_database_to_dict(db: Session) -> Dict[str, Any]:
    """Serializa toda la información clínica de la base de datos a un diccionario estándar."""
    paciente = db.query(Paciente).first()
    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    analitos = db.query(Analito).order_by(Analito.orden.asc()).all()
    auditorias = db.query(AuditoriaRango).all()

    backup = {
        "app": "cac-elrocho",
        "version": __version__,
        "paciente": {
            "nombre_completo": paciente.nombre_completo if paciente else "",
            "fecha_nacimiento": paciente.fecha_nacimiento if paciente else "",
            "dni": paciente.dni if paciente else "",
            "sexo": paciente.sexo if paciente else "",
            "centro_referencia": paciente.centro_referencia if paciente else ""
        },
        "analitos": [
            {
                "codigo": a.codigo,
                "nombre_visible": a.nombre_visible,
                "categoria": a.categoria,
                "unidad_estandar": a.unidad_estandar,
                "ref_texto_defecto": a.ref_texto_defecto,
                "orden": a.orden
            }
            for a in analitos
        ],
        "informes": [],
        "auditorias": []
    }

    for inf in informes:
        meds = db.query(Medicion).filter_by(informe_id=inf.id).all()
        backup["informes"].append({
            "fecha": inf.fecha,
            "etiqueta_corta": inf.etiqueta_corta,
            "laboratorio": inf.laboratorio,
            "facultativo": inf.facultativo,
            "referencia": inf.referencia,
            "dictamen_global": inf.dictamen_global,
            "observaciones_ia": inf.observaciones_ia,
            "estado": inf.estado,
            "sha256": inf.sha256,
            "archivo_pdf": inf.archivo_pdf,
            "mediciones": [
                {
                    "analito_codigo": m.analito.codigo if m.analito else "",
                    "valor_numerico": m.valor_numerico,
                    "valor_texto": m.valor_texto,
                    "unidad": m.unidad,
                    "ref_min": m.ref_min,
                    "ref_max": m.ref_max,
                    "ref_texto": m.ref_texto,
                    "estado_semaforo": m.estado_semaforo,
                    "nota_clinica": m.nota_clinica
                }
                for m in meds
            ]
        })

    for aud in auditorias:
        backup["auditorias"].append({
            "analito_codigo": aud.analito.codigo if aud.analito else "",
            "rango_anterior": aud.rango_anterior,
            "rango_nuevo": aud.rango_nuevo,
            "explicacion_ia": aud.explicacion_ia,
            "aplicado_en_historico": aud.aplicado_en_historico,
            "estado": aud.estado or ("aplicado" if aud.aplicado_en_historico else "pendiente"),
            "fecha_aplicacion": aud.fecha_aplicacion.isoformat() if aud.fecha_aplicacion else None
        })

    return backup

def wipe_database(db: Session):
    """Vacía de forma segura todas las mediciones, informes y auditorías."""
    db.query(Medicion).delete()
    db.query(AuditoriaRango).delete()
    db.query(Informe).delete()
    db.query(Analito).delete()
    db.query(Paciente).delete()
    db.commit()

def import_database_from_dict(db: Session, data: Dict[str, Any]):
    """Restaura completamente la base de datos a partir del respaldo JSON."""
    wipe_database(db)

    # 1. Paciente
    p_data = data.get("paciente", {})
    paciente = db.query(Paciente).first()
    if not paciente:
        paciente = Paciente()
        db.add(paciente)
    paciente.nombre_completo = p_data.get("nombre_completo", "Usuario")
    paciente.fecha_nacimiento = p_data.get("fecha_nacimiento", "")
    paciente.dni = p_data.get("dni", "")
    paciente.sexo = p_data.get("sexo", "")
    paciente.centro_referencia = p_data.get("centro_referencia", "")
    db.flush()

    # 2. Analitos
    analitos_map = {}
    for a in data.get("analitos", []):
        analito = Analito(
            codigo=a["codigo"],
            nombre_visible=a["nombre_visible"],
            categoria=a.get("categoria", "bioquimica"),
            unidad_estandar=a["unidad_estandar"],
            ref_texto_defecto=a.get("ref_texto_defecto"),
            orden=a.get("orden", 0)
        )
        db.add(analito)
        db.flush()
        analitos_map[analito.codigo] = analito

    # 3. Informes y Mediciones
    informes_map = {}
    for inf_data in data.get("informes", []):
        inf = Informe(
            paciente_id=paciente.id,
            fecha=inf_data["fecha"],
            etiqueta_corta=inf_data["etiqueta_corta"],
            laboratorio=inf_data.get("laboratorio"),
            facultativo=inf_data.get("facultativo"),
            referencia=inf_data.get("referencia"),
            dictamen_global=inf_data.get("dictamen_global"),
            observaciones_ia=inf_data.get("observaciones_ia"),
            estado=inf_data.get("estado", "confirmado"),
            sha256=inf_data.get("sha256"),
            archivo_pdf=inf_data.get("archivo_pdf")
        )
        db.add(inf)
        db.flush()
        informes_map[inf.etiqueta_corta] = inf

        for m_data in inf_data.get("mediciones", []):
            a_cod = m_data.get("analito_codigo")
            analito_obj = analitos_map.get(a_cod)
            if analito_obj:
                med = Medicion(
                    informe_id=inf.id,
                    analito_id=analito_obj.id,
                    valor_numerico=m_data.get("valor_numerico"),
                    valor_texto=m_data.get("valor_texto"),
                    unidad=m_data.get("unidad", analito_obj.unidad_estandar),
                    ref_min=m_data.get("ref_min"),
                    ref_max=m_data.get("ref_max"),
                    ref_texto=m_data.get("ref_texto", analito_obj.ref_texto_defecto),
                    estado_semaforo=m_data.get("estado_semaforo"),
                    nota_clinica=m_data.get("nota_clinica")
                )
                db.add(med)

    # 4. Auditorías de Rango
    for aud_data in data.get("auditorias", []):
        a_cod = aud_data.get("analito_codigo")
        analito_obj = analitos_map.get(a_cod)
        if analito_obj and informes_map:
            ultimo_inf = list(informes_map.values())[-1]
            f_app_raw = aud_data.get("fecha_aplicacion")
            f_app = None
            if f_app_raw:
                try:
                    f_app = datetime.fromisoformat(f_app_raw)
                except Exception:
                    f_app = None

            aud = AuditoriaRango(
                analito_id=analito_obj.id,
                informe_id=ultimo_inf.id,
                rango_anterior=aud_data.get("rango_anterior"),
                rango_nuevo=aud_data.get("rango_nuevo", ""),
                explicacion_ia=aud_data.get("explicacion_ia"),
                aplicado_en_historico=bool(aud_data.get("aplicado_en_historico", False)),
                estado=aud_data.get("estado", "aplicado" if aud_data.get("aplicado_en_historico") else "pendiente"),
                fecha_aplicacion=f_app
            )
            db.add(aud)

    db.commit()

def restore_demo_data(db: Session):
    """Restaura los datos de muestra del modo demostración."""
    from app.seed_data import run_seed
    wipe_database(db)
    run_seed(db)

def backfill_informe_hashes():
    """Calcula y rellena el hash SHA-256 de los informes existentes si tienen archivo PDF en disco."""
    import hashlib
    import logging
    from app.database import SessionLocal
    from app.models import Informe
    from app.config import settings

    logger = logging.getLogger("cac-elrocho")
    db = SessionLocal()
    try:
        informes = db.query(Informe).filter(Informe.sha256.is_(None)).all()
        updated = 0
        for inf in informes:
            if inf.archivo_pdf:
                pdf_path = settings.paths.uploads_dir / inf.archivo_pdf
                if pdf_path.exists():
                    try:
                        with open(pdf_path, "rb") as f:
                            inf.sha256 = hashlib.sha256(f.read()).hexdigest()
                        updated += 1
                    except Exception as e:
                        logger.warning(f"No se pudo calcular hash para {pdf_path}: {e}")
        if updated > 0:
            db.commit()
            logger.info(f"Se actualizaron {updated} informes existentes con su hash SHA-256.")
    except Exception as e:
        logger.error(f"Error en backfill_informe_hashes: {e}")
    finally:
        db.close()
