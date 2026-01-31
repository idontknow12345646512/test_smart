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

# --- 1. KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="S.M.A.R.T. OS 2026", page_icon="🧬", layout="wide")

# --- 2. PŘIPOJENÍ SUPABASE ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Critical Database Error: {e}")
    st.stop()

# --- 3. CORE SYSTÉM (GEMINI 2.5 KERNEL) ---

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
    return {"display_name": "Uživatel", "theme": "dark", "ai_instructions": "", "response_length": "Střední"}

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

def process_audio_stream(audio_bytes, mime_type="audio/wav"):
    """
    Připraví nativní audio stream pro Gemini 2.5 Flash.
    Model 2.5 podporuje přímé zpracování waveform dat.
    """
    return [{"mime_type": mime_type, "data": audio_bytes}]

def render_native_audio_dialog(text_response):
    """
    Simulace Native Audio Output z Gemini 2.5.
    V reálném 2.5 API bychom dostali 'audio/pcm' blob.
    Zde používáme high-speed syntézu pro emulaci.
    """
    try:
        tts = gTTS(text=text_response, lang='cs')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        b64 = base64.b64encode(fp.read()).decode()
        # Autoplay HTML5 audio element - neviditelný, jen zvuk
        md = f"""
            <audio autoplay style="display:none;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)
    except Exception:
        pass

# --- FUNKCE CHATU ---
def create_chat(uid):
    nid = str(uuid.uuid4())[:8]
    supabase.table("chats").insert({"id": nid, "user_id": uid, "name": f"Chat {datetime.now().strftime('%H:%M')}"}).execute()
    return nid

def get_user_chats(uid):
    try:
        return supabase.table("chats").select("*").eq("user_id", uid).order("updated_at", desc=True).execute().data
    except: return []

def delete_chat(cid):
    supabase.table("messages").delete().eq("chat_id", cid).execute()
    supabase.table("chats").delete().eq("id", cid).execute()
    st.session_state.chat_id = None
    st.rerun()

def rename_chat(cid, name):
    supabase.table("chats").update({"name": name}).eq("id", cid).execute()
    st.rerun()

# --- 4. AUTENTIZACE ---
if "user" not in st.session_state:
    st.title("🧬 S.M.A.R.T. OS 2026")
    t1, t2 = st.tabs(["🔐 Login", "🧬 Register"])
    with t1:
        e = st.text_input("Email", key="le")
        p = st.text_input("Heslo", type="password", key="lp")
        if st.button("Connect", use_container_width=True):
            try:
                r = supabase.auth.sign_in_with_password({"email": e, "password": p})
                if r.user:
                    st.session_state.user = r.user
                    st.session_state.session = r.session
                    st.rerun()
            except: st.error("Access Denied")
    with t2:
        re = st.text_input("Email")
        rp = st.text_input("Heslo", type="password")
        rn = st.text_input("Jméno")
        if st.button("Initialize Identity"):
            try:
                supabase.auth.sign_up({"email": re, "password": rp, "options": {"data": {"display_name": rn}}})
                st.success("Identity Created")
            except Exception as x: st.error(x)
    st.stop()

init_session()
user_id = st.session_state.user.id
profile = get_profile(user_id)
display_name = profile.get("display_name")
current_theme = profile.get("theme", "dark")

# --- 5. UI SYSTEM 2026 ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: {'#050505' if current_theme == 'dark' else '#ffffff'}; }}
    [data-testid="stSidebar"] {{ background-color: {'#0a0a0a' if current_theme == 'dark' else '#f0f2f6'}; border-right: 1px solid #333; }}
    div[data-testid="stAudioInput"] {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 999; width: 300px; }}
    </style>
""", unsafe_allow_html=True)

# --- 6. SIDEBAR ---
with st.sidebar:
    st.image(f"https://api.dicebear.com/9.x/dylan/svg?seed={display_name}", width=60)
    st.markdown(f"**{display_name}**")
    st.caption("🟢 Online | Gemini 2.5 Kernel")
    
    if st.button("➕ Nový proces", use_container_width=True):
        st.session_state.chat_id = create_chat(user_id)
        st.rerun()

    st.subheader("Archiv")
    chats = get_user_chats(user_id)
    for c in chats:
        c1, c2 = st.columns([0.85, 0.15])
        if c1.button(c['name'], key=c['id'], use_container_width=True):
            st.session_state.chat_id = c['id']
            st.rerun()
        with c2.popover("⋮"):
            nn = st.text_input("Name", c['name'], key=f"n_{c['id']}")
            if st.button("Save", key=f"s_{c['id']}"): rename_chat(c['id'], nn)
            if st.button("Delete", key=f"d_{c['id']}"): delete_chat(c['id'])
            
    st.divider()
    native_audio = st.toggle("🔊 Native Audio Dialog", value=True, help="Zapne přímou hlasovou odezvu Gemini 2.5")
    
    if st.button("Odhlásit"):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# --- 7. MAIN INTERFACE ---
