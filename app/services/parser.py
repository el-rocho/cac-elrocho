import re
from pathlib import Path
from typing import Dict, Any, List

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extrae el texto completo de un documento PDF utilizando PyMuPDF (fitz) o pypdf.
    """
    full_text = []
    
    # Intentar con PyMuPDF
    try:
        import pymupdf as fitz
        doc = fitz.open(str(pdf_path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text.append(f"--- PÁGINA {page_num + 1} ---\n" + page.get_text(sort=True))
        doc.close()
        return "\n".join(full_text)
    except ImportError:
        pass

    # Fallback con pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        for idx, page in enumerate(reader.pages):
            page_text = ""
            try:
                page_text = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                page_text = page.extract_text() or ""
            full_text.append(f"--- PÁGINA {idx + 1} ---\n" + page_text)
        return "\n".join(full_text)
    except Exception as e:
        return f"Error al extraer texto del PDF: {str(e)}"

def extract_metadata_fallback(text: str) -> Dict[str, Any]:
    """
    Heurística de extracción rápida de fecha, laboratorio y facultativo en caso de no disponer de LLM.
    """
    metadata = {
        "laboratorio": "Desconocido",
        "fecha": "",
        "facultativo": "No especificado"
    }
    
    if "RECOLETAS" in text.upper():
        metadata["laboratorio"] = "Hospital Recoletas Cuenca"
    elif "MEGALAB" in text.upper() or "CLINICA ALMED" in text.upper():
        metadata["laboratorio"] = "Megalab"
    elif "QFISIO" in text.upper():
        metadata["laboratorio"] = "Laboratorio Qfisio"

    # Buscar Doctor / Facultativo (evitando tipos de consulta)
    doc_matches = re.findall(r"(?:Doctor|Facultativo|Médico|Dr\.|Dra\.)\s*:\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s,.-]+)", text, re.IGNORECASE)
    if doc_matches:
        cand = doc_matches[0].strip()
        cand = re.split(r'(\n|\r|Procedencia|Entidad|F\.|DNI|Nacimiento|Pasaporte|Fecha)', cand, flags=re.IGNORECASE)[0].strip()
        cand = cand.strip(' ,.-')
        if len(cand) > 3 and not any(k in cand.lower() for k in ['control', 'seguimiento', 'revision', 'revisión', 'rutinario', 'anual']):
            metadata["facultativo"] = cand

    # Buscar fechas en formato DD/MM/AAAA o DD-MM-AAAA
    date_matches = re.findall(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", text)
    if date_matches:
        d, m, y = date_matches[0]
        metadata["fecha"] = f"{y}-{int(m):02d}-{int(d):02d}"

    return metadata
