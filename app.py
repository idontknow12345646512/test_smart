import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
from datetime import datetime
import time

# --- 1. DESIGN & STYLING ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

# Pomocná funkce pro načtení profilu
def get_profile(uid):
    try:
        res = supabase.table("profiles").select("*").eq("id", uid).execute()
        return res.data[0] if res.data else {}
    except:
        return {}

# --- 2. PŘIPOJENÍ SUPABASE ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 3. AUTH LOGIKA (Přihlášení a Registrace) ---
if "user" not in st.session_state:
    st.title("🤖 S.M.A.R.T. OS: Vítejte")
    t1, t2 = st.tabs(["Přihlásit se", "Vytvořit účet"])
    
    with t1:
        em = st.text_input("Email", key="login_em")
        pw = st.text_input("Heslo", type="password", key="login_pw")
        if st.button("Vstoupit", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                if res.user:
                    st.session_state.user = res.user
                    st.rerun()
            except:
                st.error("Nesprávný email nebo heslo.")
    
    with t2:
        reg_name = st.text_input("Jak vám mám říkat? (Jméno)")
        reg_em = st.text_input("Email", key="reg_em")
        reg_pw = st.text_input("Heslo (min. 6 znaků)", type="password", key="reg_pw")
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                auth_res = supabase.auth.sign_up({"email": reg_em, "password": reg_pw})
                if auth_res.user:
                    supabase.table("profiles").insert({"id": auth_res.user.id, "display_name": reg_name}).execute()
                st.success("Účet vytvořen! Nyní se přihlas v záložce vlevo.")
            except:
                st.error("Chyba při registraci.")
    st.stop()

# --- 4. DATA UŽIVATELE ---
user_id = st.session_state.user.id
profile = get_profile(user_id)
display_name = profile.get("display_name") or st.session_state.user.email
theme = profile.get("theme", "dark")

# CSS pro barvy a šipku
st.markdown(f"""
    <style>
    header[data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}
    .stDeployButton, #MainMenu {{ visibility: hidden; }}
    button[data-testid="stSidebarCollapseIcon"] {{ color: #FFD700 !important; }}
    .stApp {{ 
        background-color: {"#0e1117" if theme == "dark" else "#ffffff"}; 
        color: {"#e0e0e0" if theme == "dark" else "#000000"}; 
    }}
    div[data-testid="stChatInput"] {{ 
        border-radius: 30px !important; 
        background-color: {"#161b22" if theme == "dark" else "#f0f2f6"} !important; 
    }}
    .stButton button {{ border-radius: 10px; }}
    .disclaimer {{ font-size: 0.75rem; color: #5d636d; text-align: center; padding: 20px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 5. SIDEBAR ---
if "chat_id" not in st.session_state: 
    st.session_state.chat_id = str(uuid.uuid4())[:8]

with st.sidebar:
    st.markdown(f"<h1 style='color: #FFD700;'>Ahoj, {display_name}!</h1>", unsafe_allow_html=True)
    
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.session_state.page = "chat"
        st.rerun()
        
    if st.button("⚙️ Nastavení systému", use_container_width=True):
        st.session_state.page = "settings"
        st.rerun()
    
    st.divider()
    st.caption("Tvoje historie")
    try:
        hist = supabase.table("messages").select("chat_id").eq("user_id", user_id).execute()
        u_ids = list(set([c['chat_id'] for c in hist.data]))[-8:]
        for cid in reversed(u_ids):
            if st.button(f"📁 Chat {cid}", key=f"hist_{cid}", use_container_width=True):
                st.session_state.chat_id = cid
                st.session_state.page = "chat"
                st.rerun()
    except: pass

    st.markdown("<br>" * 3, unsafe_allow_html=True)
    if st.button("🚪 Odhlásit se", use_container_width=True):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

# --- 6. LOGIKA STRÁNEK ---

if st.session_state.get("page") == "settings":
    st.title("⚙️ Nastavení S.M.A.R.T. OS")
    t_prof, t_sec, t_ai, t_sys = st.tabs(["👤 Profil", "🔒 Zabezpečení", "🧠 AI", "🖥️ Systém"])
    
    with t_prof:
        c1, c2 = st.columns(2)
        with c1:
            n_dn = st.text_input("Jméno", value=profile.get("display_name", ""))
            n_ln = st.text_input("Příjmení", value=profile.get("last_name", ""))
        with c2:
            bd = profile.get("birth_date") or "2000-01-01"
            n_bd = st.date_input("Datum narození", value=datetime.strptime(bd, "%Y-%m-%d"))
        if st.button("Uložit profil"):
            supabase.table("profiles").update({"display_name": n_dn, "last_name": n_ln, "birth_date": str(n_bd)}).eq("id", user_id).execute()
            st.success("Uloženo!")
            st.rerun()
        st.divider()
        if st.button("🔴 Odstranit účet", type="primary"):
            st.error("Pro smazání účtu kontaktujte podporu nebo použijte admin konzoli.")

    with t_sec:
        st.subheader("Změna e-mailu (OTP)")
        new_email = st.text_input("Nový Email", value=st.session_state.user.email)
        if st.button("Poslat ověřovací kód"):
            supabase.auth.update_user({"email": new_email})
            st.session_state.changing_email = new_email
            st.info(f"Kód byl odeslán na {new_email}")
        
        if st.session_state.get("changing_email"):
            otp = st.text_input("Zadejte 6místný kód z e-mailu")
            if st.button("Potvrdit kód a změnit email"):
                try:
                    supabase.auth.verify_otp({"email": st.session_state.changing_email, "token": otp, "type": "email_change"})
                    st.success("Email změněn!")
                    del st.session_state.changing_email
                    time.sleep(2)
                    st.rerun()
                except: st.error("Neplatný kód.")

    with t_ai:
        st.subheader("Nastavení AI")
        inst = st.text_area("Jak se má AI chovat?", value=profile.get("ai_instructions", ""))
        alen = st.select_slider("Délka odpovědí", options=["Krátká", "Střední", "Dlouhá"], value=profile.get("response_length", "Střední"))
        if st.button("Uložit AI"):
            supabase.table("profiles").update({"ai_instructions": inst, "response_length": alen}).eq("id", user_id).execute()
            st.success("AI nastaveno!")

    with t_sys:
        st.subheader("Vzhled")
        n_th = st.selectbox("Motiv", ["tmavý", "světlý"], index=0 if theme=="dark" else 1)
        if st.button("Změnit motiv"):
            supabase.table("profiles").update({"theme": n_th}).eq("id", user_id).execute()
            st.rerun()

else:
    # --- CHAT REŽIM ---
    mode = st.segmented_control("Režim", ["💬 Chat", "🧠 NotebookLM"], default="💬 Chat")
    
    if mode == "🧠 NotebookLM":
        st.subheader("NotebookLM Nástroje")
        st.info("Zde brzy přibudou tlačítka pro Audio přehled a Kvízy.")
    else:
        # Načtení zpráv
        msgs = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).eq("user_id", user_id).order("created_at").execute().data
        for m in msgs:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        if prompt := st.chat_input("Napište zprávu..."):
            with st.chat_message("user"): st.markdown(prompt)
            supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "user", "content": prompt, "user_id": user_id}).execute()

            genai.configure(api_key=st.secrets["GOOGLE_API_KEY_1"])
            ai_inst = profile.get("ai_instructions") or "Jsi S.M.A.R.T. OS."
            full_inst = f"{ai_inst}\nUživateli říkej {display_name}.\nDélka: {profile.get('response_length', 'Střední')}."
            
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=full_inst)
            gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in msgs]
            
            with st.spinner("Přemýšlím..."):
                resp = model.start_chat(history=gem_hist).send_message(prompt)
                with st.chat_message("assistant"): st.markdown(resp.text)
                supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "assistant", "content": resp.text, "user_id": user_id}).execute()
                st.rerun()

st.markdown("<div class='disclaimer'>S.M.A.R.T. OS 2026. Vaše soukromí je prioritou.</div>", unsafe_allow_html=True)