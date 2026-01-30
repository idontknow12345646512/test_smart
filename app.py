import streamlit as st
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. DESIGN & KONFIGURACE ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    /* ODSTRANĚNÍ RUŠIVÝCH PRVKŮ */
    header, .stDeployButton { visibility: hidden; display: none !important; }
    .stApp { background-color: #0e1117; }
    
    /* Úprava chatovacího pole */
    div[data-testid="stChatInput"] {
        border-radius: 25px !important;
        border: 1px solid #30363d !important;
        background-color: #161b22 !important;
    }
    
    /* Styl pro Notebook karty */
    .notebook-card {
        background-color: #1e2129;
        border-left: 5px solid #ff4b4b;
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

# --- 2. DATABÁZE A STAV ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Používáme ttl=0 pro čerstvá data
        u = conn.read(worksheet="Users", ttl=0)
        s = conn.read(worksheet="Stats", ttl=0)
        # Ošetření prázdných dataframů
        if u.empty: u = pd.DataFrame(columns=["user_id", "chat_id", "role", "content", "timestamp"])
        if s.empty: s = pd.DataFrame([{"key": "total_messages", "value": "0"}])
        return u, s
    except Exception:
        return pd.DataFrame(columns=["user_id", "chat_id", "role", "content", "timestamp"]), \
               pd.DataFrame([{"key": "total_messages", "value": "0"}])

users_df, stats_df = load_data()
total_msgs = int(stats_df.loc[stats_df['key'] == 'total_messages', 'value'].values[0]) if not stats_df.empty else 0

# Session State inicializace
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]
if "notebook_context" not in st.session_state: st.session_state.notebook_context = "" 
if "last_uploaded_filename" not in st.session_state: st.session_state.last_uploaded_filename = None

# --- 3. POMOCNÉ FUNKCE PRO AI ---
def get_gemini_response(prompt_parts, history=[]):
    """Získá odpověď z Gemini s rotací klíčů."""
    # Logika výběru modelu: Po 200 zprávách přepne na levnější model
    model_name = "gemini-1.5-flash" # Standardní rychlý model
    
    # Načtení klíčů
    api_keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    api_keys = [k for k in api_keys if k] # Filtrace None

    if not api_keys:
        return "⚠️ Chyba: Nejsou nastaveny API klíče."

    for key in api_keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=model_name, 
                system_instruction=SMART_SYSTEM_INSTRUCTION
            )
            
            chat = model.start_chat(history=history)
            response = chat.send_message(prompt_parts)
            return response.text
        except Exception as e:
            continue # Zkusit další klíč
            
    return "⚠️ Omlouvám se, všechny systémy jsou momentálně přetížené. Zkuste to prosím za chvíli."

def save_interaction(role, content):
    """Uloží zprávu do Google Sheets."""
    global users_df, stats_df, total_msgs
    now = datetime.now().strftime("%H:%M")
    new_row = pd.DataFrame([{
        "user_id": "public", 
        "chat_id": st.session_state.chat_id, 
        "role": role, 
        "content": content, 
        "timestamp": now
    }])
    
    # Update lokálního DF a odeslání do Sheets
    users_df = pd.concat([users_df, new_row], ignore_index=True)
    conn.update(worksheet="Users", data=users_df)
    
    # Update počítadla (pouze pro AI odpovědi, aby se nepočítalo 2x)
    if role == "assistant":
        total_msgs += 1
        stats_df.loc[stats_df['key'] == 'total_messages', 'value'] = str(total_msgs)
        conn.update(worksheet="Stats", data=stats_df)

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🤖 S.M.A.R.T. OS")
    mode = st.radio("Režim", ["💬 Chat", "🧠 Notebook Nástroje"])
    st.divider()
    
    # Správa souborů pro Notebook
    st.subheader("📂 Zdrojová data")
    uploaded_file = st.file_uploader("Nahrajte studijní materiály", type=["pdf", "txt", "docx", "png", "jpg"], label_visibility="collapsed")
    
    if uploaded_file:
        # Pokud je to nový soubor, zpracujeme ho
        if uploaded_file.name != st.session_state.last_uploaded_filename:
            with st.spinner("Analyzuji dokument..."):
                extracted_text = extract_text_from_file(uploaded_file)
                if extracted_text:
                    st.session_state.notebook_context = extracted_text
                    st.session_state.last_uploaded_filename = uploaded_file.name
                    st.success("Dokument načten do paměti!")
                else:
                    st.warning("Tento soubor nelze přečíst jako text (bude použit jako obrázek v chatu).")

    if st.session_state.notebook_context:
        st.markdown(f"<div class='success-box'>✅ Aktivní kontext: {len(st.session_state.notebook_context)} znaků</div>", unsafe_allow_html=True)
        if st.button("❌ Vyčistit paměť"):
            st.session_state.notebook_context = ""
            st.session_state.last_uploaded_filename = None
            st.rerun()

    st.divider()
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.session_state.notebook_context = "" # Reset i kontextu
        st.rerun()
    st.caption(f"Zprávy: {total_msgs}/200")

