import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
from datetime import datetime
import time
import random
from PIL import Image
import io

# Pokusíme se importovat podporu pro HEIC
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- 1. KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="🤖", layout="wide")

# --- 2. PŘIPOJENÍ SUPABASE ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Chyba připojení k databázi: {e}")
    st.stop()

# --- 3. POMOCNÉ FUNKCE ---

def init_session():
    if "session" in st.session_state:
        try:
            supabase.auth.set_session(
                st.session_state.session.access_token, 
                st.session_state.session.refresh_token
            )
        except Exception:
            st.warning("Relace vypršela. Přihlaste se prosím znovu.")
            if "user" in st.session_state: del st.session_state.user
            if "session" in st.session_state: del st.session_state.session
            st.rerun()

def get_profile(uid):
    try:
        res = supabase.table("profiles").select("*").eq("id", uid).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return {"display_name": "Uživatel", "theme": "dark", "ai_instructions": "", "response_length": "Střední"}

def rotate_api_key():
    keys = [st.secrets.get(f"GOOGLE_API_KEY_{i}") for i in range(1, 11)]
    valid_keys = [k for k in keys if k]
    if not valid_keys:
        st.error("Chybí API klíče v secrets!")
        st.stop()
    return random.choice(valid_keys)

def process_media(uploaded_file):
    if uploaded_file.type.startswith('image/'):
        img = Image.open(uploaded_file)
        img_byte_arr = io.BytesIO()
        img.convert("RGB").save(img_byte_arr, format='JPEG')
        return [{"mime_type": "image/jpeg", "data": img_byte_arr.getvalue()}]
    return None

# --- FUNKCE PRO SPRÁVU CHATŮ ---

def get_user_chats(uid):
    try:
        res = supabase.table("chats").select("*").eq("user_id", uid).order("updated_at", desc=True).execute()
        return res.data
    except:
        return []

def create_chat(uid, name="Nový chat"):
    new_id = str(uuid.uuid4())[:8]
    supabase.table("chats").insert({"id": new_id, "user_id": uid, "name": name}).execute()
    return new_id

def delete_chat(chat_id):
    supabase.table("messages").delete().eq("chat_id", chat_id).execute()
    supabase.table("chats").delete().eq("id", chat_id).execute()
    if st.session_state.chat_id == chat_id:
        st.session_state.chat_id = None
    st.rerun()

def rename_chat(chat_id, new_name):
    supabase.table("chats").update({"name": new_name}).eq("id", chat_id).execute()
    st.rerun()

# --- 4. AUTENTIZACE ---

