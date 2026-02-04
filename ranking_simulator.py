# =========================================================
# Ranking Simulation Tool - Streamlit App (FINAL STABLE)
# =========================================================

import streamlit as st
import pandas as pd
import ast
import operator as op

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
df["asp_boost"] = df["asp_boost"].fillna(0.0)
df["pop_boost"] = df["pop_boost"].fillna(0.0)
# -----------------------------
# Sidebar Filters
# -----------------------------
st.sidebar.header("🔍 Filters")

search_term = st.sidebar.selectbox(
    "Search Term",
    (df["search_term"].unique())
)

top_k = st.sidebar.slider(
    "Top K",
    min_value=5,
    max_value=100,
    value=20,
    step=5
)

# -----------------------------
# Apply Filters
# -----------------------------
filtered_df = df[df["search_term"] == search_term]

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

**Allowed operators**
+  -  *  /  ( )
"""
)

# -----------------------------
# Safe Expression Evaluator
# -----------------------------
ALLOWED_OPERATORS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
}

def safe_eval_expr(expr, variables):
    def _eval(node):
        if isinstance(node, ast.Constant):  # numbers
            return node.value

        elif isinstance(node, ast.Name):  # variables
            if node.id not in variables:
                raise ValueError(f"Unknown variable: {node.id}")
            return variables[node.id]

        elif isinstance(node, ast.BinOp):  # a + b, a * b
            if type(node.op) not in ALLOWED_OPERATORS:
                raise TypeError("Operator not allowed")
            return ALLOWED_OPERATORS[type(node.op)](
                _eval(node.left),
                _eval(node.right)
            )

        elif isinstance(node, ast.UnaryOp):  # -x
            if isinstance(node.op, ast.USub):
                return -_eval(node.operand)
            raise TypeError("Unary operator not allowed")

        else:
            raise TypeError("Unsupported expression")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed.body)


def evaluate_formula(df, expr):
    return safe_eval_expr(
        expr,
        {
            "ranking_score": df["ranking_score"],
            "asp_boost": df["asp_boost"],
            "pop_boost": df["pop_boost"],
        }
    )

# -----------------------------
# Compute Scores
# -----------------------------
try:
    df_sim = filtered_df.copy()

    df_sim["score_a"] = evaluate_formula(df_sim, formula_a)
    df_sim["score_b"] = evaluate_formula(df_sim, formula_b)

    # Guardrails
    df_sim["score_a"] = df_sim["score_a"].clip(lower=0)
    df_sim["score_b"] = df_sim["score_b"].clip(lower=0)

except Exception as e:
    st.error(f"❌ Formula Error: {e}")
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
    "rank_delta",
    "pop_boost",
    "asp_boost"
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
    avg_shift = df_sim["rank_delta"].abs().mean()
    st.metric("Avg |Rank Change|", f"{avg_shift:.2f}")

with col3:
    improved = (df_sim["rank_delta"] < 0).sum()
    st.metric("Products Improved", improved)

with col4:
    dropped = (df_sim["rank_delta"] > 0).sum()
    st.metric("Products Dropped", dropped)

# -----------------------------
# Rank Delta Distribution
# -----------------------------
st.subheader("📉 Rank Change Distribution")

st.bar_chart(
    df_sim["rank_delta"]
        .value_counts()
        .sort_index()
)

# -----------------------------
# Download Results
# -----------------------------
st.subheader("⬇️ Download Results")

csv = topk_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download Ranking Comparison CSV",
    data=csv,
    file_name="ranking_simulation_output.csv",
    mime="text/csv"
)
