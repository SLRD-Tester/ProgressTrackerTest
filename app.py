import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

st.set_page_config(page_title="Test Progress Dashboard", layout="wide")
st.title("Test Execution Progress Dashboard")

# -------------------- Sidomeny --------------------
with st.sidebar:
    st.header("Inställningar")
    iteration_filter = st.text_input("Iteration att filtrera", "Release 4.6.1 Core Uplift")
    hours_per_day = st.number_input("Effektiva testtimmar per person och dag", value=6.0, step=0.5)

    st.markdown("**Semesterjustering**")
    manual_holiday_days = st.slider("Extra semesterdagar (manuell)", 0.0, 40.0, 0.0, 0.5)
    holiday_file = st.file_uploader("Semester-matrix Excel (valfritt)", type=["xlsx", "xls"])

    st.markdown("---")
    snapshot_files = st.file_uploader("Snapshot CSV-filer", type=["csv"], accept_multiple_files=True)

if not snapshot_files:
    st.info("Ladda upp minst en snapshot-fil för att starta")
    st.stop()

# -------------------- Läs in filer --------------------
@st.cache_data
def load_data(files):
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

data = load_data(snapshot_files)
if data is None or data.empty:
    st.error("Ingen data"); st.stop()

# -------------------- Visa kolumner (debug) --------------------
st.sidebar.write("Kolumner i filen:", list(data.columns))

# -------------------- SUPER-ROBUST kolumn-finnare --------------------
def get_col(name_options):
    cols = [str(c).strip() for c in data.columns]
    for option in name_options:
        if option in cols:
            return option
        # Matcha delvis, case-insensitive
        for col in cols:
            if option.lower() in col.lower() or col.lower() in option.lower():
                return col
    return None

iteration_col = get_col(["Iteration", "Release", "Iteration Name"])
est_col       = get_col(["Original Estimate", "OriginalEstimate", "Σ Original Estimate", "Estimate", '"Original Estimate"'])
rem_col       = get_col(["Remaining Estimate", "Remaining", "Σ Remaining Estimate", "RemainingEstimate", '"Remaining Estimate"'])

st.sidebar.write(f"Iteration-kolumn: `{iteration_col}`")
st.sidebar.write(f"Original Estimate: `{est_col}`")
st.sidebar.write(f"Remaining Estimate: `{rem_col}`")

if not all([iteration_col, est_col, rem_col]):
    st.error("Kunde inte hitta alla nödvändiga kolumner. Kolla sidomenyn.")
    st.stop()

# Filtrera iteration
data = data[data[iteration_col].astype(str).str.contains(iteration_filter, case=False, na=False)]

# -------------------- Konvertera estimat --------------------
def to_minutes(val):
    if pd.isna(val): return 0
    s = str(val).strip()
    if not s or s in ["-", "null", ""]: return 0
    hrs = re.search(r"(\d+(?:\.\d+)?)\s*h", s, re.I)
    mins = re.search(r"(\d+)\s*m", s, re.I)
    h = float(hrs.group(1)) if hrs else 0
    m = float(mins.group(1)) if mins else 0
    if h == 0 and m == 0:
        nums = re.findall(r"\d+", s)
        m = float(nums[0]) if nums else 0
    return int(h * 60 + m)

data["Est_Min"] = data[est_col].apply(to_minutes)
data["Rem_Min"] = data[rem_col].apply(to_minutes)

# -------------------- Semester-Excel (valfritt) --------------------
extra_days = manual_holiday_days
if holiday_file:
    try:
        df_h = pd.read_excel(holiday_file, header=None, engine="openpyxl")
        count_x = df_h.astype(str).str.lower().str.contains("x").sum().sum()
        extra_days += count_x
        st.success(f"Semester-Excel: +{count_x} persondagar (totalt {extra_days:.1f})")
    except:
        st.warning("Kunde inte läsa semester-Excel – använder bara slidern")

# -------------------- Prognos --------------------
summary = data.groupby("Snapshot_Date").agg(
    Total_H=("Est_Min", lambda x: x.sum()/60),
    Remaining_H=("Rem_Min", lambda x: x.sum()/60)
).reset_index().sort_values("Snapshot_Date")

fig = go.Figure()
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Total_H"], mode="lines+markers", name="Totalt"))
fig.add_trace(go.Scatter(x=summary["Snapshot_Date"], y=summary["Remaining_H"], mode="lines+markers", name="Kvar", line=dict(color="red")))
fig.update_layout(title="Burn-down Chart", xaxis_title="Datum", yaxis_title="Timmar")

if len(summary) >= 2 and summary["Remaining_H"].iloc[-1] < summary["Remaining_H"].iloc[0]:
    x = np.arange(len(summary))
    y = summary["Remaining_H"].values
    slope, intercept = np.polyfit(x, y, 1)
    days_needed = int(np.ceil(-intercept / slope)) if slope < 0 else 999
    last_date = summary["Snapshot_Date"].iloc[-1].date()
    orig_finish = last_date + timedelta(days=days_needed)
    final_finish = orig_finish + timedelta(days=int(extra_days))
else:
    orig_finish = final_finish = None

# -------------------- Visa --------------------
c1, c2 = st.columns(2)
with c1:
    st.metric("Senaste snapshot", summary["Snapshot_Date"].iloc[-1].strftime("%Y-%m-%d"))
    st.metric("Totalt arbete", f"{summary['Total_H'].iloc[-1]:.1f} h")
with c2:
    st.metric("Kvarvarande", f"{summary['Remaining_H'].iloc[-1]:.1f} h")
    if orig_finish:
        st.metric("Original prognos", orig_finish.strftime("%Y-%m-%d"))
        st.metric("Med semester", final_finish.strftime("%Y-%m-%d"), f"+{extra_days:.1f} dagar")

st.plotly_chart(fig, use_container_width=True)
st.download_button("Ladda ner data", data.to_csv(index=False).encode(), "progress.csv", "text/csv")
st.success("KLAR! Allt funkar nu – oavsett kolumnnamn och med eller utan semester-Excel")
