# =========================================================
# Ranking Simulation Tool - Streamlit App (FINAL STABLE)
# =========================================================

import streamlit as st
import pandas as pd
import ast
import operator as op
#from databricks import sql
import os

#databricks_token = os.environ.get("DATABRICKS_TOKEN")

#connection = sql.connect(
 #                       server_hostname = "zepto-ds-prod.cloud.databricks.com",
  #                      http_path = "/sql/1.0/warehouses/c9d51cc865edefd5",
   #                     access_token = databricks_token)

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
#"gold.product.search_ranking_simulator"
@st.cache_data
def load_data():
#    return pd.read_sql("SELECT * FROM gold.product.search_ranking_simulator", connection)
   return pd.read_csv("ranking_base_file.csv")


df = load_data()

if "ranking_cohort" not in df.columns:
    df["ranking_cohort"] = "Unknown"
    
#df["asp_boost"] = df["asp_boost"].fillna(0.0)
#df["pop_boost"] = df["pop_boost"].fillna(0.0)
# -----------------------------
# Sidebar Filters
# -----------------------------
st.sidebar.header("🔍 Filters")

search_term = st.sidebar.selectbox(
    "Search Term",
    (df["search_term"].unique())
)
cohort_filter = st.sidebar.selectbox(
    "Ranking Cohort",
    (df["ranking_cohort"].dropna().astype(str).unique())
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
filtered_df = filtered_df[filtered_df["ranking_cohort"] == cohort_filter]

if filtered_df.empty:
    st.warning("No data available for selected filters")
    st.stop()

# -----------------------------
# Ranking Formula Inputs
# -----------------------------
st.sidebar.header("🧮 Ranking Formulas")

formula_a = st.sidebar.text_area(
    "Formula A",
    value="ranking_score * (1 + pop_boost)",
    height=80
)

formula_b = st.sidebar.text_area(
    "Formula B",
    value="ranking_score * (1 + 1.5 * asp_boost)",
    height=80
)

st.sidebar.markdown(
    """
**Allowed variables**
- ranking_score
- asp_boost
- pop_boost
- asp
- med_asp
- p25_asp
- sku_pop
- brand_pop

**Allowed operators**
+  -  *  /  ( )

**Allowed functions**
min(a, b)
max(a, b)
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
ALLOWED_FUNCTIONS = {
    "min": lambda a, b: a.combine(b, min) if hasattr(a, "combine") else min(a, b),
    "max": lambda a, b: a.combine(b, max) if hasattr(a, "combine") else max(a, b),
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

        # Function calls (min(a,b), max(a,b))
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise TypeError("Only simple function calls allowed")

            func_name = node.func.id

            if func_name not in ALLOWED_FUNCTIONS:
                raise ValueError(f"Function '{func_name}' not allowed")

            args = [_eval(arg) for arg in node.args]

            if len(args) != 2:
                raise ValueError("Only two-argument min/max supported")

            return ALLOWED_FUNCTIONS[func_name](*args)


        else:
            raise TypeError("Unsupported expression")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed.body)


def evaluate_formula(filtered_df, expr):
    return safe_eval_expr(
        expr,
        {
            "ranking_score": filtered_df["ranking_score"],
            "asp_boost": filtered_df["asp_boost"],
            "pop_boost": filtered_df["pop_boost"],
            "asp": filtered_df["selling_price"],
            "med_asp": filtered_df["med_asp"],
            "p25_asp": filtered_df["p25_asp"],
            "sku_pop": filtered_df["sku_pop"],
            "brand_pop": filtered_df["brand_pop"]
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
df_sim["rank_a"] = df_sim["rank_a"].astype(int)
df_sim["rank_b"] = df_sim["rank_b"].astype(int)
df_sim["rank_delta"] = (-1)*df_sim["rank_delta"].astype(int)

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
    "asp_boost",
    "med_asp",
    "p25_asp",
    "sku_pop",
    "brand_pop"
]

display_df = (
    topk_df[display_cols]
        .sort_values("rank_a")
        .reset_index(drop=True)
)

def green_gradient(val):
    if val > top_k:
        return ""

    intensity = 1 - ((val - 1) / (top_k - 1))

    if is_dark:
        # Brighter green for dark background
        green = int(120 + (135 * intensity))   # 120–255
        return f"background-color: rgb(0, {green}, 0); color: white"
    else:
        # Softer green for light background
        green = int(200 + (55 * intensity))    # 200–255
        return f"background-color: rgb(220, {green}, 220); color: black"


styled_df = display_df.style.map(
    green_gradient,
    subset=["rank_a", "rank_b"]
)

st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True
)



# -----------------------------
# Summary Metrics
# -----------------------------
st.subheader("📈 Summary Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    overlap = len(
        set(topk_df[topk_df["rank_a"] <= top_k]["product_variant_id"])
        & set(topk_df[topk_df["rank_b"] <= top_k]["product_variant_id"])
    )
    st.metric("Top-K Overlap", f"{overlap}/{top_k}")

with col2:
    avg_shift = topk_df["rank_delta"].abs().mean()
    st.metric("Avg |Rank Change|", f"{avg_shift:.2f}")

with col3:
    improved = (topk_df["rank_delta"] < 0).sum()
    st.metric("Products Improved", improved)

with col4:
    dropped = (topk_df["rank_delta"] > 0).sum()
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
