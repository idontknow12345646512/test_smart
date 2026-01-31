import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
from datetime import datetime
import time
import random
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

# --- 2. PŘIPOJENÍ SUPABASE ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Chyba připojení k databázi: {e}")
    st.stop()

# --- 3. POMOCNÉ FUNKCE ---

def init_session():
    """Obnoví session Supabase."""
    if "session" in st.session_state:
        try:
            supabase.auth.set_session(
                st.session_state.session.access_token, 
                st.session_state.session.refresh_token
            )
        except Exception:
            st.warning("Relace vypršela. Přihlaste se prosím znovu.")
            if "user" in st.session_state: del st.session_state.user
            if "session" in st.session_state: del st.session_state.session
            st.rerun()

def get_profile(uid):
    """Načte data z tabulky profiles."""
    try:
        res = supabase.table("profiles").select("*").eq("id", uid).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {"display_name": "Uživatel", "theme": "dark", "ai_instructions": "", "response_length": "Střední"}

def rotate_api_key():
    """Náhodně vybere jeden z 10 klíčů pro rozložení zátěže."""
    keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    valid_keys = [k for k in keys if k]
    if not valid_keys:
        st.error("Chybí API klíče v secrets!")
        st.stop()
    return random.choice(valid_keys)

# --- 4. AUTENTIZACE (2FA LOGIKA - ČISTÉ OTP) ---

if "user" not in st.session_state:
    st.title("🤖 S.M.A.R.T. OS")
    
    tab1, tab2 = st.tabs(["🔐 Přihlášení", "✨ Vytvořit účet"])
    
    with tab1:
        if "step_2fa" not in st.session_state:
            email = st.text_input("Email", key="log_email")
            password = st.text_input("Heslo", type="password", key="log_pass")
            
            if st.button("Pokračovat", use_container_width=True):
                try:
                    # 1. Ověření hesla
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if res.user:
                        # 2. Požadavek na OTP (v šabloně v Supabase musí být {{ .Token }})
                        supabase.auth.sign_in_with_otp({"email": email})
                        st.session_state.step_2fa = True
                        st.session_state.temp_email = email
                        st.rerun()
                except Exception:
                    st.error("Nesprávný email nebo heslo.")
        else:
            # 3. Zadání kódu přímo v aplikaci
            st.info(f"🛡️ Do e-mailu {st.session_state.temp_email} vám přišel 6místný kód.")
            otp_code = st.text_input("Zadejte kód", placeholder="123456", max_chars=6)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Ověřit a vstoupit", type="primary", use_container_width=True):
                    try:
                        # Verifikace pomocí kódu (Tokenu)
                        res = supabase.auth.verify_otp({
                            "email": st.session_state.temp_email,
                            "token": otp_code,
                            "type": "email"
                        })
                        if res.user:
                            st.session_state.user = res.user
                            st.session_state.session = res.session
                            del st.session_state.step_2fa
                            st.rerun()
                    except:
                        st.error("Neplatný nebo vypršený kód.")
            with c2:
                if st.button("Zpět", use_container_width=True):
                    del st.session_state.step_2fa
                    st.rerun()

    with tab2:
        reg_name = st.text_input("Jak vám mám říkat?")
        reg_email = st.text_input("Registrační Email")
        reg_pass = st.text_input("Heslo", type="password")
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                supabase.auth.sign_up({
                    "email": reg_email, 
                    "password": reg_pass,
                    "options": {"data": {"display_name": reg_name}}
                })
                st.success("Účet vytvořen! Nyní se přihlaste.")
            except Exception as e:
                st.error(f"Chyba: {e}")
    st.stop()

# Inicializace session pro přihlášené
init_session()
user_id = st.session_state.user.id
profile = get_profile(user_id)
display_name = profile.get("display_name") or "Uživatel"
current_theme = profile.get("theme", "dark")

# --- 5. STYLOVÁNÍ ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: {'#0e1117' if current_theme == 'dark' else '#ffffff'}; }}
    [data-testid="stSidebar"] {{ background-color: {'#161b22' if current_theme == 'dark' else '#f0f2f6'}; }}
    </style>
