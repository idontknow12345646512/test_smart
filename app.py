import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
from datetime import datetime
import time
import random
from PIL import Image
import io
import base64
from gtts import gTTS

# --- 0. HARDWARE AKCELERACE & IMPORTY (2026) ---
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# Importy tvých vlastních modulů
try:
    from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION
except ImportError:
    SMART_SYSTEM_INSTRUCTION = "Jsi S.M.A.R.T. OS 2026."
    def extract_text_from_file(f): return ""

# --- 1. KONFIGURACE STRÁNKY & KOMPLETNÍ CYBER DESIGN ---
st.set_page_config(
    page_title="S.M.A.R.T. OS 2026", 
    page_icon="🧬", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializace stavů pro stabilitu UI (nezbytné pro rerun cykly)
if "processing" not in st.session_state:
    st.session_state.processing = False
if "last_processed_audio" not in st.session_state:
    st.session_state.last_processed_audio = None
if "v_counter" not in st.session_state:
    st.session_state.v_counter = 0
if "chat_id" not in st.session_state:
    st.session_state.chat_id = None

# --- PLNOTUČNÝ CSS TUNING (Zpět na plný počet řádků) ---
st.markdown("""
    <style>
    /* Hlavní kontejner aplikace */
    .stApp {
        background: radial-gradient(circle at 50% 50%, #0d0d1a 0%, #050505 100%);
        color: #e0e0ff;
    }
    
    /* Neonové animované statusy a widgety */
    .stStatusWidget {
        border: 1px solid #00f2ff !important;
        box-shadow: 0 0 15px rgba(0, 242, 255, 0.2);
        animation: glow 2s infinite alternate;
        background: rgba(0, 242, 255, 0.05) !important;
    }
    
    @keyframes glow {
        from { box-shadow: 0 0 5px rgba(0, 242, 255, 0.2); }
        to { box-shadow: 0 0 20px rgba(0, 242, 255, 0.5); }
    }

    /* Skleněný efekt pro Sidebar */
    [data-testid="stSidebar"] {
        background-color: rgba(10, 10, 20, 0.8) !important;
        backdrop-filter: blur(25px);
        border-right: 1px solid rgba(0, 242, 255, 0.15);
    }

    /* Vylepšené bubliny chatu s hloubkou */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px !important;
        padding: 15px !important;
        margin-bottom: 12px;
        transition: transform 0.2s ease, border 0.2s ease;
    }
    .stChatMessage:hover {
        transform: translateY(-2px);
        border: 1px solid rgba(0, 242, 255, 0.3);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }

    /* Tlačítka s neonovým lemováním */
    .stButton>button {
        border-radius: 14px;
        border: 1px solid rgba(0, 242, 255, 0.4);
        background: rgba(0, 242, 255, 0.07);
        color: #00f2ff;
        font-weight: 500;
        width: 100%;
        transition: 0.3s all;
    }
    .stButton>button:hover {
        background: rgba(0, 242, 255, 0.2);
        box-shadow: 0 0 15px rgba(0, 242, 255, 0.5);
    }
    
    /* Vstupní pole */
    .stChatInputContainer {
        padding-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. PŘIPOJENÍ SUPABASE ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Kritická chyba databáze: {e}")
    st.stop()

# --- 3. CORE FUNKCE SYSTÉMU ---

def init_session():
    if "session" in st.session_state and st.session_state.session:
        try:
            supabase.auth.set_session(
                st.session_state.session.access_token, 
                st.session_state.session.refresh_token
            )
        except Exception:
            if "user" in st.session_state: del st.session_state.user
            st.rerun()

def get_profile(uid):
    try:
        res = supabase.table("profiles").select("*").eq("id", uid).execute()
        if res.data: return res.data[0]
    except Exception:
        pass
    return {"display_name": "Uživatel", "theme": "dark"}

def rotate_api_key():
    keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    valid_keys = [k for k in keys if k]
    return random.choice(valid_keys) if valid_keys else None

def process_media(uploaded_file):
    if uploaded_file.type.startswith('image/'):
        img = Image.open(uploaded_file).convert("RGB")
        b = io.BytesIO()
        img.save(b, format='JPEG')
        return [{"mime_type": "image/jpeg", "data": b.getvalue()}]
    return None

def render_native_audio_dialog(text_response):
    """Generuje hlas a vrací přesný čas čekání, aby se audio nepřerušilo."""
    try:
        tts = gTTS(text=text_response, lang='cs')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        b64 = base64.b64encode(fp.read()).decode()
        
        # Audio tag s automatickým spuštěním
        audio_html = f'<audio autoplay style="display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        st.markdown(audio_html, unsafe_allow_html=True)
        
        # Výpočet času: slova * koeficient + rezerva
        words = len(text_response.split())
        wait_time = (words * 0.48) + 1.8
        return wait_time
    except Exception as e:
        st.warning(f"Audio Error: {e}")
        return 0

# --- 4. SPRÁVA CHATŮ (CRUD) ---

def create_chat(uid):
    nid = str(uuid.uuid4())[:8]
    now = datetime.now().strftime('%H:%M')
    try:
        supabase.table("chats").insert({
            "id": nid, 
            "user_id": uid, 
            "name": f"Relace {now}"
        }).execute()
        return nid
    except Exception as e:
        st.error(f"Chyba při tvorbě chatu: {e}")
        return None

def get_user_chats(uid):
    try:
        res = supabase.table("chats").select("*").eq("user_id", uid).order("updated_at", desc=True).execute()
        return res.data
    except Exception:
        return []

def delete_chat(cid):
    try:
        supabase.table("messages").delete().eq("chat_id", cid).execute()
        supabase.table("chats").delete().eq("id", cid).execute()
        st.session_state.chat_id = None
        st.rerun()
    except Exception as e:
        st.error(f"Chyba při mazání: {e}")

def rename_chat(cid, name):
    try:
        supabase.table("chats").update({"name": name}).eq("id", cid).execute()
        st.rerun()
    except Exception as e:
        st.error(f"Chyba při přejmenování: {e}")

# --- 5. AUTENTIZACE A IDENTITA ---

if "user" not in st.session_state:
    st.title("🧬 S.M.A.R.T. OS 2026")
    tab_login, tab_reg = st.tabs(["🔐 Přihlášení", "🧬 Inicializace Identity"])
    
    with tab_login:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Heslo", type="password", key="l_pass")
        if st.button("Vstoupit do systému", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state.user = res.user
                    st.session_state.session = res.session
                    st.rerun()
            except Exception:
                st.error("Přístup odepřen. Neplatné přihlašovací údaje.")
                
    with tab_reg:
        r_email = st.text_input("Email", key="r_email")
        r_pass = st.text_input("Heslo", type="password", key="r_pass")
        r_name = st.text_input("Jméno uživatele", key="r_name")
        if st.button("Vytvořit identitu", use_container_width=True):
            try:
                supabase.auth.sign_up({
                    "email": r_email, 
                    "password": r_pass, 
                    "options": {"data": {"display_name": r_name}}
                })
                st.success("Identita vytvořena. Zkontrolujte email nebo se přihlaste.")
            except Exception as e:
                st.error(f"Chyba registrace: {e}")
    st.stop()

init_session()
user_id = st.session_state.user.id
user_profile = get_profile(user_id)
user_name = user_profile.get("display_name", "Uživatel")

# --- 6. SIDEBAR ARCHITEKTURA ---

with st.sidebar:
    # Avatar a Status
    st.image(f"https://api.dicebear.com/9.x/bottts-neutral/svg?seed={user_name}", width=90)
    st.markdown(f"### {user_name}")
    st.caption("🟢 Jádro Gemini 2.5 | Systém Aktivní")
    
    # Ovládací prvky
    st.divider()
    app_mode = st.radio("Mód systému:", ["💬 Multimodální Chat", "🎙️ Native Voice Mode (2.5)"])
    web_search_enabled = st.toggle("🌐 Web Search Retrieval", value=True)
    voice_output_enabled = st.toggle("🔊 Hlasová syntéza", value=True)
    
    # Správa procesů
    st.divider()
    if st.button("➕ Nový proces (Relace)", use_container_width=True):
        st.session_state.chat_id = create_chat(user_id)
        st.rerun()

    st.subheader("Archiv relací")
    user_chats = get_user_chats(user_id)
    for chat in user_chats:
        col_btn, col_pop = st.columns([0.8, 0.2])
        if col_btn.button(chat['name'], key=f"chat_{chat['id']}", use_container_width=True):
            st.session_state.chat_id = chat['id']
            st.rerun()
        
        with col_pop.popover("⋮"):
            new_name = st.text_input("Přejmenovat", chat['name'], key=f"ren_{chat['id']}")
            if st.button("Uložit", key=f"save_{chat['id']}"):
                rename_chat(chat['id'], new_name)
            if st.button("Smazat", key=f"del_{chat['id']}", type="primary"):
                delete_chat(chat['id'])
            
    st.divider()
    if st.button("Odhlásit se", type="secondary"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# --- 7. CORE AI LOGIKA (GEMINI 2.5 KERNEL) ---

if not st.session_state.chat_id:
    st.session_state.chat_id = user_chats[0]['id'] if user_chats else create_chat(user_id)

# Konfigurace Modelu s vyhledáváním
genai.configure(api_key=rotate_api_key())
tools_list = [{"google_search_retrieval": {}}] if web_search_enabled else None

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", 
    system_instruction=SMART_SYSTEM_INSTRUCTION,
    tools=tools_list
)

# --- MÓD 1: NATIVE VOICE TERMINAL (Opraveno na 🎙️) ---

if app_mode == "🎙️ Native Voice Mode (2.5)":
    st.markdown("<h2 style='text-align: center;'>🎙️ Native Voice Terminal</h2>", unsafe_allow_html=True)
    st.info("Systém je v režimu přímého poslechu. Klikněte na mikrofon a mluvte.")
    
    cols = st.columns([1, 2, 1])
    with cols[1]:
        v_mic_key = f"v_mic_{st.session_state.v_counter}"
        voice_input = st.audio_input("Naslouchám...", key=v_mic_key)

    if voice_input and not st.session_state.processing:
        st.session_state.processing = True
        with st.status("🧠 Jádro analyzuje hlasový vstup...", expanded=True):
            try:
                audio_payload = [{"mime_type": "audio/wav", "data": voice_input.getvalue()}]
                response = model.generate_content(audio_payload + ["Jsi S.M.A.R.T. OS. Odpověz stručně a česky."])
                ai_text = response.text
                
                st.write(f"🧬 **S.M.A.R.T.:** {ai_text}")
                
                # Hlasový výstup
                wait = render_native_audio_dialog(ai_text) if voice_output_enabled else 0
                
                # Uložení do DB
                supabase.table("messages").insert({
                    "chat_id": st.session_state.chat_id, "role": "assistant", 
                    "content": f"[Voice Mode]: {ai_text}", "user_id": user_id
                }).execute()
                
                time.sleep(wait)
            except Exception as e:
                st.error(f"Chyba AI: {e}")
        
        st.session_state.v_counter += 1
        st.session_state.processing = False
        st.rerun()

# --- MÓD 2: MULTIMODÁLNÍ CHAT ---

else:
    st.title("💬 Multimodální S.M.A.R.T. Chat")
    chat_win = st.container()

    # Přílohy a dokumenty
    with st.expander("📁 Přidat kontext (Obrázky / Dokumenty)"):
        uploaded_file = st.file_uploader("Nahrát soubor", type=["png","jpg","jpeg","webp","pdf","txt","docx"])
        media_ctx = process_media(uploaded_file) if uploaded_file and uploaded_file.type.startswith('image') else None
        doc_ctx = extract_text_from_file(uploaded_file) if uploaded_file and not uploaded_file.type.startswith('image') else ""

    # Historie zpráv
    try:
        messages = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).order("created_at").execute().data
    except Exception:
        messages = []

    with chat_win:
        for m in messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

    # Vstupní rozhraní
    col_input, col_mic = st.columns([0.88, 0.12])
    with col_input:
        text_input = st.chat_input("Zadejte příkaz nebo otázku...")
    with col_mic:
        m_key = f"mic_{st.session_state.chat_id}_{len(messages)}"
        audio_input = st.audio_input("🎙️", key=m_key)

    # Detekce aktivity
    final_query = None
    audio_data = None
    
    if not st.session_state.processing:
        if text_input:
            final_query = text_input
        elif audio_input and audio_input.getvalue() != st.session_state.last_processed_audio:
            audio_data = [{"mime_type": "audio/wav", "data": audio_input.getvalue()}]
            st.session_state.last_processed_audio = audio_input.getvalue()
            final_query = "[Hlasová zpráva]"

    if final_query:
        st.session_state.processing = True
        
        # Okamžité zobrazení dotazu
        with chat_win:
            with st.chat_message("user"):
                if audio_data: st.audio(audio_input)
                else: st.markdown(final_query)
        
        # DB zápis dotazu
        supabase.table("messages").insert({
            "chat_id": st.session_state.chat_id, "role": "user", 
            "content": final_query, "user_id": user_id
        }).execute()

        with chat_win:
            with st.chat_message("assistant"):
                label = "🌐 Prohledávám web..." if web_search_enabled else "🧬 Jádro..."
                
                with st.status(label) as status:
                    # 1. PŘÍPRAVA HISTORIE (Zpětná kompatibilita)
                    gemini_history = []
                    for msg in messages[-10:]:
                        m_role = "user" if msg["role"] == "user" else "model"
                        # Gemini 2.5 vyžaduje, aby parts byl list stringů
                        gemini_history.append({"role": m_role, "parts": [str(msg["content"])]})
                    
                    # 2. KONSTRUKCE PAYLOADU
                    # Musíme zajistit, že v payloadu není nic jiného než povolené typy (text/blob)
                    safe_query = str(final_query) if final_query else "Pokračuj"
                    
                    current_payload = []
                    # Pokud máme audio, vložíme ho jako první
                    if audio_data:
                        current_payload.extend(audio_data)
                    
                    # Přidáme textový dotaz
                    current_payload.append(safe_query)
                    
                    # Přidáme vizuální kontext
                    if media_ctx:
                        current_payload.extend(media_ctx)
                    
                    # Přidáme dokument
                    if doc_ctx:
                        current_payload.append(f"KONTEXT: {str(doc_ctx)[:2000]}")

                    # 3. SAMOTNÉ VOLÁNÍ (S FINÁLNÍM FALLBACKEM)
                    try:
                        # VŽDY používáme start_chat, pokud máme definované tools
                        chat_session = model.start_chat(history=gemini_history)
                        response = chat_session.send_message(current_payload)
                        ai_response_text = response.text
                    except Exception as e:
                        # TOTÁLNÍ FALLBACK: 
                        # Pokud selže chat i tools, vytvoříme na vteřinu model BEZ TOOLS
                        # To zaručí, že odpověď dostaneš, i kdyby Google Search API mělo výpadek
                        fallback_model = genai.GenerativeModel(model_name="gemini-2.5-flash")
                        # Posíláme čistý string, žádný list
                        response = fallback_model.generate_content(safe_query)
                        ai_response_text = response.text
                    
                    status.update(label="🧬 Odpověď vygenerována", state="complete")

                # --- VÝSTUP ---
                st.markdown(ai_response_text)
                
                # Zvuková syntéza
                wait_seconds = 0
                if voice_output_enabled and ai_response_text:
                    wait_seconds = render_native_audio_dialog(ai_response_text)
                
                # DB zápis
                try:
                    supabase.table("messages").insert({
                        "chat_id": st.session_state.chat_id, 
                        "role": "assistant", 
                        "content": ai_response_text, 
                        "user_id": user_id
                    }).execute()
                except:
                    pass
                
                time.sleep(wait_seconds)

        st.session_state.processing = False
        st.rerun()