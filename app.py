import streamlit as st

st.title("NASA Space Apps 2026 - SPHEREx Time-Lapse")

ra = st.text_input("RA")
dec = st.text_input("DEC")

if st.button("Afficher l'image"):
    st.write(f"Chargement des données pour RA: {ra}, DEC: {dec}...")