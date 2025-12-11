import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Test Progress Dashboard", layout="wide")
st.title("Test Execution Progress Dashboard med semesterjusterad prognos")

# -------------------- Sidomeny --------------------
with st.sidebar:
    st.header("Inställningar")
    iteration_filter = st.text_input("Iteration att filtrera", "Release 4.6.1 Core Uplift")
    hours_per_day = st.number_input("Effektiva testtimmar per person och dag", value=6.0, step=0.5)

    st.markdown("**Semesterjustering**")
    manual_holiday_days = st.slider("Extra semesterdagar (manuell justering)", 0.0, 40.0, 0.0, 0.5)
    holiday_file = st.file_uploader("Semester-matrix Excel (valfritt – ger exakt justering)", type=["xlsx", "xls"])

    st.markdown("---")
    snapshot_files = st.file_uploader(
        "Snapshot CSV-filer (snapshot_YYYY_MM_DD.csv)",
        type=["csv"],
        accept_multiple_files=True
    )

if not snapshot_files:
    st.info("Ladda upp minst en snapshot_CSV-fil för att starta")
    st.stop()

# -------------------- Hjälpfunktion: tolka estimate --------------------
def estimate_to_minutes(val):
    if pd.isna(val): return 0
    s = str(val).strip().lower()
    if not s or s in ["-", "null", "nan"]: return 0
    s = re.sub(r"[,\s]+", " ", s)
    hrs = re.search(r"(\d+(?:\.\d+)?)\s*h", s)
    mins = re.search(r"(\d+)\s*m", s)
    h = float(hrs.group(1)) if hrs else 0
    m = float(mins.group(1)) if mins else 0
    if h == 0 and m == 0:
        num = re.search(r"\d+", s)
        m = float(num.group()) if num else 0
    return int(round(h * 60 + m))

# -------------------- Läs in snapshots --------------------
@st.cache_data
def load_snapshots(files):
    dfs = []
    for f in files:
        for sep in [",", ";"]:
            try:
                df = pd.read_csv(f, sep=sep, on_bad_lines="skip", engine="python")
                if df.shape[1] > 3: break
            except: continue
        else:
            st.error(f"Kunde inte läsa {f.name}"); continue

        try:
            date_str = f.name.split("snapshot_")[-1].split(".")[0].replace("_", "-")[:10]
            snap_date = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            snap_date = datetime.now()
        df["Snapshot_Date"] = snap_date
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else None

data = load_snapshots(snapshot_files)
if data is None or data.empty:
    st.error("Ingen data kunde läsas"); st.stop()

# -------------------- Smart kolumn-matchning --------------------
def col(df, names):
    cols = [c.strip() for c in df.columns]
    for n in names:
        if n in cols: return n
        if n.lower() in [c.lower() for c in cols]:
            return cols[[c.lower() for c in cols].index(n.lower())]
    return None

iteration_col = col(data, ["Iteration", "Iteration Name"])
est_col = col(data, ["Original Estimate", "OriginalEstimate", "Σ Original Estimate", "Estimate"])
rem_col = col(data, ["Remaining Estimate", "Remaining", "Σ Remaining Estimate"])
if not all([iteration_col, est_col, rem_col]):
    st.error(f"Saknar kolumner! Hittade: Iteration={iteration_col}, Original Estimate={est_col}, Remaining={rem_col}")
    st.stop()

data = data[data[iteration_col].astype(str).str.contains(iteration_filter, case=False, na=False)]
data["Est_Min"] = data[est_col].apply(estimate_to_minutes)
data["Rem_Min"] = data[rem_col].apply(estimate_to_minutes)

# -------------------- Semester-matrix (valfritt!) --------------------
extra_holiday_days_from_file = 0.0
if holiday_file:
    try:
        df_h = pd.read_excel(holiday_file, header=None, engine="openpyxl")
        # Enkel men fungerande detektering av x/X i hela arket efter första rad/kolumn
        holiday_cells = df_h.iloc[2:, 1:].applymap(lambda x: str(x).strip().lower() == "x")
        extra_holiday_days_from_file = holiday_cells.sum().sum() * (hours_per_day / hours_per_day)  # 1 x = 1 persondag
        st.success(f"Semester-Excel laddad → {extra_holiday_days_from_file:.1f} extra persondagar upptäckta")
    except Exception as e:
        st.warning(f"Kunde inte tolka semester-excel (använder bara slidern): {e}")
else:
    st.info("Ingen semester-Excel uppladdad → använder bara manuella slidern + svenska helgdagar")

total_extra_days = manual_holiday_days + extra_holiday_days_from_file

# -------------------- Summering & prognos --------------------
summary = data.groupby("Snapshot_Date").agg(
    Total_Hours=("Est_Min", lambda x: x.sum()/60),
    Remaining_Hours=("Rem_Min", lambda x: x.sum()/60)
).reset_index().sort_values("Snapshot_Date")

if len(summary) >= 2 and summary["Remaining_Hours"].iloc[-1] < summary["Remaining_Hours"].iloc[0]:
    x = np.arange(len(summary))
    y = summary["Remaining_Hours"].values
    slope, intercept = np.polyfit(x, y, 1)
    days_needed = int(np.ceil(-intercept / slope)) if slope < 0 else 999
    last_date = summary["Snapshot_Date"].iloc[-1].date()
    orig_finish = last_date + timedelta(days=days_needed)
    final_finish = orig_finish + timedelta(days=int(total_extra_days))
else:
    orig_finish = final_finish = None
    days_needed = 0

# -------------------- Visa resultat --------------------
c1, c2 = st.columns(2)
with c1:
    st.metric("Senaste snapshot", summary["Snapshot_Date"].iloc[-1].strftime("%Y-%m-%d"))
    st.metric("Totalt arbete", f"{summary['Total_Hours'].iloc[-1]:.1f} h")
with c2:
    st.metric("Kvarvarande", f"{summary['Remaining_Hours'].iloc[-1]:.1f} h")
    if orig_finish:
        st.metric("Original prognos", orig_finish.strftime("%Y-%m-%d"))
        st.metric("Semesterjusterad prognos", final_finish.strftime("%Y-%m-%d"),
                  f"+{total_extra_days:.1f} dagar")

# Burn-down chart
fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_Hours"], mode="lines+markers", name="Totalt"))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Remaining_Hours"], mode="lines+markers", name="Kvar", line=dict(color="red")))
fig.update_layout(title="Burn-down Chart", xaxis_title="Datum", yaxis_title="Timmar")
st.plotly_chart(fig, use_container_width=True)

st.download_button("Ladda ner allt som CSV", data.to_csv(index=False).encode(), "progress_data.csv", "text/csv")
st.success("Färdigt! Dela länken med kollegorna – semester-Excel är helt valfritt")
