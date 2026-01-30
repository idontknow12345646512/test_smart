import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import time
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. KONFIGURACE A DESIGN (Podle tvého obrázku) ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* ODSTRANĚNÍ STREAMLIT PRVKŮ */
    header[data-testid="stHeader"] { background: transparent !important; }
    header[data-testid="stHeader"] button { visibility: visible !important; color: #FFD700 !important; }
    .stDeployButton { display: none !important; }
    #MainMenu { visibility: hidden; }
    
    /* CELKOVÝ VZHLED */
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    
    /* SIDEBAR */
    section[data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px solid #333; }
    
    /* INPUT KAPSLE */
    div[data-testid="stChatInput"] {
        border-radius: 30px !important;
        border: 1px solid #444 !important;
        background-color: #1e1e1e !important;
        padding: 5px 10px !important;
    }
    
    /* DISCLAIMER DOLE */
    .disclaimer {
        font-size: 0.75rem;
        color: #666;
        text-align: center;
        margin-top: 10px;
        padding-bottom: 20px;
    }

    /* NOTEBOOK KARTY */
    .stButton button { border-radius: 20px; border: 1px solid #333; background: #1e1e1e; color: white; }
    .stButton button:hover { border-color: #FFD700; color: #FFD700; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABÁZE (S cache, aby se to netočilo věčně) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        users = conn.read(worksheet="Users", ttl=0)
        stats = conn.read(worksheet="Stats", ttl=0)
        return users, stats
    except:
        return pd.DataFrame(columns=["user_id", "chat_id", "role", "content", "timestamp"]), \
               pd.DataFrame([{"key": "total_messages", "value": "0"}])

users_df, stats_df = get_data()
total_msgs = int(stats_df.loc[stats_df['key'] == 'total_messages', 'value'].values[0]) if not stats_df.empty else 0

# Stav session
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]
if "notebook_context" not in st.session_state: st.session_state.notebook_context = ""
if "file_name" not in st.session_state: st.session_state.file_name = None

# --- 3. AI LOGIKA (Gemini 1.5 Flash + Čeština) ---
def call_gemini(prompt_parts, history=[]):
    api_keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    api_keys = [k for k in api_keys if k]
    
    for key in api_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=SMART_SYSTEM_INSTRUCTION # "Vždy mluv česky..."
            )
            chat = model.start_chat(history=history)
            response = chat.send_message(prompt_parts)
            return response.text
        except:
            continue
    return "⚠️ Systém je přetížen, zkuste to prosím za moment."

def save_msg(role, content):
    global users_df, total_msgs
    now = datetime.now().strftime("%H:%M")
    new_row = pd.DataFrame([{"user_id": "public", "chat_id": st.session_state.chat_id, "role": role, "content": content, "timestamp": now}])
    users_df = pd.concat([users_df, new_row], ignore_index=True)
    conn.update(worksheet="Users", data=users_df)
    
    if role == "assistant":
        stats_df.loc[stats_df['key'] == 'total_messages', 'value'] = str(total_msgs + 1)
        conn.update(worksheet="Stats", data=stats_df)

# --- 4. STRUKTURA STRÁNKY (Podle obrázku) ---

# SIDEBAR
with st.sidebar:
    st.markdown("<h1 style='color: #FFD700;'>S.M.A.R.T. OS</h1>", unsafe_allow_html=True)
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.session_state.notebook_context = ""
        st.session_state.file_name = None
        st.rerun()
    
    st.divider()
    st.subheader("Historie")
    my_chats = users_df["chat_id"].unique()
    for cid in list(my_chats)[-5:]:
        if st.button(f"Chat {cid}", key=f"h_{cid}", use_container_width=True):
            st.session_state.chat_id = cid
            st.rerun()

    st.markdown("<div style='position: fixed; bottom: 20px; width: 260px;'>", unsafe_allow_html=True)
    if st.button("👤 Můj Účet / Admin", use_container_width=True):
        st.query_params["mode"] = "admin"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ADMIN MÓD (Pokud je v URL)
if st.query_params.get("mode") == "admin":
    st.title("🔐 Admin Panel")
    if st.text_input("Heslo", type="password") == st.secrets.get("ADMIN_PASSWORD"):
        st.write(f"Zprávy celkem: {total_msgs}")
        st.dataframe(users_df)
        if st.button("Zavřít Admina"):
            st.query_params.clear()
            st.rerun()
    st.stop()

# HLAVNÍ PLOCHA
mode = st.segmented_control("Režim", ["💬 Chat", "🧠 NotebookLM"], default="💬 Chat")

if mode == "🧠 NotebookLM":
    st.subheader("Nástroje pro vaše soubory")
    if not st.session_state.notebook_context:
        st.warning("Nejdříve nahrajte soubor v režimu Chat.")
    else:
        st.info(f"Pracuji se souborem: {st.session_state.file_name}")
        c1, c2, c3 = st.columns(3)
        if c1.button("🎙️ Audio Scénář"):
            res = call_gemini(f"Vytvoř scénář podcastu z tohoto textu: {st.session_state.notebook_context[:15000]}")
            st.markdown(res)
        if c2.button("❓ Kvíz"):
            res = call_gemini(f"Vytvoř kvíz z tohoto textu: {st.session_state.notebook_context[:15000]}")
            st.markdown(res)
        if c3.button("📝 Shrnutí"):
            res = call_gemini(f"Shrň tento text: {st.session_state.notebook_context[:15000]}")
            st.markdown(res)

else:
    # CHAT
    chat_box = st.container()
    current_chat = users_df[users_df["chat_id"] == st.session_state.chat_id]
    
    with chat_box:
        if current_chat.empty:
            st.markdown("<div style='text-align: center; margin-top: 50px;'><h2>Ahoj! Jak ti můžu dnes pomoci?</h2></div>", unsafe_allow_html=True)
        for _, r in current_chat.iterrows():
            with st.chat_message(r["role"]):
                st.markdown(r["content"])

    # PROSTOR MEZI CHATEM A INPUTEM
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    # INPUT ZÓNA (Kapsle + Plusko)
    with st.container():
        up_file = st.file_uploader("➕", type=["pdf", "docx", "txt"], label_visibility="collapsed")
        if up_file and up_file.name != st.session_state.file_name:
            st.session_state.notebook_context = extract_text_from_file(up_file)
            st.session_state.file_name = up_file.name
            st.success(f"Soubor {up_file.name} nahrán!")
            time.sleep(1)
            st.rerun()

        if prompt := st.chat_input("Zeptejte se na cokoliv..."):
            save_msg("user", prompt)
            
            hist = []
            for _, r in current_chat.tail(6).iterrows():
                hist.append({"role": "user" if r["role"] == "user" else "model", "parts": [r["content"]]})
            
            p_parts = [prompt]
            if st.session_state.notebook_context:
                p_parts.append(f"\n\nKONTEXT Z DOKUMENTU: {st.session_state.notebook_context[:15000]}")
            
            odpoved = call_gemini(p_parts, history=hist)
            save_msg("assistant", odpoved)
            st.rerun()

    st.markdown("<div class='disclaimer'>S.M.A.R.T. OS může dělat chyby. Vždy si ověřte klíčové informace.</div>", unsafe_allow_html=True)