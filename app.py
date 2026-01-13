import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# --- 1. DESIGN (Červená odstranit, Bílá přemístit, Žlutá šipka/plus) ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    /* ODSTRANĚNÍ RUŠIVÝCH PRVKŮ */
    header, .stDeployButton { visibility: hidden; display: none !important; }
    .stApp { background-color: #0e1117; }
    
    /* Úprava chatovacího pole podle tvého nákresu */
    div[data-testid="stChatInput"] {
        border-radius: 25px !important;
        border: 1px solid #30363d !important;
        background-color: #161b22 !important;
    }
    
    /* Kontejner pro nástroje Notebooku */
    .notebook-card {
        background-color: #1e2129;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABÁZE A PAMĚŤ ---
conn = st.connection("gsheets", type=GSheetsConnection)
def load_data():
    try:
        u = conn.read(worksheet="Users", ttl=0)
        s = conn.read(worksheet="Stats", ttl=0)
        return u, s
    except:
        return pd.DataFrame(columns=["user_id", "chat_id", "role", "content", "timestamp"]), \
               pd.DataFrame([{"key": "total_messages", "value": "0"}])

users_df, stats_df = load_data()
total_msgs = int(stats_df.loc[stats_df['key'] == 'total_messages', 'value'].values[0]) if not stats_df.empty else 0

if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]

# --- 3. SIDEBAR (Žlutá šipka pro ovládání) ---
with st.sidebar:
    st.title("🤖 S.M.A.R.T. OS")
    mode = st.radio("Režim", ["💬 Chat", "🧠 Notebook Nástroje"])
    st.divider()
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.rerun()
    st.caption(f"Zprávy: {total_msgs}/200")

# --- 4. FUNKCE NOTEBOOKU (To, co jsi poslal na obrázku) ---
def generate_notebook_tool(tool_name, prompt_extra):
    st.info(f"Generuji {tool_name} z nahraných podkladů...")
    # Zde by AI vzala nahrané soubory a vytvořila výstup (např. kvíz)
    # Pro ukázku teď použijeme chat input, ale AI k tomu dostane instrukci

# --- 5. HLAVNÍ PLOCHA ---
if mode == "🧠 Notebook Nástroje":
    st.subheader("Nástroje Notebooku (Beta)")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎙️ Audio přehled"): generate_notebook_tool("Audio", "Vytvoř scénář pro audio shrnutí")
        if st.button("🗺️ Myšlenková mapa"): generate_notebook_tool("Mapu", "Vytvoř osnovu pro myšlenkovou mapu")
        if st.button("🗂️ Výukové kartičky"): generate_notebook_tool("Kartičky", "Vytvoř 10 otázek a odpovědí")
    with col2:
        if st.button("🎥 Video přehled"): generate_notebook_tool("Video", "Vytvoř scénář pro video")
        if st.button("📝 Zprávy"): generate_notebook_tool("Zprávu", "Shrň dokument do formální zprávy")
        if st.button("❓ Kvíz"): generate_notebook_tool("Kvíz", "Vytvoř test s volbami A, B, C")

else:
    # CHAT REŽIM
    st.markdown('<div style="max-width: 850px; margin: 0 auto;">', unsafe_allow_html=True)
    cur_chat = users_df[users_df["chat_id"] == st.session_state.chat_id]
    
    for _, m in cur_chat.iterrows():
        with st.chat_message(m["role"]):
            st.write(m["content"])

    # PLUS (+) U INPUTU PODLE OBRÁZKU
    up_file = st.file_uploader("➕", type=["png", "jpg", "jpeg", "pdf", "txt"], label_visibility="collapsed")
    if prompt := st.chat_input("Zeptejte se Gemini 3..."):
        with st.chat_message("user"):
            st.write(prompt)
            
        # AI LOGIKA S PAMĚTÍ A ČEŠTINOU
        model_name = "gemini-3-flash" if total_msgs < 200 else "gemini-2.5-flash-lite"
        api_keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
        
        history = []
        for _, row in cur_chat.tail(10).iterrows():
            history.append({"role": "user" if row["role"] == "user" else "model", "parts": [row["content"]]})

        current_parts = [prompt]
        if up_file:
            raw_data = up_file.read()
            if up_file.type == "text/plain": current_parts.append(raw_data.decode('utf-8'))
            else: current_parts.append({"mime_type": up_file.type, "data": raw_data})

        success = False
        for key in api_keys:
            if not key or success: continue
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name=model_name, 
                    system_instruction="VŽDY MLUV ČESKY ZA KAŽDÝCH OKOLNOSTÍ. Jsi S.M.A.R.T. OS, tvůrce studijních materiálů.")
                chat_session = model.start_chat(history=history)
                response = chat_session.send_message(current_parts)
                ai_text = response.text
                success = True
                break
            except: continue

        if success:
            with st.chat_message("assistant"): st.markdown(ai_text)
            # Uložení (včetně historie)
            now = datetime.now().strftime("%H:%M")
            u_row = pd.DataFrame([{"user_id": "public", "chat_id": st.session_state.chat_id, "role": "user", "content": prompt, "timestamp": now}])
            a_row = pd.DataFrame([{"user_id": "public", "chat_id": st.session_state.chat_id, "role": "assistant", "content": ai_text, "timestamp": now}])
            conn.update(worksheet="Users", data=pd.concat([users_df, u_row, a_row], ignore_index=True))
            stats_df.loc[stats_df['key'] == 'total_messages', 'value'] = str(total_msgs + 1)
            conn.update(worksheet="Stats", data=stats_df)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