if not st.session_state.get("chat_id"):
    st.session_state.chat_id = create_chat(user_id) if not chats else chats[0]['id']

# Header & Context
st.title("💬 Native Audio Dialog")
with st.expander("📁 Multimodální kontext (Visual/Doc)"):
    up = st.file_uploader("Upload", type=["png","jpg","jpeg","webp","pdf","txt","docx"])
    vis_ctx = process_media(up) if up and up.type.startswith('image') else None
    doc_ctx = extract_text_from_file(up) if up and not up.type.startswith('image') else ""

# Chat History
try:
    msgs = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).order("created_at").execute().data
except: msgs = []

for m in msgs:
    with st.chat_message(m["role"]): st.markdown(m["content"])

# --- INPUT LOGIC (TEXT OR AUDIO) ---
# Input Area
col_txt, col_mic = st.columns([0.85, 0.15])
with col_txt:
    txt_in = st.chat_input("Příkaz...")
with col_mic:
    # Streamlit Audio Input Widget (Native in 2026/Streamlit 1.40+)
    aud_in = st.audio_input("🎙️")

final_prompt = None
native_audio_input = None

if txt_in:
    final_prompt = txt_in
elif aud_in:
    native_audio_input = process_audio_stream(aud_in.getvalue())
    final_prompt = "[Audio Stream Data]"

# --- PROCESSING ---
if final_prompt:
    # 1. User Message Display & Save
    with st.chat_message("user"):
        if aud_in: st.audio(aud_in)
        else: st.markdown(final_prompt)
    
    supabase.table("messages").insert({
        "chat_id": st.session_state.chat_id, "role": "user", 
        "content": final_prompt, "user_id": user_id
    }).execute()

    # 2. AI Processing
    genai.configure(api_key=rotate_api_key())
    
    # === GEMINI 2.5 FLASH NATIVE AUDIO CONFIG ===
    model_name = "gemini-2.5-flash"  # Explicitní verze pro rok 2026
    
    # System Instruction pro Audio Dialog
    sys_prompt = f"""
    {SMART_SYSTEM_INSTRUCTION}
    SYSTEM UPDATE 2026: Aktivován modul Gemini 2.5 Flash.
    MODE: Native Audio Dialog.
    Pokud dostaneš audio vstup, reaguj přirozenou konverzací.
    Uživatel: {display_name}.
    """
    if doc_ctx: sys_prompt += f"\nDATA: {doc_ctx[:5000]}"

    # Fallback na starší model, pokud by 2.5 v simulátoru (dnešku) nejel
    try:
        model = genai.GenerativeModel(model_name, system_instruction=sys_prompt)
    except:
        model = genai.GenerativeModel("gemini-2.0-flash-exp", system_instruction=sys_prompt)

    # Historie
    hist = [{"role": "user" if m["role"]=="user" else "model", "parts": [m["content"]]} for m in msgs]
    
    with st.spinner("⚡ Gemini 2.5 Processing Neural Audio..."):
        try:
            input_payload = []
            
            # Pokud je aktivní Audio Dialog, posíláme bajty
            if native_audio_input:
                input_payload.extend(native_audio_input)
                # Prompt pro model, aby věděl, že má zpracovat audio
                input_payload.append("Listen to this audio stream and respond in Czech.")
            else:
                input_payload.append(final_prompt)
            
            if vis_ctx: input_payload.extend(vis_ctx)

            chat = model.start_chat(history=hist)
            response = chat.send_message(input_payload)
            ai_output = response.text
            
        except Exception as e:
            ai_output = f"Neural Link Error: {e}"

    # 3. AI Output Display & Save
    with st.chat_message("assistant"):
        st.markdown(ai_output)
        
        # === NATIVE AUDIO DIALOG OUTPUT ===
        # Pokud je zapnuto v sidebaru, simulujeme přímý audio výstup
        if native_audio:
            render_native_audio_dialog(ai_output)

    supabase.table("messages").insert({
        "chat_id": st.session_state.chat_id, "role": "assistant", 
        "content": ai_output, "user_id": user_id
    }).execute()
    
    # Refresh pro plynulost dialogu
    time.sleep(0.5)
    st.rerun()