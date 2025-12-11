import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Jobb-progress", layout="wide")
st.title("📊 Jobb-progress – alla projekt")

st.markdown("**Ladda upp alla Excel-filer på en gång (du kan markera 20+ filer samtidigt)**")

uploaded_files = st.file_uploader(
    "Dra hit eller klicka för att välja filer",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="Markera alla filer i mappen och dra in dem samtidigt"
)

if uploaded_files:
    with st.spinner(f"Läser in {len(uploaded_files)} filer..."):
        dfs = []
        for file in uploaded_files:
            df = pd.read_excel(file)
            df["Källa"] = file.name.split(".")[0]  # lägger till filnamnet som kolumn
            dfs.append(df)
        
        # Slår ihop alla filer
        data = pd.concat(dfs, ignore_index=True)
        
        # ──────────────────────
        # HIT SKA DU LÄGGA IN ER BEFINTLIGA PROGRESS-KOD
        # Ersätt raden nedan med er riktiga beräkning
        # data = calculate_progress(data)   # <-- klistra in er kod här
        # ──────────────────────
        # Som placeholder räknar vi bara antalet rader per projekt
        summary = data.groupby("Projekt").size().reset_index(name="Antal jobb")
        summary["Progress %"] = (summary["Antal jobb"] / summary["Antal jobb"].sum() * 100).round(1)
        
        st.success(f"Färdigt! {len(uploaded_files)} filer är sammanställda")
        
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(data, use_container_width=True)
        with col2:
            st.dataframe(summary, use_container_width=True)
        
        # Fin interaktiv graf
        fig = px.bar(summary, 
                     x="Projekt", 
                     y="Progress %",
                     text="Progress %",
                     title="Total progress alla projekt",
                     color="Progress %",
                     color_continuous_scale="Blues")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
        
        # Ladda ner-knapp
        excel_data = summary.to_excel(index=False)
        st.download_button(
            "📥 Ladda ner sammanställd Excel",
            excel_data,
            "progress_sammanställning.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
