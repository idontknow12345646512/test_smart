import streamlit as st
import google.generativeai as genai
from supabase import create_client
import pandas as pd
import uuid

# --- 1. DESIGN & ŠIPKA (Žlutá šipka v sidebaru) ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    /* Průhledný header aby zůstala šipka sidebaru */
    header[data-testid="stHeader"] { background: rgba(0,0,0,0) !important; }
    .stDeployButton, #MainMenu { visibility: hidden; }
    
    /* Vynucení žluté barvy pro šipku */
    button[data-testid="stSidebarCollapseIcon"] { color: #FFD700 !important; }
    
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    
    /* Zaoblený input kapsle podle tvého nákresu */
    div[data-testid="stChatInput"] { 
        border-radius: 30px !important; 
        background-color: #161b22 !important; 
        border: 1px solid #333 !important;
    }
    .disclaimer { font-size: 0.75rem; color: #5d636d; text-align: center; padding: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. PŘIPOJENÍ ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 3. AUTH LOGIKA ---
if "user" not in st.session_state:
    st.title("🤖 S.M.A.R.T. OS: Přihlášení")
    tab1, tab2 = st.tabs(["Přihlásit se", "Vytvořit účet"])
    
    with tab1:
        email = st.text_input("Email")
        pwd = st.text_input("Heslo", type="password")
        if st.button("Vstoupit", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Chyba přihlášení.")
            
    with tab2:
        reg_email = st.text_input("Nový Email")
        reg_pwd = st.text_input("Nové Heslo (min. 6 znaků)", type="password")
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": reg_email, "password": reg_pwd})
                st.success("Účet vytvořen! Nyní se přihlaste v první záložce.")
            except: st.error("Chyba registrace.")
    st.stop()

# --- 4. DATA PRO PŘIHLÁŠENÉHO UŽIVATELE ---
user_id = st.session_state.user.id

def get_history(chat_id):
    # Načte historii jen pro přihlášeného uživatele
    res = supabase.table("messages").select("*").eq("chat_id", chat_id).eq("user_id", user_id).order("created_at").execute()
    return res.data

def save_msg(chat_id, role, content):
    supabase.table("messages").insert({
        "chat_id": chat_id, "role": role, "content": content, "user_id": user_id
    }).execute()

# --- 5. SIDEBAR ---
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]

with st.sidebar:
    st.markdown("<h1 style='color: #FFD700;'>S.M.A.R.T.</h1>", unsafe_allow_html=True)
    st.write(f"📧 {st.session_state.user.email}")
    
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.rerun()
    
    st.divider()
    # Zobrazení tvých minulých chatů
    chats_res = supabase.table("messages").select("chat_id").eq("user_id", user_id).execute()
    u_ids = list(set([c['chat_id'] for c in chats_res.data]))[-5:]
    for cid in reversed(u_ids):
        if st.button(f"📁 Chat {cid}", key=cid, use_container_width=True):
            st.session_state.chat_id = cid
            st.rerun()
            
    if st.button("Odhlásit se"):
        del st.session_state.user
        st.rerun()

# --- 6. CHAT ---
st.subheader(f"Režim: Pro | ID: {st.session_state.chat_id}")

history = get_history(st.session_state.chat_id)
for m in history:
    with st.chat_message(m["role"]): st.markdown(m["content"])

# Nahrávání souborů (Plusko)
up = st.file_uploader("➕", type=["pdf", "txt", "docx"], label_visibility="collapsed")

if prompt := st.chat_input("Zeptejte se na cokoliv..."):
    with st.chat_message("user"): st.markdown(prompt)
    save_msg(st.session_state.chat_id, "user", prompt)

    # Gemini logika
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY_1"])
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction="Jsi S.M.A.R.T. OS.")
    
    gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in history]
    response = model.start_chat(history=gem_hist).send_message(prompt)
    
    with st.chat_message("assistant"): st.markdown(response.text)
    save_msg(st.session_state.chat_id, "assistant", response.text)
    st.rerun()

st.markdown("<div class='disclaimer'>S.M.A.R.T. OS může dělat chyby. Data jsou soukromá.</div>", unsafe_allow_html=True)