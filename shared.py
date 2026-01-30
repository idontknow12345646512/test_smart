# shared.py
import io
import pypdf
from docx import Document

def extract_text_from_file(uploaded_file):
    """Extrahuje text z PDF, DOCX nebo TXT."""
    text = ""
    try:
        if uploaded_file.type == "application/pdf":
            reader = pypdf.PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif uploaded_file.type == "text/plain":
            text = uploaded_file.getvalue().decode("utf-8")
        else:
            return None # Nepodporovaný formát pro textovou analýzu, zpracuje Gemini jako obrázek/data
    except Exception as e:
        return f"Chyba při čtení souboru: {e}"
    
    return text

# Globální nastavení pro systémové instrukce
SMART_SYSTEM_INSTRUCTION = """
Jsi S.M.A.R.T. OS (Study Material & Assistant for Research and Teaching). 
Tvá osobnost:
1. Jsi maximálně UPŘÍMNÝ. Pokud něco nevíš nebo v textu informace není, řekni to. Nevymýšlej si fakta.
2. Jsi EMPATICKÝ a podpůrný studijní partner.
3. Vždy mluv ČESKY (pokud uživatel nepožádá jinak).

Tvé úkoly:
- Pokud uživatel nahraje soubor, tvé odpovědi musí vycházet PRIMÁRNĚ z tohoto souboru.
- Formátuj výstupy přehledně (Markdown, odrážky, tučné písmo).
"""
