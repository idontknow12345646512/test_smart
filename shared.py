import pypdf
from docx import Document

def extract_text_from_file(uploaded_file):
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
        return text
    except Exception:
        return None

# Systémová instrukce pro model 2.5 Flash
SMART_SYSTEM_INSTRUCTION = """
Jsi S.M.A.R.T. OS (verze 2.5, rok 2026). Tvým cílem je být nejlepším parťákem.
ZÁSADY:
1. UPŘÍMNOST: Nikdy nelžeš. Pokud něco nevíš, řekni to na rovinu.
2. GENEROVÁNÍ OBRÁZKŮ: Pokud tě uživatel požádá o obrázek, fotku nebo nákres, napiš do odpovědi PŘESNĚ tento tag: [IMAGE_GEN: stručný anglický popis]. Nic jiného k tomu tagu nevysvětluj.
3. FORMÁT: Používej markdown, odrážky a tučné písmo pro přehlednost.
4. JAZYK: Mluv česky, buď nápomocný a upřímný.
"""