# --- 5. FUNKCE NOTEBOOKU (LOGIKA) ---
def run_notebook_tool(tool_name, prompt_instruction):
    if not st.session_state.notebook_context:
        st.warning("⚠️ Pro použití nástrojů Notebooku musíte nejprve nahrát dokument (PDF, TXT, DOCX) v postranním panelu.")
        return

    st.markdown(f"### ⚙️ Generuji: {tool_name}")
    with st.spinner("Pracuji na tom..."):
        # Konstrukce promptu s kontextem
        full_prompt = f"""
        ZDROJOVÝ TEXT:
        {st.session_state.notebook_context[:30000]} 
        (text může být zkrácen pokud je příliš dlouhý)

        INSTRUKCE:
        {prompt_instruction}
        
        Výstup musí být ve formátu Markdown. Buď precizní.
        """
        
        response = get_gemini_response([full_prompt])
        
        st.markdown("---")
        st.markdown(response)
        
        # Uložíme výsledek i do historie chatu, aby o tom uživatel věděl
        save_interaction("user", f"Generuj nástroj: {tool_name}")
        save_interaction("assistant", response)

# --- 6. HLAVNÍ PLOCHA ---
if mode == "🧠 Notebook Nástroje":
    st.subheader("🧠 Notebook LM: Studijní Nástroje")
    st.info("Vyberte nástroj. Výstupy budou generovány na základě nahraného dokumentu v postranním panelu.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎙️ Audio Přehled (Scénář)", use_container_width=True): 
            run_notebook_tool("Audio Scénář", "Vytvoř scénář pro podcast (Deep Dive), kde se dva moderátoři (Host a Expert) baví o tomto textu. Mělo by to být poutavé, ne jen suché čtení. Použij formát: **Host:** text... **Expert:** text...")
        
        if st.button("🗺️ Myšlenková mapa (Osnova)", use_container_width=True): 
            run_notebook_tool("Myšlenková mapa", "Vytvoř hierarchickou textovou osnovu (použij odrážky a pod-odrážky), která by sloužila jako základ pro myšlenkovou mapu tohoto textu. Najdi hlavní téma a klíčové větve.")
        
        if st.button("🗂️ Výukové kartičky", use_container_width=True): 
            run_notebook_tool("Kartičky", "Vytvoř 10 studijních kartiček z tohoto textu. Formát: **Otázka:** ... **Odpověď:** ...")

    with col2:
        if st.button("🎥 Video Scénář", use_container_width=True): 
            run_notebook_tool("Video Scénář", "Jsi YouTuber. Vytvoř scénář pro krátké vysvětlující video na základě tohoto textu. Zahrň úvod (háček), hlavní body a závěr.")
        
        if st.button("📝 Formální Zpráva", use_container_width=True): 
            run_notebook_tool("Zpráva", "Shrň tento dokument do profesionální zprávy (Executive Summary). Použij sekce: Úvod, Klíčová zjištění, Závěr.")
        
        if st.button("❓ Kvíz (A, B, C)", use_container_width=True): 
            run_notebook_tool("Kvíz", "Vytvoř test s 5 otázkami z textu. Každá otázka musí mít 3 možnosti (A, B, C) a na konci uveď správné řešení s vysvětlením.")

else:
    # --- CHAT REŽIM ---
    st.markdown('<div style="max-width: 850px; margin: 0 auto;">', unsafe_allow_html=True)
    
    # Zobrazení historie
    cur_chat = users_df[users_df["chat_id"] == st.session_state.chat_id]
    for _, m in cur_chat.iterrows():
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # Input area
    # Poznámka: File uploader v chatu je pro jednorázové obrázky/soubory,
    # zatímco Sidebar uploader je pro dlouhodobou paměť (Notebook mode).
    chat_file = st.file_uploader("Přidat přílohu k aktuální zprávě", type=["png", "jpg", "jpeg", "pdf", "txt"], key="chat_up")
    
    if prompt := st.chat_input("Zeptejte se Gemini 3..."):
        # Zobrazení uživatelské zprávy
        with st.chat_message("user"):
            st.markdown(prompt)
        save_interaction("user", prompt)

        # Příprava dat pro Gemini
        history_gemini = []
        for _, row in cur_chat.tail(10).iterrows():
            history_gemini.append({"role": "user" if row["role"] == "user" else "model", "parts": [row["content"]]})
        
        current_parts = [prompt]
        
        # Přidání kontextu z Notebooku, pokud existuje (Grounding)
        if st.session_state.notebook_context:
            current_parts.append(f"\n\n(Kontext z nahraného dokumentu pro odpověď: {st.session_state.notebook_context[:10000]}...)")

        # Zpracování souboru přímo v chatu
        if chat_file:
            raw_data = chat_file.read()
            if chat_file.type in ["image/png", "image/jpeg", "image/jpg"]:
                 current_parts.append({"mime_type": chat_file.type, "data": raw_data})
            elif chat_file.type == "application/pdf":
                 # Pro chat jen extrahujeme text rychle
                 text_pdf = extract_text_from_file(chat_file)
                 current_parts.append(f"Obsah PDF souboru: {text_pdf}")
            else:
                 current_parts.append(raw_data.decode('utf-8'))

        # Volání AI
        with st.chat_message("assistant"):
            with st.spinner("Přemýšlím..."):
                ai_text = get_gemini_response(current_parts, history=history_gemini)
                st.markdown(ai_text)
        
        save_interaction("assistant", ai_text)
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
