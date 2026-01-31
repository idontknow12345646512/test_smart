import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
import time

# --- 1. DESIGN & ŠIPKA (Vše podle tvého nákresu) ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    /* Průhledný header aby zůstala vidět šipka sidebaru */
    header[data-testid="stHeader"] { background: rgba(0,0,0,0) !important; }
    .stDeployButton, #MainMenu { visibility: hidden; }
    
    /* Žlutá šipka sidebaru */
    button[data-testid="stSidebarCollapseIcon"] { color: #FFD700 !important; }
    
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    
    /* Zaoblený chat input (kapsle) */
    div[data-testid="stChatInput"] { 
        border-radius: 30px !important; 
        background-color: #161b22 !important; 
        border: 1px solid #333 !important;
    }
    
    /* Disclaimer dole */
    .disclaimer { font-size: 0.75rem; color: #5d636d; text-align: center; padding: 20px; }
    
    /* Stylování tlačítek v sidebaru */
    .stButton button { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. PŘIPOJENÍ SUPABASE ---
# Ujisti se, že máš v Secrets SUPABASE_URL a SUPABASE_KEY (anon)
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 3. OPRAVENÁ AUTH LOGIKA (Přihlášení napoprvé) ---
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
                    st.rerun() # Okamžitý restart do aplikace
            except:
                st.error("Nesprávný email nebo heslo.")
    
    with t2:
        reg_em = st.text_input("Nový Email", key="reg_em")
        reg_pw = st.text_input("Nové Heslo (min. 6 znaků)", type="password", key="reg_pw")
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                # Nezapomeň mít v Supabase vypnuté 'Confirm email'
                supabase.auth.sign_up({"email": reg_em, "password": reg_pw})
                st.success("Účet vytvořen! Nyní se přihlas v záložce vlevo.")
            except:
                st.error("Chyba při registraci. Email už může existovat.")
    st.stop()

# --- 4. NASTAVENÍ PRO PŘIHLÁŠENÉHO UŽIVATELE ---
user_id = st.session_state.user.id
if "chat_id" not in st.session_state: 
    st.session_state.chat_id = str(uuid.uuid4())[:8]

def save_msg(cid, role, content):
    supabase.table("messages").insert({
        "chat_id": cid, 
        "role": role, 
        "content": content, 
        "user_id": user_id
    }).execute()

# --- 5. SIDEBAR (Historie a Odhlášení) ---
with st.sidebar:
    st.markdown("<h1 style='color: #FFD700;'>S.M.A.R.T.</h1>", unsafe_allow_html=True)
    st.caption(f"Přihlášen jako: {st.session_state.user.email}")
    
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.rerun()
    
    st.divider()
    st.caption("Tvoje historie")
    
    # Načtení historie jen pro aktuálního uživatele
    try:
        hist_res = supabase.table("messages").select("chat_id").eq("user_id", user_id).execute()
        u_ids = list(set([c['chat_id'] for c in hist_res.data]))[-8:]
        for cid in reversed(u_ids):
            if st.button(f"📁 Chat {cid}", key=f"hist_{cid}", use_container_width=True):
                st.session_state.chat_id = cid
                st.rerun()
    except:
        pass

    st.markdown("<br>" * 5, unsafe_allow_html=True)
    if st.button("🚪 Odhlásit se", use_container_width=True):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

# --- 6. HLAVNÍ REŽIMY (Chat / Notebook) ---
mode = st.segmented_control("Režim", ["💬 Chat", "🧠 NotebookLM"], default="💬 Chat")

if mode == "🧠 NotebookLM":
    st.subheader("Analýza dokumentů")
    st.info("Tady budeme přidávat tlačítka pro Audio, Kvízy a Mapy z tvých souborů.")
    # Zde brzy přidáme tvé specifické Notebook nástroje
else:
    # KLASICKÝ CHAT
    st.caption(f"Aktuální vlákno: {st.session_state.chat_id}")
    
    # Načtení zpráv z DB
    messages = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).eq("user_id", user_id).order("created_at").execute().data
    
    for m in messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # Input zóna s Pluskem
    col_up, col_chat = st.columns([1, 10])
    with col_up:
        up_file = st.file_uploader("➕", type=["pdf", "txt", "docx"], label_visibility="collapsed")
    
    if prompt := st.chat_input("Zeptej se na cokoliv..."):
        # 1. Uživatel
        with st.chat_message("user"):
            st.markdown(prompt)
        save_msg(st.session_state.chat_id, "user", prompt)

        # 2. AI (Gemini 1.5 Flash)
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY_1"])
        model = genai.GenerativeModel("gemini-1.5-flash", 
                                      system_instruction="Jsi S.M.A.R.T. OS. Mluv vždy česky a buď užitečný.")
        
        # Sestavení paměti
        gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in messages]
        chat_session = model.start_chat(history=gem_hist)
        
        with st.spinner("S.M.A.R.T. odpovídá..."):
            response = chat_session.send_message(prompt)
            ai_text = response.text

        # 3. Asistent
        with st.chat_message("assistant"):
            st.markdown(ai_text)
        save_msg(st.session_state.chat_id, "assistant", ai_text)
        st.rerun()

st.markdown("<div class='disclaimer'>S.M.A.R.T. OS může dělat chyby. Informace jsou soukromé.</div>", unsafe_allow_html=True)