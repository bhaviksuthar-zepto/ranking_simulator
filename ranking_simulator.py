# =========================================================
# Ranking Simulation Tool - Streamlit App
# =========================================================

import streamlit as st
import pandas as pd
import numpy as np
import numexpr as ne

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="Ranking Simulation Tool",
    layout="wide"
)

st.title("🔁 Ranking Simulation & Comparison Tool")

# -----------------------------
# Load Data
# -----------------------------
@st.cache_data
def load_data():
    return pd.read_csv("base_file.csv")

df = load_data()

# -----------------------------
# Sidebar Filters
# -----------------------------
st.sidebar.header("🔍 Filters")

search_term = st.sidebar.selectbox(
    "Search Term",
    sorted(df["search_term"].unique())
)

brand_filter = st.sidebar.multiselect(
    "Brand Name",
    sorted(df["brand_name"].unique())
)

category_filter = st.sidebar.multiselect(
    "L3 Category",
    sorted(df["l3_category_name"].unique())
)

top_k = st.sidebar.slider(
    "Top K",
    min_value=5,
    max_value=100,
    value=20,
    step=5
)

# -----------------------------
# Filter Data
# -----------------------------
filtered_df = df[df["search_term"] == search_term]

if brand_filter:
    filtered_df = filtered_df[filtered_df["brand_name"].isin(brand_filter)]

if category_filter:
    filtered_df = filtered_df[filtered_df["l3_category_name"].isin(category_filter)]

if filtered_df.empty:
    st.warning("No data available for selected filters")
    st.stop()

# -----------------------------
# Ranking Formula Inputs
# -----------------------------
st.sidebar.header("🧮 Ranking Formulas")

formula_a = st.sidebar.text_area(
    "Formula A",
    value="ranking_score * (1 + asp_boost)",
    height=80
)

formula_b = st.sidebar.text_area(
    "Formula B",
    value="ranking_score * (1 + 2 * asp_boost)",
    height=80
)

st.sidebar.markdown(
    """
    **Allowed variables**
    - ranking_score
    - asp_boost
    - pop_boost
    """
)

# -----------------------------
# Safe Formula Evaluation
# -----------------------------
def evaluate_formula(df, expr):
    local_dict = {
        "ranking_score": df["ranking_score"].values,
        "asp_boost": df["asp_boost"].values,
        "pop_boost": df["pop_boost"].values,
    }
    return ne.evaluate(expr, local_dict)

try:
    df_sim = filtered_df.copy()

    df_sim["score_a"] = evaluate_formula(df_sim, formula_a)
    df_sim["score_b"] = evaluate_formula(df_sim, formula_b)

except Exception as e:
    st.error(f"❌ Error in formula evaluation: {e}")
    st.stop()

# -----------------------------
# Rank Computation
# -----------------------------
df_sim["rank_a"] = df_sim["score_a"].rank(
    method="first", ascending=False
)

df_sim["rank_b"] = df_sim["score_b"].rank(
    method="first", ascending=False
)

df_sim["rank_delta"] = df_sim["rank_b"] - df_sim["rank_a"]

# -----------------------------
# Top-K Selection
# -----------------------------
topk_df = df_sim[
    (df_sim["rank_a"] <= top_k) | (df_sim["rank_b"] <= top_k)
].sort_values("rank_a")

# -----------------------------
# Display Ranking Table
# -----------------------------
st.subheader("📊 Ranking Comparison")

display_cols = [
    "product_variant_id",
    "product_name",
    "brand_name",
    "l3_category_name",
    "selling_price",
    "ranking_cohort",
    "rank_a",
    "rank_b",
    "rank_delta"
]

st.dataframe(
    topk_df[display_cols]
        .sort_values("rank_a")
        .reset_index(drop=True),
    use_container_width=True
)

# -----------------------------
# Summary Metrics
# -----------------------------
st.subheader("📈 Summary Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    overlap = len(
        set(df_sim[df_sim["rank_a"] <= top_k]["product_variant_id"])
        & set(df_sim[df_sim["rank_b"] <= top_k]["product_variant_id"])
    )
    st.metric("Top-K Overlap", f"{overlap}/{top_k}")

with col2:
    avg_rank_shift = df_sim["rank_delta"].abs().mean()
    st.metric("Avg |Rank Change|", f"{avg_rank_shift:.2f}")

with col3:
    improved = (df_sim["rank_delta"] < 0).sum()
    st.metric("Products Improved", improved)

with col4:
    worsened = (df_sim["rank_delta"] > 0).sum()
    st.metric("Products Dropped", worsened)

# -----------------------------
# Rank Delta Distribution
# -----------------------------
st.subheader("📉 Rank Change Distribution")

rank_delta_counts = (
    df_sim["rank_delta"]
    .value_counts()
    .sort_index()
)

st.bar_chart(rank_delta_counts)

# -----------------------------
# Download Results
# -----------------------------
st.subheader("⬇️ Download")

csv = topk_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download Ranking Comparison CSV",
    data=csv,
    file_name="ranking_simulation_output.csv",
    mime="text/csv"
)
