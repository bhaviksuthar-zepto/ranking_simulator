import numpy as np
import streamlit as st
import pandas as pd

@st.cache_data
def load_data():
    return pd.read_csv("base_file.csv")

df = load_data()

st.sidebar.title("Ranking Simulator")

# ---- Controls ----
query = st.sidebar.selectbox(
    "Search Term",
    options=df["search_term"],unique()
)

w_asp = st.sidebar.slider("ASP Boost Weight", -2.0, 2.0, 1.0, 0.1)
w_mul = st.sidebar.slider("Multiplier Weight", -2.0, 2.0, 1.0, 0.1)

top_k = st.sidebar.selectbox("Top K", [10, 20, 50])

# ---- Filter Query ----
subset = df[df["search_term"] == query].copy()

if subset.empty:
    st.warning("No products found for this query")
    st.stop()

# ---- Baseline ----
subset["score_A"] = subset["ranking_score"]
subset["rank_A"] = subset["rnk"]

# ---- New Equation ----
subset["score_B"] = (
    subset["ranking_score"]
    + w_asp * subset["asp_boost"]
    + w_mul * subset["mulpitlier1"]
)

subset["rank_B"] = subset["score_B"].rank(
    ascending=False,
    method="first"
)

subset["delta_rank"] = subset["rank_A"] - subset["rank_B"]

# ---- Display ----
st.subheader(f"Ranking Comparison for '{query}'")

cols = [
    "product_name",
    "brand_name",
    "rank_A",
    "rank_B",
    "delta_rank",
    "asp_boost",
    "mulpitlier1"
]

st.dataframe(
    subset.sort_values("rank_B")
          .head(top_k)[cols],
    use_container_width=True
)

# ---- Summary Metrics ----
moved_up = (subset["delta_rank"] > 0).sum()
moved_down = (subset["delta_rank"] < 0).sum()

st.metric("Products Moved Up", moved_up)
st.metric("Products Moved Down", moved_down)
