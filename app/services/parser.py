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
            full_text.append(f"--- PÁGINA {page_num + 1} ---\n" + page.get_text())
        doc.close()
        return "\n".join(full_text)
    except ImportError:
        pass

    # Fallback con pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        for idx, page in enumerate(reader.pages):
            full_text.append(f"--- PÁGINA {idx + 1} ---\n" + (page.extract_text() or ""))
        return "\n".join(full_text)
    except Exception as e:
        return f"Error al extraer texto del PDF: {str(e)}"

def extract_metadata_fallback(text: str) -> Dict[str, Any]:
    """
    Heurística de extracción rápida de fecha y laboratorio en caso de no disponer de LLM.
    """
    metadata = {
        "laboratorio": "Desconocido",
        "fecha": "",
        "facultativo": "No especificado"
    }
    
    if "RECOLETAS" in text.upper():
        metadata["laboratorio"] = "Hospital Recoletas"
    elif "MEGALAB" in text.upper():
        metadata["laboratorio"] = "Laboratorio Megalab"

    # Buscar fechas en formato DD/MM/AAAA o DD-MM-AAAA
    date_matches = re.findall(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b", text)
    if date_matches:
        d, m, y = date_matches[0]
        metadata["fecha"] = f"{y}-{int(m):02d}-{int(d):02d}"

    return metadata
