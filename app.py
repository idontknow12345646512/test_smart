import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
import random
import io
import base64
import requests
from PIL import Image
from gtts import gTTS
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- KONFIGURACE ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="✨", layout="wide")

# CSS pro Gemini UI 2026 a Login Tlačítka
st.markdown("""
    <style>
    .stApp { background-color: #0e0e10; color: #e3e3e3; }
    [data-testid="stSidebar"] { background-color: #171719; border-right: 1px solid #333; }
    .auth-status { text-align: right; padding: 10px; color: #8ab4f8; font-weight: bold; }
    .stChatInputContainer { padding-bottom: 20px; }
    #MainMenu, footer, header { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# Inicializace Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- SESSION STATE ---
if "messages" not in st.session_state: st.session_state.messages = []
if "user" not in st.session_state: st.session_state.user = None
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]

# --- POMOCNÉ FUNKCE ---
def get_random_key():
    keys = [st.secrets[k] for k in st.secrets.keys() if "GOOGLE_API_KEY_" in k]
    return random.choice(keys) if keys else st.secrets.get("GOOGLE_API_KEY")

def speak(text):
    try:
        clean_text = text.split("[IMAGE_GEN:")[0].replace("*", "").strip()
        tts = gTTS(text=clean_text[:250], lang='cs')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        b64 = base64.b64encode(fp.getvalue()).decode()
        st.components.v1.html(f'<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', height=0)
    except: pass

# --- SIDEBAR (AUTH & SETTINGS) ---
with st.sidebar:
    st.title("✨ S.M.A.R.T. OS")
    
    # LOGIN / REGISTER SEKCE
    if st.session_state.user is None:
        st.subheader("Přihlášení")
        email = st.text_input("E-mail")
        password = st.text_input("Heslo", type="password")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Log In", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Chyba")
        with col2:
            if st.button("Sign Up", use_container_width=True):
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Ověřte mail!")
                except: st.error("Chyba")
    else:
        st.success(f"Přihlášen: {st.session_state.user.email}")
        if st.button("Odhlásit se", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    st.divider()
    voice_on = st.toggle("🔊 Hlasová odezva", value=True)
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- CHAT INTERFACE ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Vstup
user_input = st.chat_input("Zeptej se na cokoliv...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        full_response = ""
        resp_placeholder = st.empty()
        
        # Rotace klíčů
        genai.configure(api_key=get_random_key())
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SMART_SYSTEM_INSTRUCTION)
        
        try:
            response = model.generate_content(user_input, stream=True)
            for chunk in response:
                full_response += chunk.text
                resp_placeholder.markdown(full_response + "▌")
            resp_placeholder.markdown(full_response)
            
            # Pokud je uživatel přihlášen, uložíme do DB
            if st.session_state.user:
                try:
                    supabase.table("messages").insert({
                        "user_id": st.session_state.user.id,
                        "chat_id": st.session_state.chat_id,
                        "role": "assistant",
                        "content": full_response
                    }).execute()
                except: pass
            
            if voice_on: speak(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error("Model je přetížen, zkuste to znovu.")