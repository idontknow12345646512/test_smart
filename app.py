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

from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. KONFIGURACE STRÁNKY & CYBERPUNK DESIGN ---
st.set_page_config(page_title="S.M.A.R.T. OS 2026", page_icon="🧬", layout="wide")

if "processing" not in st.session_state: st.session_state.processing = False
if "last_processed_audio" not in st.session_state: st.session_state.last_processed_audio = None
if "v_counter" not in st.session_state: st.session_state.v_counter = 0

# --- KOMPLETNÍ TUNING UI (CSS ANIMACE A DESIGN) ---
st.markdown("""
    <style>
    /* Hlavní vizuál systému */
    .stApp {
        background: radial-gradient(circle at 50% 50%, #0d0d1a 0%, #050505 100%);
        color: #e0e0ff;
        font-family: 'Inter', sans-serif;
    }
    
    /* Animovaný Glow efekt pro statusy */
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

    /* Skleněný Sidebar (Glassmorphism) */
    [data-testid="stSidebar"] {
        background-color: rgba(10, 10, 20, 0.7) !important;
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(0, 242, 255, 0.1);
    }

    /* Tuněné chatové bubliny */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px !important;
        margin-bottom: 10px;
        transition: all 0.3s ease;
    }
    .stChatMessage:hover {
        transform: translateY(-2px);
        border: 1px solid rgba(0, 242, 255, 0.3);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
    }

    /* Stylizace tlačítek */
    .stButton>button {
        border-radius: 12px;
        border: 1px solid rgba(0, 242, 255, 0.3);
        background: rgba(0, 242, 255, 0.05);
        color: #00f2ff;
        font-weight: 600;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: rgba(0, 242, 255, 0.2);
        box-shadow: 0 0 20px rgba(0, 242, 255, 0.4);
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. PŘIPOJENÍ SUPABASE ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Critical Database Error: {e}")
    st.stop()

# --- 3. POMOCNÉ FUNKCE (KERNELY) ---

def init_session():
    if "session" in st.session_state:
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
    except: pass
    return {"display_name": "Uživatel", "theme": "dark"}

def rotate_api_key():
    keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    valid = [k for k in keys if k]
    return random.choice(valid) if valid else None

def process_media(uploaded_file):
    if uploaded_file.type.startswith('image/'):
        img = Image.open(uploaded_file).convert("RGB")
        b = io.BytesIO()
        img.save(b, format='JPEG')
        return [{"mime_type": "image/jpeg", "data": b.getvalue()}]
    return None

def render_native_audio_dialog(text_response):
    """OPRAVENO: Generuje hlas a dynamicky počítá čas pro dočtení CELÉ zprávy."""
    try:
        tts = gTTS(text=text_response, lang='cs')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        b64 = base64.b64encode(fp.read()).decode()
        
        # Vložení audio elementu
        st.markdown(f'<audio autoplay style="display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)
        
        # DYNAMICKÝ VÝPOČET ČASU: 
        # Průměrná rychlost řeči je cca 150 slov za minutu -> cca 0.4s na slovo. 
        # Přidáváme rezervu pro interpunkci.
        words_count = len(text_response.split())
        estimated_seconds = (words_count * 0.5) + 1.5 
        return estimated_seconds
    except:
        return 0

# --- 4. SPRÁVA CHATŮ ---
def create_chat(uid):
    nid = str(uuid.uuid4())[:8]
    supabase.table("chats").insert({"id": nid, "user_id": uid, "name": f"Relace {datetime.now().strftime('%H:%M')}"}).execute()
    return nid

def delete_chat(cid):
    supabase.table("messages").delete().eq("chat_id", cid).execute()
    supabase.table("chats").delete().eq("id", cid).execute()
    st.session_state.chat_id = None
    st.rerun()

def rename_chat(cid, name):
    supabase.table("chats").update({"name": name}).eq("id", cid).execute()
    st.rerun()

# --- 5. AUTENTIZACE ---
if "user" not in st.session_state:
    st.title("S.M.A.R.T. OS Beta")
    t1, t2 = st.tabs(["Přihlásit se", "Zaregistrovat se"])
    with t1:
        e = st.text_input("Email", key="auth_e")
        p = st.text_input("Heslo", type="password", key="auth_p")
        if st.button("Přihlásit se", use_container_width=True):
            try:
                r = supabase.auth.sign_in_with_password({"email": e, "password": p})
                if r.user:
                    st.session_state.user = r.user
                    st.session_state.session = r.session
                    st.rerun()
            except: st.error("Zadali jste špatně Email nebo heslo.")
    with t2:
        re = st.text_input("Nový Email")
        rp = st.text_input("Nové heslo", type="password")
        rn = st.text_input("Jméno (Přezdívka)")
        if st.button("Zaregistrovat"):
            try:
                supabase.auth.sign_up({"email": re, "password": rp, "options": {"data": {"display_name": rn}}})
                st.success("Účrt vytvořen. Nyní se vraťte do záložky Přihlásit se a přihlašte se.")
            except Exception as x: st.error(x)
    st.stop()

init_session()
user_id = st.session_state.user.id
profile = get_profile(user_id)
display_name = profile.get("display_name")

# --- 6. SIDEBAR ---
with st.sidebar:
    st.image(f"https://api.dicebear.com/9.x/bottts-neutral/svg?seed={display_name}", width=80)
    st.markdown(f"### {display_name}")
    st.caption("Gemini 2.5")
    
    app_mode = st.radio("Režim", ["Chat", "Hlasový režim (2.5)"])
    use_web_search = st.toggle("Vyhledávání na iternetu", value=False)
    
    st.divider()
    if st.button("Nový chat", use_container_width=True):
        st.session_state.chat_id = create_chat(user_id)
        st.rerun()

    st.subheader("Historie chatů")
    chats = supabase.table("chats").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute().data
    for c in chats:
        c1, c2 = st.columns([0.8, 0.2])
        if c1.button(c['name'], key=f"btn_{c['id']}", use_container_width=True):
            st.session_state.chat_id = c['id']
            st.rerun()
        with c2.popover("⋮"):
            nn = st.text_input("Název", c['name'], key=f"rename_{c['id']}")
            if st.button("Uložit", key=f"save_{c['id']}"): rename_chat(c['id'], nn)
            if st.button("Smazat", key=f"del_{c['id']}"): delete_chat(c['id'])
            
    st.divider()
    native_audio = st.toggle("Číst zprávy nahlas", value=False)
    if st.button("Odhlásit se"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# --- 7. HLAVNÍ ROZHRANÍ ---
if not st.session_state.get("chat_id"):
    st.session_state.chat_id = chats[0]['id'] if chats else create_chat(user_id)

# Konfigurace Gemini s Vyhledáváním
genai.configure(api_key=rotate_api_key())
model_tools = [{"google_search_retrieval": {}}] if use_web_search else None
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", 
    system_instruction=SMART_SYSTEM_INSTRUCTION,
    tools=model_tools
)

# --- MÓD 1: NATIVE VOICE TERMINAL (Opraveno) ---
# Důležité: String v podmínce musí přesně sedět na název v radio buttonu v sidebaru
if app_mode == "Hlasový režim(2.5)":
    st.markdown("<h2 style='text-align: center;'>Hlasový režim</h2>", unsafe_allow_html=True)
    st.info("Klikněte na mikrofon a začněte mluvit.")
    
    cols = st.columns([1, 2, 1])
    with cols[1]:
        # Používáme v_counter, aby se mikrofon po každé odpovědi vyresetoval
        v_mic_key = f"v_mic_{st.session_state.v_counter}"
        voice_in = st.audio_input("Poslouchám...", key=v_mic_key)

    if voice_in and not st.session_state.processing:
        st.session_state.processing = True
        
        # Animovaný status bar z našeho nového UI
        with st.status("Přemýšlím...", expanded=True):
            try:
                # Příprava dat pro Gemini
                audio_payload = [{"mime_type": "audio/wav", "data": voice_in.getvalue()}]
                
                # Generování odpovědi (model už máš definovaný výše s vyhledáváním)
                response = model.generate_content(audio_payload + ["Jsi S.M.A.R.T. OS. Odpověz stručně, přirozeně a česky."])
                ai_text = response.text
                
                # Zobrazení odpovědi
                st.write(f" **S.M.A.R.T.:** {ai_text}")
                
                # HLASOVÝ VÝSTUP (Teď už s tvým novým opravným čekáním)
                wait = render_native_audio_dialog(ai_text) if native_audio else 0
                
                # Uložení do databáze
                supabase.table("messages").insert({
                    "chat_id": st.session_state.chat_id, 
                    "role": "assistant", 
                    "content": f"[Voice Mode]: {ai_text}", 
                    "user_id": user_id
                }).execute()
                
                # Klíčová pauza, aby dozněl hlas, než se zavře status a udělá rerun
                time.sleep(wait)
                
            except Exception as e:
                st.error(f"Chyba hlasového modulu: {e}")
        
        # Posuneme counter pro reset mikrofonu a uvolníme zámek processing
        st.session_state.v_counter += 1
        st.session_state.processing = False
        st.rerun()

# --- MÓD 2: MULTIMODÁLNÍ CHAT ---
else:
    st.title("Smart AI")
    chat_container = st.container()

    with st.expander("Nahrajte soubory, obrázky"):
        up = st.file_uploader("Nahrát soubor", type=["png","jpg","jpeg","webp","pdf","txt","docx"])
        vis_ctx = process_media(up) if up and up.type.startswith('image') else None
        doc_ctx = extract_text_from_file(up) if up and not up.type.startswith('image') else ""

    # Vykreslení historie
    try:
        msgs = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).order("created_at").execute().data
    except: msgs = []

    with chat_container:
        for m in msgs:
            with st.chat_message(m["role"]): st.markdown(m["content"])

    # Vstupy
    col_t, col_m = st.columns([0.85, 0.15])
    with col_t: txt_in = st.chat_input("Napište zprávu...")
    with col_m: aud_in = st.audio_input("", key=f"chat_mic_{len(msgs)}")

    # Logika detekce vstupu
    final_prompt = None
    audio_data = None
    if not st.session_state.processing:
        if txt_in:
            final_prompt = txt_in
        elif aud_in and aud_in.getvalue() != st.session_state.last_processed_audio:
            audio_data = [{"mime_type": "audio/wav", "data": aud_in.getvalue()}]
            st.session_state.last_processed_audio = aud_in.getvalue()
            final_prompt = "[Hlasová zpráva]"

    if final_prompt:
        st.session_state.processing = True
        with chat_container:
            with st.chat_message("user"):
                if audio_data: st.audio(aud_in)
                else: st.markdown(final_prompt)
        
        # Zápis do DB
        supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "user", "content": final_prompt, "user_id": user_id}).execute()

        with chat_container:
            with st.chat_message("assistant"):
                status_txt = "Prohledávám web..." if use_web_search else "Přemýšlím..."
                with st.status(status_txt):
                    # Historie pro kontext
                    hist = [{"role": "user" if m["role"]=="user" else "model", "parts": [m["content"]]} for m in msgs]
                    payload = audio_data + ["Odpověz v CZ."] if audio_data else [final_prompt]
                    if vis_ctx: payload.extend(vis_ctx)
                    if doc_ctx: payload.append(f"KONTEXT DOKUMENTU: {doc_ctx[:4000]}")
                    
                    chat_session = model.start_chat(history=hist)
                    response = chat_session.send_message(payload)
                    ai_reply = response.text
                
                st.markdown(ai_reply)
                
                # Hlasový výstup
                wait_time = render_native_audio_dialog(ai_reply) if native_audio else 0
                
                # Uložení odpovědi
                supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "assistant", "content": ai_reply, "user_id": user_id}).execute()
                
                time.sleep(wait_time)

        st.session_state.processing = False
        st.rerun()