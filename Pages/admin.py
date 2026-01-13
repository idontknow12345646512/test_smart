import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="S.M.A.R.T. Admin", page_icon="🔐")

st.title("🔐 S.M.A.R.T. Admin")

pw = st.text_input("Zadejte admin heslo", type="password")

if pw == st.secrets["ADMIN_PASSWORD"]:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    tab1, tab2 = st.tabs(["📊 Statistiky", "💬 Historie"])
    
    with tab1:
        stats = conn.read(worksheet="Stats", ttl=0)
        st.subheader("Počítadlo zpráv")
        st.dataframe(stats, use_container_width=True)
        
        if st.button("🔄 Resetovat počítadlo na 0"):
            new_stats = pd.DataFrame([{"key": "total_messages", "value": "0"}])
            conn.update(worksheet="Stats", data=new_stats)
            st.success("Počítadlo bylo vyresetováno.")
            st.rerun()

    with tab2:
        users = conn.read(worksheet="Users", ttl=0)
        st.subheader("Kompletní historie chatů")
        st.dataframe(users, use_container_width=True)
        
        csv = users.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Stáhnout CSV zálohu", data=csv, file_name="smart_backup.csv")

elif pw:
    st.error("Špatné heslo.")
