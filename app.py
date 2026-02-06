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

# Inicializace Supabase
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- AUTH LOGIKA (ÚČTY) ---
if "user" not in st.session_state:
    st.session_state.user = None

def login_ui():
    st.title("🧬 S.M.A.R.T. Login")
    tab1, tab2 = st.tabs(["Přihlášení", "Registrace"])
    
    with tab1:
        email = st.text_input("E-mail", key="login_email")
        password = st.text_input("Heslo", type="password", key="login_pass")
        if st.button("Vstoupit do OS"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error("Chybné údaje nebo uživatel neexistuje.")

    with tab2:
        reg_email = st.text_input("E-mail", key="reg_email")
        reg_password = st.text_input("Heslo (min. 6 znaků)", type="password", key="reg_pass")
        if st.button("Vytvořit účet"):
            try:
                supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                st.success("Registrace úspěšná! Nyní se přihlaste.")
            except Exception as e:
                st.error(f"Chyba registrace: {e}")

# Pokud není uživatel přihlášen, zobrazíme jen login a ukončíme skript
if st.session_state.user is None:
    login_ui()
    st.stop()

# --- HLAVNÍ APLIKACE (Po přihlášení) ---

# Funkce pro klíče
def get_random_key():
    keys = [st.secrets[k] for k in st.secrets.keys() if "GOOGLE_API_KEY_" in k]
    return random.choice(keys) if keys else st.secrets.get("GOOGLE_API_KEY")

# Session state pro zprávy
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Načtení historie z DB pro daného uživatele
    res = supabase.table("messages").select("*").eq("user_id", st.session_state.user.id).order("created_at").execute()
    st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in res.data]

# Sidebar s odhlášením
with st.sidebar:
    st.write(f"👤 **{st.session_state.user.email}**")
    if st.button("Odhlásit se"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.messages = []
        st.rerun()
    st.divider()
    voice_on = st.toggle("🔊 Hlas", value=True)

# --- CHAT ENGINE ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Napiš S.M.A.R.T.ovi...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        full_res = ""
        placeholder = st.empty()
        
        # Rotace a Generování
        genai.configure(api_key=get_random_key())
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SMART_SYSTEM_INSTRUCTION)
        
        try:
            response = model.generate_content(user_input, stream=True)
            for chunk in response:
                full_res += chunk.text
                placeholder.markdown(full_res + "▌")
            placeholder.markdown(full_res)
            
            # Uložení do historie a DB s vazbou na uživatele
            st.session_state.messages.append({"role": "assistant", "content": full_res})
            supabase.table("messages").insert({
                "user_id": st.session_state.user.id,
                "chat_id": "current", 
                "role": "assistant",
                "content": full_res
            }).execute()
            
            # Hlasový výstup (volitelně)
            # speak(full_res) - funkce z minulého kódu
            
        except Exception as e:
            st.error(f"Chyba jádra: {e}")