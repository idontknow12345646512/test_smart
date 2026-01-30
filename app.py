import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import time
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. KONFIGURACE A STAV ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

# Načtení query parametrů pro Admin mód
query_params = st.query_params
is_admin_mode = query_params.get("mode") == "admin"

# --- 2. CSS STYLING (DESIGN PODLE OBRÁZKU) ---
st.markdown("""
    <style>
    /* ZÁKLAD - Tmavý, moderní */
    .stApp { background-color: #121212; color: #E0E0E0; }
    
    /* SKRYTÍ HEADERU (ale zachování šipky) */
    header[data-testid="stHeader"] { 
        background: transparent !important; 
        color: transparent !important;
    }
    /* Toto vynutí zobrazení šipky i při skrytém headeru */
    header[data-testid="stHeader"] button {
        visibility: visible !important;
        color: #FFD700 !important; /* ŽLUTÁ ŠIPKA */
    }
    
    .stDeployButton { display: none; }
    
    /* SIDEBAR - Tmavší šedá, oddělená */
    section[data-testid="stSidebar"] {
        background-color: #000000;
        border-right: 1px solid #333;
    }
    
    /* ŠIPKA PRO SIDEBAR - Stylizace */
    button[kind="header"] {
        color: #FFD700 !important;
        background: transparent !important;
    }

    /* CHAT BUBBLINY */
    [data-testid="stChatMessage"] {
        background-color: transparent;
        border: none;
    }
    [data-testid="chatAvatarIcon-user"] {
        background-color: #FFD700 !important; 
    }
    
    /* INPUT BAR - "Kapsle" */
    div[data-testid="stChatInput"] {
        border-radius: 30px !important;
        border: 1px solid #444 !important;
        background-color: #1e1e1e !important;
        padding: 5px 10px !important;
        margin-bottom: 20px;
    }
    
    /* Tlačítka Notebooku */
    .stButton button {
        border-radius: 20px;
        border: 1px solid #333;
        background-color: #1e1e1e;
        color: white;
        transition: all 0.3s;
    }
    .stButton button:hover {
        border-color: #FFD700;
        color: #FFD700;
    }
    
    /* Warning/Disclaimer text dole */
    .disclaimer {
        font-size: 0.7rem;
        color: #666;
        text-align: center;
        margin-top: -15px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        users = conn.read(worksheet="Users", ttl=0)
        stats = conn.read(worksheet="Stats", ttl=0)
        if users.empty: users = pd.DataFrame(columns=["user_id", "chat_id", "role", "content", "timestamp"])
        if stats.empty: stats = pd.DataFrame([{"key": "total_messages", "value": "0"}])
        return users, stats
    except:
        return pd.DataFrame(), pd.DataFrame()

# Session State Init
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]
if "notebook_context" not in st.session_state: st.session_state.notebook_context = ""
if "file_name" not in st.session_state: st.session_state.file_name = None

users_df, stats_df = get_data()
total_msgs = int(stats_df.loc[stats_df['key'] == 'total_messages', 'value'].values[0]) if not stats_df.empty else 0

# --- 4. FUNKCE GEMINI ---
def call_gemini(prompt_parts, history=[]):
    api_keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    api_keys = [k for k in api_keys if k]
    model_name = "gemini-1.5-flash"
    
    for key in api_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name=model_name, system_instruction=SMART_SYSTEM_INSTRUCTION)
            chat = model.start_chat(history=history)
            response = chat.send_message(prompt_parts)
            return response.text
        except Exception:
            continue
    return "⚠️ Omlouvám se, systémy jsou momentálně přetížené."

def save_msg(role, content):
    global users_df, total_msgs
    now = datetime.now().strftime("%H:%M")
    new_row = pd.DataFrame([{"user_id": "public", "chat_id": st.session_state.chat_id, "role": role, "content": content, "timestamp": now}])
    users_df = pd.concat([users_df, new_row], ignore_index=True)
    conn.update(worksheet="Users", data=users_df)
    if role == "assistant":
        stats_df.loc[stats_df['key'] == 'total_messages', 'value'] = str(total_msgs + 1)
        conn.update(worksheet="Stats", data=stats_df)

# --- 5. LOGIKA APLIKACE ---

if is_admin_mode:
    st.title("🔐 Admin Panel")
    pwd = st.text_input("Heslo", type="password")
    if pwd == st.secrets.get("ADMIN_PASSWORD", "admin123"):
        t1, t2 = st.tabs(["Statistiky", "Data"])
        with t1:
            st.metric("Celkem zpráv", total_msgs)
            if st.button("Resetovat počítadlo"):
                conn.update(worksheet="Stats", data=pd.DataFrame([{"key": "total_messages", "value": "0"}]))
                st.rerun()
        with t2:
            st.dataframe(users_df)
    else:
        if pwd: st.error("Přístup zamítnut")

else:
    # SIDEBAR
    with st.sidebar:
        st.header("S.M.A.R.T. OS")
        if st.button("➕ Nový chat", use_container_width=True):
            st.session_state.chat_id = str(uuid.uuid4())[:8]
            st.session_state.notebook_context = ""
            st.session_state.file_name = None
            st.rerun()

        st.markdown("---")
        st.subheader("Historie")
        my_chats = users_df[users_df["chat_id"].notna()]["chat_id"].unique()
        for cid in list(my_chats)[-5:]:
            if st.button(f"Chat {cid}", key=f"hist_{cid}"):
                st.session_state.chat_id = cid
                st.rerun()

        st.markdown("---")
        with st.expander("👤 Můj Účet"):
            if st.button("⚙️ Admin Login"):
                st.query_params["mode"] = "admin"
                st.rerun()

    # HLAVNÍ PLOCHA
    c1, c2 = st.columns([8, 2])
    with c2:
        st.markdown("<div style='text-align: right; color: #666;'>Log in | Sign up</div>", unsafe_allow_html=True)

    if st.session_state.notebook_context:
        st.info(f"🧠 Kontext: **{st.session_state.file_name}**")
        with st.expander("🛠️ Nástroje Notebooku", expanded=False):
            nc1, nc2, nc3 = st.columns(3)
            if nc1.button("🎙️ Audio"):
                save_msg("user", "Generuj: Audio Scénář")
                resp = call_gemini([f"KONTEXT: {st.session_state.notebook_context}\n\nÚKOL: Vytvoř scénář podcastu."])
                save_msg("assistant", resp)
                st.rerun()
            # ... další tlačítka (Kvíz, Souhrn) ...

    # Vykreslení chatu
    current_chat_msgs = users_df[users_df["chat_id"] == st.session_state.chat_id]
    chat_container = st.container()
    with chat_container:
        if current_chat_msgs.empty:
            st.markdown("<div style='text-align: center; margin-top: 100px; color: #555;'><h2>👋 S.M.A.R.T. OS</h2></div>", unsafe_allow_html=True)
        for _, row in current_chat_msgs.iterrows():
            with st.chat_message(row["role"]):
                st.markdown(row["content"])

    # INPUT
    uploaded_file = st.file_uploader("Přidat soubor", type=["pdf", "txt", "docx"], label_visibility="collapsed")
    if uploaded_file and uploaded_file.name != st.session_state.file_name:
        text = extract_text_from_file(uploaded_file)
        if text:
            st.session_state.notebook_context = text
            st.session_state.file_name = uploaded_file.name
            st.rerun()

    if user_input := st.chat_input("Zeptejte se na cokoliv..."):
        save_msg("user", user_input)
        history_gemini = []
        for _, r in current_chat_msgs.tail(10).iterrows():
            history_gemini.append({"role": "user" if r["role"] == "user" else "model", "parts": [r["content"]]})
        
        prompt_parts = [user_input]
        if st.session_state.notebook_context:
            prompt_parts.append(f"\n\n[KONTEXT]: {st.session_state.notebook_context[:15000]}")

        response_text = call_gemini(prompt_parts, history=history_gemini)
        save_msg("assistant", response_text)
        st.rerun()

    st.markdown("<div class='disclaimer'>S.M.A.R.T. OS může dělat chyby.</div>", unsafe_allow_html=True)