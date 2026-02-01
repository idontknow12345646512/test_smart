import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
import time
import io
import base64
import requests
from PIL import Image
from gtts import gTTS
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- KONFIGURACE ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="✨", layout="wide")

# Gemini UI Design 2026
st.markdown("""
    <style>
    .stApp { background-color: #0e0e10; color: #e3e3e3; }
    .stChatMessage { padding: 20px 5%; border-bottom: 0px; }
    .stChatInputContainer { padding-bottom: 20px; }
    [data-testid="stSidebar"] { background-color: #171719; border-right: 1px solid #333; }
    .stButton>button { border-radius: 20px; width: 100%; background: #1e1e20; border: 1px solid #3c4043; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZACE ---
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state: st.session_state.messages = []

# API Klíče ze Secrets
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    HF_TOKEN = st.secrets["HF_TOKEN"]
except Exception as e:
    st.error("Chybí API klíče v Secrets!")

# --- FUNKCE ---
def generate_free_image(prompt):
    """Generování obrázků zdarma přes Hugging Face (Flux.1)"""
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        return Image.open(io.BytesIO(response.content))
    except:
        return None

def speak(text):
    """Hlasový výstup 2026 - čistý a automatický"""
    clean_text = text.split("[IMAGE_GEN:")[0].replace("*", "").strip()
    if clean_text:
        tts = gTTS(text=clean_text[:400], lang='cs')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        b64 = base64.b64encode(fp.getvalue()).decode()
        audio_html = f'<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        st.components.v1.html(audio_html, height=0)

# --- SIDEBAR ---
with st.sidebar:
    st.title("✨ S.M.A.R.T. OS")
    st.caption("Verze 2.5 Flash | 2026")
    if st.button("➕ Nový chat"):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    voice_active = st.toggle("🔊 Hlasová odezva", value=True)
    uploaded_file = st.file_uploader("Nahrát soubor (PDF, Docx)", type=["pdf", "docx", "txt"])

# --- HLAVNÍ CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Vstup
user_input = st.chat_input("Napiš mi nebo mě o něco požádej...")

if user_input:
    # Přidání kontextu ze souboru
    file_context = ""
    if uploaded_file:
        file_text = extract_text_from_file(uploaded_file)
        if file_text:
            file_context = f"\n\n[KONTEXT ZE SOUBORU]:\n{file_text[:5000]}"

    # Uložení zprávy uživatele
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Odpověď AI
    with st.chat_message("assistant"):
        with st.spinner("S.M.A.R.T. odpovídá..."):
            try:
                model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SMART_SYSTEM_INSTRUCTION)
                full_prompt = user_input + file_context
                
                # Historie pro model
                history = [{"role": m["role"].replace("assistant", "model"), "parts": [m["content"]]} for m in st.session_state.messages[-6:]]
                
                response = model.generate_content(full_prompt)
                ai_text = response.text
                
                # Zpracování obrázku
                if "[IMAGE_GEN:" in ai_text:
                    img_prompt = ai_text.split("[IMAGE_GEN:")[1].split("]")[0].strip()
                    display_text = ai_text.split("[IMAGE_GEN:")[0].strip()
                    st.markdown(display_text if display_text else "Generuji obrázek...")
                    
                    img = generate_free_image(img_prompt)
                    if img:
                        st.image(img, use_container_width=True)
                        ai_text = display_text + "\n\n(Obrázek vygenerován)"
                    else:
                        st.error("Generování obrázku se nezdařilo.")
                else:
                    st.markdown(ai_text)

                # Hlas
                if voice_active:
                    speak(ai_text)

                # Uložení
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
                
                # Supabase log (volitelně)
                supabase.table("messages").insert({
                    "chat_id": st.session_state.chat_id, 
                    "role": "assistant", 
                    "content": ai_text
                }).execute()

            except Exception as e:
                st.error(f"Chyba: {e}")