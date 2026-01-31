import streamlit as st
import google.generativeai as genai
from supabase import create_client
import uuid
from datetime import datetime
import time

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
    """Obnoví session Supabase, aby fungovaly funkce jako změna hesla/emailu."""
    if "session" in st.session_state:
        try:
            # Pokusíme se obnovit session pro klienta
            supabase.auth.set_session(
                st.session_state.session.access_token, 
                st.session_state.session.refresh_token
            )
        except Exception:
            # Pokud je token starý, raději uživatele odhlásíme
            st.warning("Relace vypršela. Přihlaste se prosím znovu.")
            del st.session_state.session
            if "user" in st.session_state: del st.session_state.user
            st.rerun()

def get_profile(uid):
    """Načte profil a zajistí, že vrátí slovník i při chybě."""
    try:
        # Vypneme cache, chceme vždy čerstvá data při načtení
        res = supabase.table("profiles").select("*").eq("id", uid).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    # Výchozí hodnoty, pokud profil neexistuje
    return {
        "display_name": "", 
        "theme": "dark", 
        "ai_instructions": "", 
        "response_length": "Střední",
        "birth_date": str(datetime.now().date())
    }

# --- 4. AUTH LOGIKA (Přihlášení / Registrace) ---

# Pokud uživatel není přihlášen
if "user" not in st.session_state:
    st.title("🤖 S.M.A.R.T. OS")
    
    tab1, tab2 = st.tabs(["Přihlásit se", "Vytvořit účet"])
    
    with tab1:
        email = st.text_input("Email", key="log_email")
        password = st.text_input("Heslo", type="password", key="log_pass")
        
        if st.button("Vstoupit", use_container_width=True):
            try:
                # Přihlášení
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.user:
                    st.session_state.user = res.user
                    st.session_state.session = res.session  # DŮLEŽITÉ: Ukládáme celou session
                    st.rerun()
            except Exception as e:
                st.error("Nesprávný email nebo heslo.")

    with tab2:
        reg_name = st.text_input("Jak vám mám říkat? (Display Name)")
        reg_email = st.text_input("Email", key="reg_email")
        reg_pass = st.text_input("Heslo (min. 6 znaků)", type="password", key="reg_pass")
        
        if st.button("Zaregistrovat se", use_container_width=True):
            try:
                # Registrace
                res = supabase.auth.sign_up({"email": reg_email, "password": reg_pass})
                if res.user:
                    # Vytvoření profilu
                    supabase.table("profiles").insert({
                        "id": res.user.id, 
                        "display_name": reg_name
                    }).execute()
                    st.success("Účet vytvořen! Nyní se přihlaste v první záložce.")
            except Exception as e:
                st.error(f"Chyba registrace: {e}")
    
    st.stop() # Zastaví načítání zbytku aplikace

# --- 5. NAČTENÍ DAT A OBNOVA SESSION ---

# Obnovíme session pro auth operace
init_session()

user_id = st.session_state.user.id
profile = get_profile(user_id) # Načteme čerstvý profil

# Nastavení proměnných z profilu
display_name = profile.get("display_name") or st.session_state.user.email
current_theme = profile.get("theme", "dark")

# --- 6. APLIKACE MOTIVU (CSS) ---

# Definice barev
if current_theme == "light":
    bg_color = "#ffffff"
    text_color = "#000000"
    sidebar_bg = "#f0f2f6"
    input_bg = "#ffffff"
    input_border = "#cccccc"
else: # Dark theme (default)
    bg_color = "#0e1117"
    text_color = "#e0e0e0"
    sidebar_bg = "#262730"
    input_bg = "#161b22"
    input_border = "#333333"

# Injektáž CSS - Používáme !important pro přepsání Streamlit defaults
st.markdown(f"""
    <style>
    /* Hlavní pozadí aplikace */
    .stApp {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
    }}
    
    /* Skrytí horní lišty, ale zachování prostoru */
    header[data-testid="stHeader"] {{
        background: rgba(0,0,0,0) !important;
    }}
    .stDeployButton, #MainMenu {{ visibility: hidden; }}
    
    /* Žlutá šipka sidebaru */
    button[data-testid="stSidebarCollapseIcon"] {{ color: #FFD700 !important; }}
    
    /* Vstupní pole chatu - Kapsle */
    div[data-testid="stChatInput"] {{
        border-radius: 30px !important;
        background-color: {input_bg} !important;
        border: 1px solid {input_border} !important;
        color: {text_color} !important;
    }}
    
    /* Text inputy v nastavení */
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border-radius: 10px !important;
    }}
    
    .disclaimer {{ font-size: 0.75rem; color: #5d636d; text-align: center; padding: 20px; }}
    </style>
""", unsafe_allow_html=True)

# --- 7. SIDEBAR ---

if "chat_id" not in st.session_state: 
    st.session_state.chat_id = str(uuid.uuid4())[:8]

