import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# --- 1. DESIGN (Stabilní a čistý) ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    header { visibility: hidden; }
    .stDeployButton { display: none !important; }
    .stApp { background-color: #0e1117; }
    .main-content { max-width: 800px; margin: 0 auto; padding-bottom: 160px; }
    
    /* Úprava pro mobilní zobrazení tlačítka souborů */
    div[data-testid="stFileUploader"] {
        background-color: #1e2129;
        border-radius: 10px;
        padding: 5px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABÁZE ---
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

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🤖 S.M.A.R.T. OS")
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.rerun()
    st.divider()
    st.caption(f"Zprávy: {total_msgs}/200")

# --- 4. CHAT (Zobrazení historie) ---
st.markdown('<div class="main-content">', unsafe_allow_html=True)
cur_chat = users_df[users_df["chat_id"] == st.session_state.chat_id]

for _, m in cur_chat.iterrows():
    with st.chat_message(m["role"]):
        st.write(m["content"])

# --- 5. PLUS TLAČÍTKO A VSTUP ---
with st.container():
    # "+" pro přidání souboru
    up_file = st.file_uploader("➕", type=["png", "jpg", "jpeg", "pdf", "txt"], label_visibility="collapsed")
    prompt = st.chat_input("Napište zprávu...")

# --- 6. AI LOGIKA S PAMĚTÍ (Chat History) ---
if prompt:
    with st.chat_message("user"):
        st.write(prompt)
    
    model_name = "gemini-2.5-flash" if total_msgs < 200 else "gemini-2.5-flash-lite"
    api_keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    
    # --- PRÍPRAVA HISTORIE PRO AI (Paměť) ---
    history = []
    # AI uvidí posledních 10 zpráv z aktuálního chatu
    for _, row in cur_chat.tail(10).iterrows():
        history.append({
            "role": "user" if row["role"] == "user" else "model",
            "parts": [row["content"]]
        })

    # Příprava aktuální zprávy
    current_parts = [prompt]
    if up_file:
        raw_data = up_file.read()
        if up_file.type == "text/plain":
            current_parts.append(f"\n[Soubor: {up_file.name}]\n{raw_data.decode('utf-8')}")
        else:
            current_parts.append({"mime_type": up_file.type, "data": raw_data})

    success = False
    ai_text = ""

    for key in api_keys:
        if not key or success: continue
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction="Vždy mluv česky za každých okolností. Jsi S.M.A.R.T. OS, nápomocný asistent pro studenty."
            )
            
            # Start chatu s historií
            chat_session = model.start_chat(history=history)
            response = chat_session.send_message(current_parts)
            
            ai_text = response.text
            success = True
            break
        except:
            continue

    if success:
        with st.chat_message("assistant"):
            st.markdown(ai_text)
        
        # Uložení do GSheets
        now = datetime.now().strftime("%H:%M")
        u_row = pd.DataFrame([{"user_id": "public", "chat_id": st.session_state.chat_id, "role": "user", "content": prompt, "timestamp": now}])
        a_row = pd.DataFrame([{"user_id": "public", "chat_id": st.session_state.chat_id, "role": "assistant", "content": ai_text, "timestamp": now}])
        conn.update(worksheet="Users", data=pd.concat([users_df, u_row, a_row], ignore_index=True))
        
        # Update limitu
        stats_df.loc[stats_df['key'] == 'total_messages', 'value'] = str(total_msgs + 1)
        conn.update(worksheet="Stats", data=stats_df)
        st.rerun()
    else:
        st.error("AI neodpovídá. Zkontrolujte API klíče.")

st.markdown('</div>', unsafe_allow_html=True)

