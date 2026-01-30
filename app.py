import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid

# --- DESIGN & STYLING ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    header[data-testid="stHeader"] { background: rgba(0,0,0,0) !important; }
    .stDeployButton, #MainMenu { visibility: hidden; }
    button[data-testid="stSidebarCollapseIcon"] { color: #FFD700 !important; }
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    div[data-testid="stChatInput"] { 
        border-radius: 30px !important; 
        background-color: #161b22 !important; 
        border: 1px solid #333 !important;
    }
    .disclaimer { font-size: 0.75rem; color: #5d636d; text-align: center; padding: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- PŘIPOJENÍ ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- PŘIHLÁŠENÍ ---
if "user" not in st.session_state:
    st.title("🤖 S.M.A.R.T. OS: Vítejte")
    t1, t2 = st.tabs(["Přihlásit se", "Vytvořit účet"])
    with t1:
        em = st.text_input("Email", key="login_em")
        pw = st.text_input("Heslo", type="password", key="login_pw")
        if st.button("Vstoupit", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Chybné údaje.")
    with t2:
        reg_em = st.text_input("Email", key="reg_em")
        reg_pw = st.text_input("Heslo (min. 6 znaků)", type="password", key="reg_pw")
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": reg_em, "password": reg_pw})
                st.success("Účet vytvořen! Nyní se přihlaste.")
            except: st.error("Chyba při registraci.")
    st.stop()

# --- LOGIKA CHATU ---
user_id = st.session_state.user.id
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]

def save_m(cid, role, content):
    supabase.table("messages").insert({"chat_id": cid, "role": role, "content": content, "user_id": user_id}).execute()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='color: #FFD700;'>S.M.A.R.T.</h1>", unsafe_allow_html=True)
    st.caption(f"Uživatel: {st.session_state.user.email}")
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.rerun()
    st.divider()
    # Historie
    hist_res = supabase.table("messages").select("chat_id").eq("user_id", user_id).execute()
    u_ids = list(set([c['chat_id'] for c in hist_res.data]))[-5:]
    for cid in reversed(u_ids):
        if st.button(f"📁 Chat {cid}", key=cid, use_container_width=True):
            st.session_state.chat_id = cid
            st.rerun()
    if st.button("Odhlásit se"):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()

# --- HLAVNÍ CHAT ---
st.subheader(f"Chat ID: {st.session_state.chat_id}")
history = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).eq("user_id", user_id).order("created_at").execute().data

for m in history:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Zeptejte se na cokoliv..."):
    with st.chat_message("user"): st.markdown(prompt)
    save_m(st.session_state.chat_id, "user", prompt)

    genai.configure(api_key=st.secrets["GOOGLE_API_KEY_1"])
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction="Mluv vždy česky. Jsi S.M.A.R.T. OS.")
    
    gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in history]
    response = model.start_chat(history=gem_hist).send_message(prompt)
    
    with st.chat_message("assistant"): st.markdown(response.text)
    save_m(st.session_state.chat_id, "assistant", response.text)
    st.rerun()

st.markdown("<div class='disclaimer'>S.M.A.R.T. OS může dělat chyby. Vaše data jsou v bezpečí.</div>", unsafe_allow_html=True)