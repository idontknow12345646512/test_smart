import streamlit as st
import google.generativeai as genai
from supabase import create_client
import pandas as pd
import uuid
from datetime import datetime

# --- 1. DESIGN PODLE TVÉHO NÁKRESU ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    /* Odstranění lišt Streamlitu pro čistý vzhled */
    header, .stDeployButton { visibility: hidden; display: none !important; }
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    
    /* Ikona šipky (sidebar) - žlutá barva podle nákresu */
    button[kind="header"] { color: #FFD700 !important; }
    
    /* Input kapsle - kulaté rohy a tmavé barvy */
    div[data-testid="stChatInput"] { 
        border-radius: 30px !important; 
        background-color: #161b22 !important; 
        border: 1px solid #333 !important;
        margin-bottom: 5px;
    }
    
    /* Disclaimer pod inputem - fixní pozice */
    .disclaimer { 
        font-size: 0.75rem; 
        color: #5d636d; 
        text-align: center; 
        padding-bottom: 20px; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. PŘIPOJENÍ K DATABÁZI (Bleskový Supabase) ---
@st.cache_resource
def init_db():
    # Použije klíče ze Secrets
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_db()

def load_messages(chat_id):
    # Načte historii zpráv okamžitě bez točícího se kolečka
    res = supabase.table("messages").select("*").eq("chat_id", chat_id).order("created_at").execute()
    return res.data

def save_message(chat_id, role, content):
    # Uloží zprávu "navždy"
    supabase.table("messages").insert({
        "chat_id": chat_id, 
        "role": role, 
        "content": content
    }).execute()

# --- 3. SIDEBAR (Historie a Účet) ---
if "chat_id" not in st.session_state: 
    st.session_state.chat_id = str(uuid.uuid4())[:8]

with st.sidebar:
    st.markdown("<h1 style='color: #FFD700;'>S.M.A.R.T. OS</h1>", unsafe_allow_html=True)
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.rerun()
    
    st.divider()
    st.caption("Tvoje historie")
    # Dynamické načtení posledních chatů
    try:
        all_chats = supabase.table("messages").select("chat_id").execute()
        unique_ids = list(set([c['chat_id'] for c in all_chats.data]))[-10:]
        for cid in reversed(unique_ids):
            if st.button(f"📁 Chat {cid}", key=f"btn_{cid}", use_container_width=True):
                st.session_state.chat_id = cid
                st.rerun()
    except:
        st.info("Zatím žádná historie.")

    # Tlačítko pro Účet/Nastavení úplně dole
    st.markdown("<div style='position: fixed; bottom: 20px; width: 260px;'>", unsafe_allow_html=True)
    if st.button("👤 Můj účet / Nastavení", use_container_width=True):
        st.session_state.show_admin = not st.session_state.get('show_admin', False)
    st.markdown("</div>", unsafe_allow_html=True)

# --- 4. HLAVNÍ PLOCHA ---
if st.session_state.get('show_admin'):
    st.title("🔐 Správa S.M.A.R.T. OS")
    pwd = st.text_input("Zadejte admin heslo", type="password")
    if pwd == st.secrets["ADMIN_PASSWORD"]:
        st.success("Přihlášeno")
        res = supabase.table("messages").select("*").execute()
        df = pd.DataFrame(res.data)
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Záloha CSV", df.to_csv(index=False), "backup.csv")
else:
    # Přepínač režimů (Pro / NotebookLM)
    mode = st.segmented_control("Režim", ["💬 Chat", "🧠 NotebookLM"], default="💬 Chat")
    
    # Zobrazení historie chatu
    history_data = load_messages(st.session_state.chat_id)
    for msg in history_data:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # PLUS (+) u inputu pro nahrávání souborů
    with st.container():
        up_file = st.file_uploader("➕", type=["pdf", "txt", "docx"], label_visibility="collapsed")
        
        if prompt := st.chat_input("Zeptejte se na cokoliv..."):
            # 1. Zobrazení a uložení uživatele
            with st.chat_message("user"): st.markdown(prompt)
            save_message(st.session_state.chat_id, "user", prompt)

            # 2. AI LOGIKA (Gemini)
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY_1"])
            # Systémová instrukce zajišťuje češtinu
            model = genai.GenerativeModel("gemini-1.5-flash", 
                system_instruction="Vždy mluv česky. Jsi S.M.A.R.T. OS, inteligentní asistent.")
            
            # Příprava kontextu (paměti) z historie
            gem_history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in history_data]
            chat_session = model.start_chat(history=gem_history)
            
            # Generování odpovědi
            with st.spinner("S.M.A.R.T. přemýšlí..."):
                response = chat_session.send_message(prompt)
                ai_text = response.text

            # 3. Zobrazení a uložení AI
            with st.chat_message("assistant"): st.markdown(ai_text)
            save_message(st.session_state.chat_id, "assistant", ai_text)
            st.rerun()

    # Fixní disclaimer dole
    st.markdown("<div class='disclaimer'>S.M.A.R.T. OS může dělat chyby. Vždy si ověřte důležité informace.</div>", unsafe_allow_html=True)