if "user" not in st.session_state:
    st.title("🤖 S.M.A.R.T. OS")
    tab1, tab2 = st.tabs(["🔐 Přihlášení", "✨ Vytvořit účet"])
    with tab1:
        email = st.text_input("Email", key="log_email")
        password = st.text_input("Heslo", type="password", key="log_pass")
        if st.button("Vstoupit do systému", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state.user = res.user
                    st.session_state.session = res.session
                    st.rerun()
            except: st.error("Chyba přihlášení.")
    with tab2:
        reg_name = st.text_input("Jak vám mám říkat?")
        reg_email = st.text_input("Registrační Email")
        reg_pass = st.text_input("Heslo", type="password")
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": reg_email, "password": reg_pass, "options": {"data": {"display_name": reg_name}}})
                st.success("Účet vytvořen!")
            except Exception as e: st.error(f"Chyba: {e}")
    st.stop()

init_session()
user_id = st.session_state.user.id
profile = get_profile(user_id)
display_name = profile.get("display_name") or "Uživatel"
current_theme = profile.get("theme", "dark")

# --- 5. STYLOVÁNÍ ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: {'#0e1117' if current_theme == 'dark' else '#ffffff'}; }}
    [data-testid="stSidebar"] {{ background-color: {'#161b22' if current_theme == 'dark' else '#f0f2f6'}; }}
    .chat-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- 6. SIDEBAR (HISTORIE CHATŮ) ---
with st.sidebar:
    st.image(f"https://api.dicebear.com/7.x/bottts/svg?seed={display_name}", width=80)
    st.subheader(f"Ahoj, {display_name}")
    
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.chat_id = create_chat(user_id)
        st.session_state.page = "chat"
        st.rerun()

    st.divider()
    st.write("📜 Moje Chaty")
    user_chats = get_user_chats(user_id)
    
    for chat in user_chats:
        col_name, col_menu = st.columns([0.8, 0.2])
        with col_name:
            if st.button(chat['name'], key=f"sel_{chat['id']}", use_container_width=True):
                st.session_state.chat_id = chat['id']
                st.session_state.page = "chat"
                st.rerun()
        with col_menu:
            # Tři tečky jako popover (Streamlit native "tečky" menu)
            with st.popover("⋮"):
                new_name = st.text_input("Přejmenovat", value=chat['name'], key=f"ren_{chat['id']}")
                if st.button("Uložit název", key=f"save_{chat['id']}"):
                    rename_chat(chat['id'], new_name)
                
                # Download
                chat_msgs = supabase.table("messages").select("role,content").eq("chat_id", chat['id']).order("created_at").execute().data
                txt_content = "\n".join([f"{m['role']}: {m['content']}" for m in chat_msgs])
                st.download_button("📥 Stáhnout TXT", txt_content, file_name=f"{chat['name']}.txt", key=f"dl_{chat['id']}")
                
                if st.button("🗑️ Smazat chat", key=f"del_{chat['id']}", type="primary"):
                    delete_chat(chat['id'])

    st.divider()
    if st.button("⚙️ Nastavení", use_container_width=True):
        st.session_state.page = "settings"
        st.rerun()
    if st.button("🚪 Odhlásit se", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.rerun()

# --- 7. HLAVNÍ OBSAH ---

if st.session_state.get("page") == "settings":
    st.title("⚙️ Nastavení systému")
    # ... (Zůstává stejné jako ve tvém kódu) ...
    if st.button("Zpět k chatu"):
        st.session_state.page = "chat"
        st.rerun()

else:
    if not st.session_state.get("chat_id"):
        # Pokud není vybrán chat, zkus vybrat poslední nebo vytvořit nový
        if user_chats:
            st.session_state.chat_id = user_chats[0]['id']
        else:
            st.session_state.chat_id = create_chat(user_id)
    
    # Získání názvu aktuálního chatu
    current_chat_name = next((c['name'] for c in user_chats if c['id'] == st.session_state.chat_id), "Chat")
    st.title(f"💬 {current_chat_name}")

    # Nahrávání souborů v chatu
    with st.expander("📁 Přiložit data k této zprávě"):
        uploaded_file = st.file_uploader("Obrázek nebo dokument", type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "webp", "heic"])
    
    doc_context = ""
    visual_context = None
    if uploaded_file:
        if uploaded_file.type.startswith('image/'):
            visual_context = process_media(uploaded_file)
            st.image(uploaded_file, width=200)
        else:
            doc_context = extract_text_from_file(uploaded_file)

    # Načtení zpráv
    try:
        msgs = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).order("created_at").execute().data
    except: msgs = []

    for m in msgs:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Napište zprávu..."):
        st.chat_message("user").markdown(prompt)
        supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "user", "content": prompt, "user_id": user_id}).execute()
        # Aktualizace času v tabulce chats
        supabase.table("chats").update({"updated_at": "now()"}).eq("id", st.session_state.chat_id).execute()

        genai.configure(api_key=rotate_api_key())
        len_prompt = {"Krátká": "stručný", "Střední": "vyvážený", "Dlouhá": "velmi detailní"}.get(profile.get("response_length"), "vyvážený")

        final_system_prompt = f"{SMART_SYSTEM_INSTRUCTION}\nUživatele oslovuj: {display_name}.\nStyl: {len_prompt}."
        if doc_context: final_system_prompt += f"\n\nKONTEXT SOUBORU:\n{doc_context[:15000]}"

        model = genai.GenerativeModel("gemini-2.0-flash-exp", system_instruction=final_system_prompt)
        gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in msgs]
        
        with st.spinner("🚀 Analyzuji..."):
            try:
                message_parts = [prompt]
                if visual_context: message_parts.extend(visual_context)
                chat_session = model.start_chat(history=gem_hist)
                response = chat_session.send_message(message_parts)
                ai_text = response.text
            except Exception as e: ai_text = f"Chyba AI: {e}"

        with st.chat_message("assistant"): st.markdown(ai_text)
        supabase.table("messages").insert({"chat_id": st.session_state.chat_id, "role": "assistant", "content": ai_text, "user_id": user_id}).execute()
        st.rerun()