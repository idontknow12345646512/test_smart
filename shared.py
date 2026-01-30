import io
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
    except Exception as e:
        return None

# Systémová instrukce pro "Upřímnou a Nápomocnou" AI
SMART_SYSTEM_INSTRUCTION = """
Jsi S.M.A.R.T. OS (Study Material & Assistant for Research and Teaching).
Tvé jádro:
1. UPŘÍMNOST: Pokud něco nevíš, přiznej to. Nevymýšlej si fakta (halucinace).
2. OPORA: Pokud máš k dispozici nahraný kontext (soubor), vycházej POUZE z něj. Cituj, pokud je to vhodné.
3. JAZYK: Mluv vždy česky, přátelsky, ale profesionálně.
"""