with st.sidebar:
    st.markdown(f"<h1 style='color: #FFD700;'>Ahoj, {display_name}!</h1>", unsafe_allow_html=True)
    
    col_new, col_set = st.columns(2)
    with col_new:
        if st.button("➕ Chat", use_container_width=True):
            st.session_state.chat_id = str(uuid.uuid4())[:8]
            st.session_state.page = "chat"
            st.rerun()
    with col_set:
        if st.button("⚙️ Úpravy", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()
    
    st.divider()
    st.caption("🗂️ Historie chatů")
    
    try:
        # Načteme unikátní ID chatů uživatele
        hist_res = supabase.table("messages").select("chat_id").eq("user_id", user_id).execute()
        # Získáme unikátní ID a vezmeme posledních 10
        all_ids = [row['chat_id'] for row in hist_res.data]
        unique_ids = list(dict.fromkeys(all_ids))[-10:] # Odstraní duplicity a zachová pořadí
        
        for cid in reversed(unique_ids):
            if st.button(f"Chat {cid}", key=f"h_{cid}", use_container_width=True):
                st.session_state.chat_id = cid
                st.session_state.page = "chat"
                st.rerun()
    except Exception:
        st.caption("Žádná historie.")

    st.divider()
    if st.button("🚪 Odhlásit se", use_container_width=True):
        supabase.auth.sign_out()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 8. HLAVNÍ OBSAH (Router) ---

if st.session_state.get("page") == "settings":
    st.title("⚙️ Nastavení systému")
    
    # Záložky nastavení
    t_prof, t_sec, t_ai, t_sys = st.tabs(["👤 Profil", "🛡️ Zabezpečení", "🧠 Inteligence AI", "🖥️ Vzhled"])
    
    # --- PROFIL ---
    with t_prof:
        st.subheader("Osobní údaje")
        c1, c2 = st.columns(2)
        with c1:
            # Používáme .get s prázdným stringem jako fallback
            new_dn = st.text_input("Zobrazované jméno", value=profile.get("display_name", ""))
            new_ln = st.text_input("Příjmení", value=profile.get("last_name", ""))
        with c2:
            bday_str = profile.get("birth_date")
            # Pokud datum chybí, použijeme dnešek
            default_date = datetime.strptime(bday_str, "%Y-%m-%d").date() if bday_str else datetime.now().date()
            new_bd = st.date_input("Datum narození", value=default_date)
            
        if st.button("💾 Uložit profil", type="primary"):
            try:
                supabase.table("profiles").update({
                    "display_name": new_dn,
                    "last_name": new_ln,
                    "birth_date": str(new_bd)
                }).eq("id", user_id).execute()
                st.success("Profil byl úspěšně aktualizován!")
                time.sleep(1)
                st.rerun() # Nutné pro refresh jména v sidebaru
            except Exception as e:
                st.error(f"Chyba při ukládání: {e}")

    # --- ZABEZPEČENÍ ---
    with t_sec:
        st.subheader("Změna přihlašovacího e-mailu")
        new_email_input = st.text_input("Nový e-mail", value=st.session_state.user.email)
        
        if st.button("Odeslat potvrzovací kód"):
            if new_email_input == st.session_state.user.email:
                st.warning("Zadejte jiný e-mail než ten aktuální.")
            else:
                try:
                    # Zde to dříve padalo na AuthSessionMissingError
                    supabase.auth.update_user({"email": new_email_input})
                    st.session_state.email_change_pending = new_email_input
                    st.info(f"Potvrzovací odkaz/kód byl odeslán na {new_email_input}. Zkontrolujte schránku.")
                except Exception as e:
                    st.error(f"Chyba: {e}")

        st.info("💡 Pro změnu hesla se odhlaste a použijte 'Zapomenuté heslo' (pokud je nastaveno) nebo kontaktujte admina.")

    # --- AI INTELIGENCE ---
    with t_ai:
        st.subheader("Chování Asistenta")
        
        current_inst = profile.get("ai_instructions", "")
        new_inst = st.text_area("Vlastní instrukce (System Prompt)", value=current_inst, height=150)
        
        # Příklady - nyní jasně viditelné
        with st.expander("👀 Zobrazit příklady instrukcí"):
            st.markdown("""
            * **Profesionál:** "Jsi zkušený manažer. Odpovídej stručně, formálně a v odrážkách."
            * **Programátor:** "Jsi senior Python vývojář. Piš pouze kód bez omáčky okolo."
            * **Kamarád:** "Jsi můj nejlepší kámoš. Tykej mi, používej emotikony a buď vtipný."
            * **Učitel:** "Vysvětluj všechno, jako by mi bylo 10 let. Používej metafory."
            """)
        
        # Mapování slov na hodnoty
        length_options = ["Krátká", "Střední", "Dlouhá"]
        current_len = profile.get("response_length", "Střední")
        # Ošetření, kdyby v DB bylo něco jiného
        if current_len not in length_options: current_len = "Střední"
        
        new_len = st.select_slider("Preferovaná délka odpovědí", options=length_options, value=current_len)
        
        if st.button("💾 Uložit nastavení AI", type="primary"):
            try:
                supabase.table("profiles").update({
                    "ai_instructions": new_inst,
                    "response_length": new_len
                }).eq("id", user_id).execute()
                st.success("Nastavení AI uloženo! Projeví se v příští zprávě.")
                time.sleep(1)
                st.rerun() # Nutné, aby se načetla nová data do proměnných
            except Exception as e:
                st.error(f"Chyba ukládání: {e}")

    # --- VZHLED ---
    with t_sys:
        st.subheader("Motiv aplikace")
        
        # Výběr motivu
        theme_map = {"Tmavý": "dark", "Světlý": "light"}
        # Reverzní mapa pro zjištění indexu
        rev_theme_map = {"dark": "Tmavý", "light": "Světlý"}
        
        current_selection = rev_theme_map.get(current_theme, "Tmavý")
        selected_theme_label = st.radio("Vyberte motiv", ["Tmavý", "Světlý"], index=["Tmavý", "Světlý"].index(current_selection), horizontal=True)
        
        if st.button("🎨 Použít motiv"):
            new_theme_val = theme_map[selected_theme_label]
            if new_theme_val != current_theme:
                supabase.table("profiles").update({"theme": new_theme_val}).eq("id", user_id).execute()
                st.success("Motiv změněn! Obnovuji...")
                time.sleep(0.5)
                st.rerun()
            else:
                st.info("Tento motiv je již aktivní.")

else:
    # --- CHAT / NOTEBOOK ---
    mode = st.segmented_control("Režim", ["💬 Chat", "🧠 NotebookLM"], default="💬 Chat")

    if mode == "🧠 NotebookLM":
        st.subheader("Analýza dokumentů")
        col1, col2, col3 = st.columns(3)
        with col1: st.button("🎙️ Audio Přehled", use_container_width=True)
        with col2: st.button("❓ Generovat Kvíz", use_container_width=True)
        with col3: st.button("🗺️ Myšlenková mapa", use_container_width=True)
        
        st.info("Tyto funkce budou aktivovány v další aktualizaci.")

    else:
        # KLASICKÝ CHAT
        st.caption(f"ID vlákna: {st.session_state.chat_id}")
        
        # Načtení historie
        msgs = []
        try:
            res = supabase.table("messages").select("*").eq("chat_id", st.session_state.chat_id).eq("user_id", user_id).order("created_at").execute()
            msgs = res.data
        except: pass
        
        # Vykreslení zpráv
        for m in msgs:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        # Input zóna
        if prompt := st.chat_input("Zeptejte se..."):
            # 1. Uložit User Message
            with st.chat_message("user"): st.markdown(prompt)
            supabase.table("messages").insert({
                "chat_id": st.session_state.chat_id, "role": "user", "content": prompt, "user_id": user_id
            }).execute()

            # 2. Příprava AI s daty z PROFILU
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY_1"])
            
            # Sestavení System Promptu
            custom_instruction = profile.get("ai_instructions") or "Jsi užitečný asistent."
            length_instruction = profile.get("response_length", "Střední")
            len_prompt = ""
            if length_instruction == "Krátká": len_prompt = "Odpovídej velmi stručně, jednou větou."
            elif length_instruction == "Dlouhá": len_prompt = "Rozepiš se do detailů, buď obsáhlý."
            
            final_system_prompt = f"""
            Jsi S.M.A.R.T. OS.
            Uživatele oslovuj: {display_name}.
            
            INSTRUKCE UŽIVATELE:
            {custom_instruction}
            
            DÉLKA ODPOVĚDI:
            {len_prompt}
            """
            
            model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=final_system_prompt)
            
            # Konverze historie pro Gemini
            gem_hist = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in msgs]
            
            # 3. Generování odpovědi
            with st.spinner("Přemýšlím..."):
                try:
                    chat = model.start_chat(history=gem_hist)
                    response = chat.send_message(prompt)
                    ai_text = response.text
                except Exception as e:
                    ai_text = f"Omlouvám se, došlo k chybě AI: {e}"

            # 4. Uložit a zobrazit AI Message
            with st.chat_message("assistant"): st.markdown(ai_text)
            supabase.table("messages").insert({
                "chat_id": st.session_state.chat_id, "role": "assistant", "content": ai_text, "user_id": user_id
            }).execute()
            
            # Lehký refresh, aby se vše synchronizovalo
            st.rerun()

st.markdown("<div class='disclaimer'>S.M.A.R.T. OS v1.2 | Data jsou šifrována.</div>", unsafe_allow_html=True)