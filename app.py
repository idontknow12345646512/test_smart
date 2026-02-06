import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
from datetime import datetime
import time
import random
from PIL import Image
import io
import base64
from gtts import gTTS
from duckduckgo_search import DDGS
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. KONFIGURACE A CYBER DESIGN ---
st.set_page_config(page_title="S.M.A.R.T. OS 2026", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at 50% 50%, #0d0d1a 0%, #050505 100%); color: #e0e0ff; }
    
    /* FIX ŠIPKY SIDEBARU - Aby byla vždy vidět neonově modře */
    button[kind="header"] {
        color: #00f2ff !important;
        background-color: rgba(0, 242, 255, 0.15) !important;
        border: 1px solid #00f2ff !important;
        border-radius: 50%;
        z-index: 1000;
    }

    [data-testid="stSidebar"] {
        background-color: rgba(10, 10, 20, 0.9) !important;
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(0, 242, 255, 0.2);
    }

    .stChatMessage {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(0, 242, 255, 0.1);
        border-radius: 20px !important;
    }
    
    #MainMenu, footer, header { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# Inicializace Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 2. POMOCNÉ FUNKCE (Rotace, Hlas, Obrázky) ---
def rotate_api_key():
    keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    valid_keys = [k for k in keys if k]
    return random.choice(valid_keys) if valid_keys else st.secrets.get("GOOGLE_API_KEY")

def generate_free_image(prompt):
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}
    try:
        res = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=15)
        return Image.open(io.BytesIO(res.content))
    except: return None

def speak(text):
    try:
        clean_text = text.split("[IMAGE_GEN:")[0].replace("*", "").strip()
        tts = gTTS(text=clean_text[:300], lang='cs')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        b64 = base64.b64encode(fp.getvalue()).decode()
        st.components.v1.html(f'<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', height=0)
    except: pass

# --- 3. STRÁNKA PŘIHLÁŠENÍ ---
def show_login_page():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #00f2ff;'>🧬 S.M.A.R.T. OS</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔐 Vstoupit", "🧬 Nová Identita"])
        with tab1:
            email = st.text_input("Email")
            password = st.text_input("Heslo", type="password")
            if st.button("Inicializovat spojení", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Přístup zamítnut.")
        with tab2:
            r_email = st.text_input("Nový Email")
            r_pass = st.text_input("Nové Heslo", type="password")
            if st.button("Vytvořit účet", use_container_width=True):
                try:
                    supabase.auth.sign_up({"email": r_email, "password": r_pass})
                    st.success("Registrace OK, potvrďte email!")
                except Exception as e: st.error(f"Chyba: {e}")

# --- 4. HLAVNÍ APLIKACE ---
def show_main_app():
    if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]
    if "messages" not in st.session_state: st.session_state.messages = []

    # SIDEBAR
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user.email.split('@')[0]}")
        st.caption("🟢 Systém Online | Gemini 2.5 Flash")
        st.divider()
        voice_on = st.toggle("🔊 Hlasová syntéza", value=True)
        web_on = st.toggle("🌐 Webový průzkum", value=True)
        uploaded_file = st.file_uploader("Nahrát soubor", type=["pdf", "docx", "txt"])
        
        st.divider()
        if st.button("➕ Nová relace", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_id = str(uuid.uuid4())[:8]
            st.rerun()
        
        if st.button("🚪 Odhlásit", type="secondary", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    # CHAT AREA
    st.title("💬 S.M.A.R.T. Interface")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Zadejte příkaz...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            full_res = ""
            placeholder = st.empty()
            
            # Web Search Retrieval
            web_context = ""
            if web_on:
                with st.spinner("🔍 Prohledávám sítě..."):
                    try:
                        with DDGS() as ddgs:
                            results = list(ddgs.text(user_input, max_results=3))
                            web_context = "\n".join([f"Zdroj: {r['body']}" for r in results])
                    except: pass

            # Konfigurace AI
            genai.configure(api_key=rotate_api_key())
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SMART_SYSTEM_INSTRUCTION)
            
            file_ctx = extract_text_from_file(uploaded_file) if uploaded_file else ""
            prompt = f"SOUBOR: {file_ctx}\nWEB: {web_context}\nDOTAZ: {user_input}"

            try:
                response = model.generate_content(prompt, stream=True)
                for chunk in response:
                    full_res += chunk.text
                    placeholder.markdown(full_res + "▌")
                placeholder.markdown(full_res)

                # Speciální funkce (Obrázky)
                if "[IMAGE_GEN:" in full_res:
                    img_p = full_res.split("[IMAGE_GEN:")[1].split("]")[0].strip()
                    with st.spinner("🎨 Generuji vizuál..."):
                        img = generate_free_image(img_p)
                        if img: st.image(img, use_container_width=True)

                if voice_on: speak(full_res)

                # DB Zápis
                supabase.table("messages").insert({
                    "user_id": st.session_state.user.id,
                    "chat_id": st.session_state.chat_id,
                    "role": "assistant",
                    "content": full_res
                }).execute()
                
                st.session_state.messages.append({"role": "assistant", "content": full_res})
            except Exception as e:
                st.error(f"Chyba jádra: {e}")

# --- SPOUŠTĚČ ---
if "user" not in st.session_state or st.session_state.user is None:
    show_login_page()
else:
    show_main_app()