""", unsafe_allow_html=True)

# --- 6. SIDEBAR ---
with st.sidebar:
    avatar_url = f"https://api.dicebear.com/7.x/bottts/svg?seed={display_name}"
    st.image(avatar_url, width=100)
    st.markdown(f"### {display_name}")
    st.caption("🛡️ Zabezpečeno 2FA | Gemini 2.0 Flash")
    
    st.divider()
    
    if st.button("💬 Chat", use_container_width=True):
        st.session_state.page = "chat"
        st.rerun()
        
    if st.button("⚙️ Nastavení", use_container_width=True):
        st.session_state.page = "settings"
        st.rerun()

    st.divider()
    st.subheader("📁 Dokumenty k analýze")
    uploaded_file = st.file_uploader("Nahrajte soubor", type=["pdf", "docx", "txt"])
    doc_context = ""
    if uploaded_file:
        doc_context = extract_text_from_file(uploaded_file)
        if doc_context: st.success("Soubor připraven!")

    st.divider()
    if st.button("🚪 Odhlásit se", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# --- 7. HLAVNÍ OBSAH ---

if st.session_state.get("page") == "settings":
    st.title("⚙️ Nastavení S.M.A.R.T. OS")
    t_prof, t_ai, t_sys = st.tabs(["👤 Profil", "🧠 AI Možnosti", "🎨 Vzhled"])
    
    with t_prof:
        new_dn = st.text_input("Zobrazované jméno", value=display_name)
        if st.button("Uložit jméno"):
            supabase.table("profiles").update({"display_name": new_dn}).eq("id", user_id).execute()
            st.rerun()
            
    with t_ai:
        ai_inst = st.text_area("Vlastní instrukce pro AI", value=profile.get("ai_instructions", ""))
        res_len = st.select_slider("Délka odpovědí", options=["Krátká", "Střední", "Dlouhá"], value=profile.get("response_length", "Střední"))
        if st.button("Uložit nastavení AI"):
            supabase.table("profiles").update({"ai_instructions": ai_inst, "response_length": res_len}).eq("id", user_id).execute()
            st.success("Nastavení uloženo.")

    with t_sys:
        theme = st.radio("Motiv", ["Tmavý", "Světlý"], index=0 if current_theme == "dark" else 1)
        if st.button("Změnit vzhled"):
            supabase.table("profiles").update({"theme": "dark" if theme == "Tmavý" else "light"}).eq("id", user_id).execute()
            st.rerun()

else:
    if "chat_id" not in st.session_state:
        st.session_state.chat_id = str(uuid.uuid4())[:8]

    st.title("💬 S.M.A.R.T. Chat")
    
    try:
        msgs = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).order("created_at").execute().data
    except: msgs = []

    for m in msgs:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Napište zprávu..."):
        st.chat_message("user").markdown(prompt)
        supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "user", "content": prompt, "user_id": user_id}).execute()

        genai.configure(api_key=rotate_api_key())
        
        len_map = {"Krátká": "stručný", "Střední": "vyvážený", "Dlouhá": "velmi detailní"}
        len_prompt = len_map.get(profile.get("response_length"), "střední")

        final_system_prompt = f"""
        {SMART_SYSTEM_INSTRUCTION}
        Uživatele oslovuj: {display_name}.
        Instrukce uživatele: {profile.get('ai_instructions', 'Buď nápomocný.')}
        Požadovaný styl: {len_prompt}.
        """
        
        if doc_context:
            final_system_prompt += f"\n\nKONTEXT Z NAHRANÉHO SOUBORU (Prioritizuj toto):\n{doc_context[:20000]}"

        # Model Gemini 2.5 Flash
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=final_system_prompt)
        
        gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in msgs]
        
        with st.spinner("S.M.A.R.T. OS přemýšlí..."):
            try:
                chat = model.start_chat(history=gem_hist)
                response = chat.send_message(prompt)
                ai_text = response.text
            except Exception as e:
                ai_text = f"Omlouvám se, došlo k chybě AI: {e}"

        with st.chat_message("assistant"): st.markdown(ai_text)
        supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "assistant", "content": ai_text, "user_id": user_id}).execute()
        st.rerun()