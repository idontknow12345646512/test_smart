import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
from datetime import datetime

# --- 1. DESIGN & ŠIPKA (Vše podle tvého nákresu) ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

# Pomocná funkce pro načtení profilu
def get_profile(uid):
    res = supabase.table("profiles").select("*").eq("id", uid).execute()
    return res.data[0] if res.data else {}

# --- 2. PŘIPOJENÍ SUPABASE ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 3. AUTH LOGIKA ---
if "user" not in st.session_state:
    st.title("🤖 S.M.A.R.T. OS: Přihlášení")
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
        reg_name = st.text_input("Jak vám mám říkat? (Display Name)")
        reg_em = st.text_input("Email", key="reg_em")
        reg_pw = st.text_input("Heslo (min. 6 znaků)", type="password", key="reg_pw")
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                auth_res = supabase.auth.sign_up({"email": reg_em, "password": reg_pw})
                if auth_res.user:
                    # Vytvoření profilu po registraci
                    supabase.table("profiles").insert({
                        "id": auth_res.user.id, 
                        "display_name": reg_name
                    }).execute()
                st.success("Účet vytvořen! Nyní se přihlas v záložce vlevo.")
            except:
                st.error("Chyba při registraci.")
    st.stop()

# --- 4. DATA UŽIVATELE ---
user_id = st.session_state.user.id
profile = get_profile(user_id)
display_name = profile.get("display_name") or st.session_state.user.email
theme = profile.get("theme", "dark")

# CSS pro dynamický motiv a UI
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
        border: 1px solid #333 !important;
    }}
    .disclaimer {{ font-size: 0.75rem; color: #5d636d; text-align: center; padding: 20px; }}
    .stButton button {{ border-radius: 10px; }}
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
        hist_res = supabase.table("messages").select("chat_id").eq("user_id", user_id).execute()
        u_ids = list(set([c['chat_id'] for c in hist_res.data]))[-8:]
        for cid in reversed(u_ids):
            if st.button(f"📁 Chat {cid}", key=f"hist_{cid}", use_container_width=True):
                st.session_state.chat_id = cid
                st.session_state.page = "chat"
                st.rerun()
    except:
        pass

    st.markdown("<br>" * 3, unsafe_allow_html=True)
    if st.button("🚪 Odhlásit se", use_container_width=True):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

# --- 6. LOGIKA STRÁNEK ---

# --- STRÁNKA: NASTAVENÍ ---
if st.session_state.get("page") == "settings":
    st.title("⚙️ Nastavení S.M.A.R.T. OS")
    t_prof, t_sec, t_ai, t_sys = st.tabs(["👤 Profil", "🔒 Zabezpečení", "🧠 AI Nastavení", "🖥️ Systém"])
    
    with t_prof:
        c1, c2 = st.columns(2)
        with c1:
            new_dn = st.text_input("Jméno (Display Name)", value=profile.get("display_name", ""))
            new_ln = st.text_input("Příjmení", value=profile.get("last_name", ""))
        with c2:
            bday = profile.get("birth_date") or "2000-01-01"
            new_bd = st.date_input("Datum narození", value=datetime.strptime(bday, "%Y-%m-%d"))
        
        if st.button("Uložit změny profilu"):
            supabase.table("profiles").update({
                "display_name": new_dn, "last_name": new_ln, "birth_date": str(new_bd)
            }).eq("id", user_id).execute()
            st.success("Profil aktualizován!")
            st.rerun()
            
        st.divider()
        if st.button("🔴 Odstranit účet a všechna data", type="primary"):
            st.warning("Tato akce smaže všechny vaše chaty a profil.")
            # Zde by byla logika pro smazání, vyžaduje potvrzení

    with t_sec:
        st.subheader("Zabezpečení účtu")
        new_em = st.text_input("Změnit Email", value=st.session_state.user.email)
        if st.button("Aktualizovat email"):
            supabase.auth.update_user({"email": new_em})
            st.info("Ověřovací odkaz byl odeslán na nový email.")
            
        st.divider()
        st.subheader("Dvoufázové ověření (2FA)")
        use_2fa = st.toggle("Zapnout 2FA", help="Zvýší bezpečnost při přihlašování.")
        if use_2fa:
            st.info("Funkce 2FA vyžaduje propojení s aplikací Authenticator.")

    with t_ai:
        st.subheader("Konfigurace AI asistenta")
        ai_inst = st.text_area("Jak se má AI chovat?", value=profile.get("ai_instructions", ""), 
                               placeholder="Např. Jsi přísný učitel matematiky. Odpovídej stručně.")
        
        ai_len = st.select_slider("Délka odpovědí", options=["Krátká", "Střední", "Dlouhá"], 
                                  value=profile.get("response_length", "Střední"))
        
        st.caption("Příklady chování:")
        st.code("- Mluv jako pirát.\n- Vysvětluj vše jako pětiletému dítěti.\n- Piš pouze v odrážkách.")
        
        if st.button("Uložit AI nastavení"):
            supabase.table("profiles").update({
                "ai_instructions": ai_inst, "response_length": ai_len
            }).eq("id", user_id).execute()
            st.success("AI nastavení uloženo!")

    with t_sys:
        st.subheader("Vzhled systému")
        new_th = st.selectbox("Režim zobrazení", ["tmavý", "světlý"], 
                              index=0 if theme == "dark" else 1)
        if st.button("Použít motiv"):
            supabase.table("profiles").update({"theme": new_th}).eq("id", user_id).execute()
            st.rerun()

# --- STRÁNKA: CHAT / NOTEBOOK ---
else:
    mode = st.segmented_control("Režim", ["💬 Chat", "🧠 NotebookLM"], default="💬 Chat")

    if mode == "🧠 NotebookLM":
        st.subheader("Analýza dokumentů")
        st.info("Tady budeme přidávat tlačítka pro Audio, Kvízy a Mapy z tvých souborů.")
    else:
        # KLASICKÝ CHAT
        st.caption(f"Aktuální vlákno: {st.session_state.chat_id}")
        
        messages = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).eq("user_id", user_id).order("created_at").execute().data
        
        for m in messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        col_up, col_chat = st.columns([1, 10])
        with col_up:
            up_file = st.file_uploader("➕", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if prompt := st.chat_input("Zeptejte se na cokoliv..."):
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Uložení zprávy uživatele
            supabase.table("messages").insert({
                "chat_id": st.session_state.chat_id, "role": "user", "content": prompt, "user_id": user_id
            }).execute()

            # AI Logika s instrukcemi z profilu
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY_1"])
            
            custom_inst = profile.get("ai_instructions") or "Mluv vždy česky a buď užitečný."
            full_system_inst = f"{custom_inst}\nUživateli říkej: {display_name}.\nDélka odpovědi: {profile.get('response_length', 'Střední')}."
            
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=full_system_inst)
            
            gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in messages]
            chat_session = model.start_chat(history=gem_hist)
            
            with st.spinner("S.M.A.R.T. odpovídá..."):
                response = chat_session.send_message(prompt)
                ai_text = response.text

            with st.chat_message("assistant"):
                st.markdown(ai_text)
            
            # Uložení zprávy asistenta
            supabase.table("messages").insert({
                "chat_id": st.session_state.chat_id, "role": "assistant", "content": ai_text, "user_id": user_id
            }).execute()
            st.rerun()

st.markdown("<div class='disclaimer'>S.M.A.R.T. OS může dělat chyby. Informace jsou soukromé.</div>", unsafe_allow_html=True)