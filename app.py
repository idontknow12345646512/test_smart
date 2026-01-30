import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. KONFIGURACE A STAV SIDEBARU ---
# Inicializace stavu sidebaru, aby šel ovládat tlačítkem
if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"

st.set_page_config(
    page_title="S.M.A.R.T. OS", 
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state=st.session_state.sidebar_state
)

# --- CSS STYLY (ŽLUTÁ ŠIPKA A SKRYTÍ HEADERU) ---
st.markdown("""
    <style>
    /* 1. Skryjeme standardní header a deploy button */
    header[data-testid="stHeader"] {
        background-color: transparent;
        border-bottom: none;
    }
    /* Skryje barevnou linku nahoře */
    header[data-testid="stHeader"] > div:first-child {
        display: none;
    }
    .stDeployButton {
        display: none !important;
    }
    [data-testid="stMainMenu"] {
        display: none !important;
    }

    /* 2. ZVIDITELNÍME A OBARVÍME ŠIPKU PRO SIDEBAR */
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }
    button[kind="header"] {
        background-color: transparent !important;
        color: #FFD700 !important; /* Žlutá barva šipky */
        border: 1px solid #30363d;
        visibility: visible !important;
    }
    
    /* 3. Tmavý vzhled aplikace */
    .stApp { background-color: #0e1117; }
    
    /* Chat input */
    div[data-testid="stChatInput"] {
        border-radius: 25px !important;
        border: 1px solid #30363d !important;
        background-color: #161b22 !important;
    }
    
    /* Karty */
    .notebook-card {
        background-color: #1e2129;
        border-left: 5px solid #FFD700; /* Žlutý akcent */
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 5px;
    }
    .success-box {
        padding: 10px;
        background-color: #0d3625;
        border-radius: 5px;
        color: #57ab5a;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABÁZE A PAMĚŤ ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        u = conn.read(worksheet="Users", ttl=0)
        s = conn.read(worksheet="Stats", ttl=0)
        if u.empty: u = pd.DataFrame(columns=["user_id", "chat_id", "role", "content", "timestamp"])
        if s.empty: s = pd.DataFrame([{"key": "total_messages", "value": "0"}])
        return u, s
    except Exception:
        return pd.DataFrame(columns=["user_id", "chat_id", "role", "content", "timestamp"]), \
               pd.DataFrame([{"key": "total_messages", "value": "0"}])

users_df, stats_df = load_data()
total_msgs = int(stats_df.loc[stats_df['key'] == 'total_messages', 'value'].values[0]) if not stats_df.empty else 0

if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]
if "notebook_context" not in st.session_state: st.session_state.notebook_context = "" 
if "last_uploaded_filename" not in st.session_state: st.session_state.last_uploaded_filename = None

# --- 3. POMOCNÉ FUNKCE PRO AI ---
def get_gemini_response(prompt_parts, history=[]):
    model_name = "gemini-1.5-flash"
    api_keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    api_keys = [k for k in api_keys if k]

    if not api_keys: return "⚠️ Chyba: Nejsou nastaveny API klíče."

    for key in api_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name=model_name, system_instruction=SMART_SYSTEM_INSTRUCTION)
            chat = model.start_chat(history=history)
            response = chat.send_message(prompt_parts)
            return response.text
        except Exception: continue
            
    return "⚠️ Systémy přetíženy, zkuste to prosím později."

def save_interaction(role, content):
    global users_df, stats_df, total_msgs
    now = datetime.now().strftime("%H:%M")
    new_row = pd.DataFrame([{"user_id": "public", "chat_id": st.session_state.chat_id, "role": role, "content": content, "timestamp": now}])
    users_df = pd.concat([users_df, new_row], ignore_index=True)
    conn.update(worksheet="Users", data=users_df)
    if role == "assistant":
        total_msgs += 1
        stats_df.loc[stats_df['key'] == 'total_messages', 'value'] = str(total_msgs)
        conn.update(worksheet="Stats", data=stats_df)

# --- 4. TLAČÍTKO NA OTEVŘENÍ SIDEBARU (POKUD JE ZAVŘENÝ) ---
# Toto se zobrazí nahoře, pokud by uživatel sidebar zavřel
col_btn, _ = st.columns([1, 10])
with col_btn:
    if st.button("➤ Menu", key="open_sidebar_btn", help="Otevřít postranní panel"):
        st.session_state.sidebar_state = "expanded"
        st.rerun()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🤖 S.M.A.R.T. OS")
    mode = st.radio("Režim", ["💬 Chat", "🧠 Notebook Nástroje"])
    st.divider()
    
    st.subheader("📂 Zdrojová data")
    uploaded_file = st.file_uploader("Nahrajte studijní materiály", type=["pdf", "txt", "docx", "png", "jpg"], label_visibility="collapsed")
    
    if uploaded_file:
        if uploaded_file.name != st.session_state.last_uploaded_filename:
            with st.spinner("Analyzuji dokument..."):
                extracted_text = extract_text_from_file(uploaded_file)
                if extracted_text:
                    st.session_state.notebook_context = extracted_text
                    st.session_state.last_uploaded_filename = uploaded_file.name
                    st.success("Dokument načten!")
                else:
                    st.warning("Pouze obrazový režim.")

    if st.session_state.notebook_context:
        st.markdown(f"<div class='success-box'>✅ Kontext aktivní</div>", unsafe_allow_html=True)
        if st.button("❌ Vyčistit paměť"):
            st.session_state.notebook_context = ""
            st.session_state.last_uploaded_filename = None
            st.rerun()

    st.divider()
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.session_state.notebook_context = ""
        st.rerun()
    st.caption(f"Zprávy: {total_msgs}/200")

# --- 6. FUNKCE NOTEBOOKU ---
def run_notebook_tool(tool_name, prompt_instruction):
    if not st.session_state.notebook_context:
        st.warning("⚠️ Nejdříve nahrajte soubor v menu (vlevo).")
        return

    st.markdown(f"### ⚙️ Generuji: {tool_name}")
    with st.spinner("Pracuji na tom..."):
        full_prompt = f"ZDROJOVÝ TEXT:\n{st.session_state.notebook_context[:30000]}\n\nINSTRUKCE:\n{prompt_instruction}\nVýstup formátuj v Markdownu."
        response = get_gemini_response([full_prompt])
        st.markdown("---")
        st.markdown(response)
        save_interaction("user", f"Generuj nástroj: {tool_name}")
        save_interaction("assistant", response)

# --- 7. HLAVNÍ PLOCHA ---
if mode == "🧠 Notebook Nástroje":
    st.subheader("🧠 Notebook LM: Studijní Nástroje")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎙️ Audio Přehled (Scénář)", use_container_width=True): 
            run_notebook_tool("Audio Scénář", "Vytvoř scénář podcastu (Host a Expert). Musí to být dialog.")
        if st.button("🗺️ Myšlenková mapa", use_container_width=True): 
            run_notebook_tool("Myšlenková mapa", "Vytvoř hierarchickou osnovu pro myšlenkovou mapu.")
        if st.button("🗂️ Výukové kartičky", use_container_width=True): 
            run_notebook_tool("Kartičky", "Vytvoř 10 kartiček (Otázka/Odpověď).")

    with col2:
        if st.button("🎥 Video Scénář", use_container_width=True): 
            run_notebook_tool("Video Scénář", "Vytvoř scénář pro YouTube video.")
        if st.button("📝 Formální Zpráva", use_container_width=True): 
            run_notebook_tool("Zpráva", "Shrň dokument do Executive Summary.")
        if st.button("❓ Kvíz (A, B, C)", use_container_width=True): 
            run_notebook_tool("Kvíz", "Vytvoř test s 5 otázkami a řešením.")

else:
    # CHAT REŽIM
    st.markdown('<div style="max-width: 850px; margin: 0 auto;">', unsafe_allow_html=True)
    
    cur_chat = users_df[users_df["chat_id"] == st.session_state.chat_id]
    for _, m in cur_chat.iterrows():
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    chat_file = st.file_uploader("📎", type=["png", "jpg", "pdf", "txt"], key="chat_up", label_visibility="collapsed")
    
    if prompt := st.chat_input("Zeptejte se Gemini..."):
        with st.chat_message("user"): st.markdown(prompt)
        save_interaction("user", prompt)

        history_gemini = []
        for _, row in cur_chat.tail(10).iterrows():
            history_gemini.append({"role": "user" if row["role"] == "user" else "model", "parts": [row["content"]]})
        
        current_parts = [prompt]
        if st.session_state.notebook_context:
            current_parts.append(f"\n\n(Kontext z dokumentu: {st.session_state.notebook_context[:10000]}...)")

        if chat_file:
            raw_data = chat_file.read()
            if chat_file.type in ["image/png", "image/jpeg"]: current_parts.append({"mime_type": chat_file.type, "data": raw_data})
            elif chat_file.type == "application/pdf": current_parts.append(f"Obsah PDF: {extract_text_from_file(chat_file)}")
            else: current_parts.append(raw_data.decode('utf-8'))

        with st.chat_message("assistant"):
            with st.spinner("..."):
                ai_text = get_gemini_response(current_parts, history=history_gemini)
                st.markdown(ai_text)
        
        save_interaction("assistant", ai_text)
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
