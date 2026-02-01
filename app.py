import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
import random
import io
import base64
import requests
from PIL import Image
from gtts import gTTS
from shared import extract_text_from_file, SMART_SYSTEM_INSTRUCTION

# --- KONFIGURACE ---
st.set_page_config(page_title="S.M.A.R.T. OS", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e0e10; color: #e3e3e3; }
    [data-testid="stSidebar"] { background-color: #171719; border-right: 1px solid #333; }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    #MainMenu, footer, header { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- KLÍČE & ROTACE ---
def get_all_keys():
    return [st.secrets[k] for k in st.secrets.keys() if "GOOGLE_API_KEY_" in k]

# --- INICIALIZACE ---
if "chat_id" not in st.session_state: st.session_state.chat_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state: st.session_state.messages = []

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Chyba připojení k Supabase.")

# --- POMOCNÉ FUNKCE ---
def generate_free_image(prompt):
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {st.secrets['HF_TOKEN']}"}
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt}, timeout=15)
        return Image.open(io.BytesIO(response.content))
    except: return None

def speak(text):
    clean_text = text.split("[IMAGE_GEN:")[0].replace("*", "").strip()
    if clean_text:
        try:
            tts = gTTS(text=clean_text[:300], lang='cs')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            b64 = base64.b64encode(fp.getvalue()).decode()
            audio_html = f'<audio autoplay><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
            st.components.v1.html(audio_html, height=0)
        except: pass

# --- SIDEBAR ---
with st.sidebar:
    st.title("✨ S.M.A.R.T. 2.5")
    if st.button("➕ Nový chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_id = str(uuid.uuid4())[:8]
        st.rerun()
    voice_on = st.toggle("🔊 Aktivní hlas", value=True)
    uploaded_file = st.file_uploader("Analyzovat soubor", type=["pdf", "docx", "txt"])

# --- CHAT ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Napiš něco...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        all_keys = get_all_keys()
        random.shuffle(all_keys) # Zamícháme klíče
        
        success = False
        for key in all_keys:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SMART_SYSTEM_INSTRUCTION)
                
                context = ""
                if uploaded_file:
                    file_text = extract_text_from_file(uploaded_file)
                    context = f"\n\nKontext: {file_text[:2000]}"
                
                response = model.generate_content(user_input + context, stream=True)
                for chunk in response:
                    full_response += chunk.text
                    response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                success = True
                break # Povedlo se, končíme rotaci
            except Exception as e:
                continue # Zkusíme další klíč
        
        if not success:
            st.error("Všechny API klíče jsou momentálně vytížené. Zkus to za chvíli.")
        else:
            if "[IMAGE_GEN:" in full_response:
                img_prompt = full_response.split("[IMAGE_GEN:")[1].split("]")[0].strip()
                with st.spinner("Kreslím..."):
                    img = generate_free_image(img_prompt)
                    if img: st.image(img, use_container_width=True)

            if voice_on: speak(full_response)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Tichý zápis do DB (nezpůsobí pád aplikace při chybě RLS)
            try:
                supabase.table("messages").insert({
                    "chat_id": st.session_state.chat_id, 
                    "role": "assistant", 
                    "content": full_response
                }).execute()
            except:
                pass # Ignorujeme chybu RLS, aby uživatel mohl dál chatovat