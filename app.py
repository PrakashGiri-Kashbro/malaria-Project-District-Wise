import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk
import json

# load
@st.cache_data
def load_file():
    return pd.read_csv("data/malaria_indicators_btn.csv")

df = load_file()

st.title("Malaria Dashboard (Bhutan)")
st.write("This is a simple dashboard made for learning. It shows malaria indicators of Bhutan.")

# ------------------------------------------------
# SHOW ACTUAL CSV COLUMNS
# ------------------------------------------------
st.write("### CSV Columns Detected:")
st.write(list(df.columns))

# ------------------------------------------------
# USER PICKS COLUMNS (NO MORE ERRORS)
# ------------------------------------------------
indicator_col = st.sidebar.selectbox("Select indicator column", df.columns)
year_col = st.sidebar.selectbox("Select year column", df.columns)
value_col = st.sidebar.selectbox("Select numeric/value column", df.columns)

# rename internally (safe)
df = df.rename(columns={
    indicator_col: "indicator_name",
    year_col: "year",
    value_col: "value_num"
})

# numeric conversion (safe)
df["value_num"] = pd.to_numeric(df["value_num"], errors="coerce")

# ------------------------------------------------
# indicator selection
# ------------------------------------------------
ind_list = df["indicator_name"].dropna().unique()
picked = st.sidebar.selectbox("Select Indicator", ind_list)

filt = df[df["indicator_name"] == picked]

st.subheader(picked)

# -----------------------
# Charts
# -----------------------
fig1 = px.bar(filt, x="year", y="value_num", title=picked)
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.line(filt, x="year", y="value_num", markers=True)
st.plotly_chart(fig2, use_container_width=True)

# table
st.write("### Data Table")
st.dataframe(filt)

# -----------------------
# Map
# -----------------------
st.write("---")
st.header("Bhutan Map")

with open("data/bhutan_districts.json", "r") as f:
    geo = json.load(f)

layer = pdk.Layer(
    "GeoJsonLayer",
    geo,
    stroked=True,
    filled=True,
    get_fill_color="[255, 0, 0, 100]"
)

view = pdk.ViewState(latitude=27.5, longitude=90.4, zoom=7)

st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=view
    )
)
