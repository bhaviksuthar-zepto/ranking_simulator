# =========================================================
# Ranking Simulation Tool - Streamlit App (Safe Eval Version)
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

    **Allowed operators**
    +  -  *  /  ()
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

        elif isinstance(node, ast.BinOp):  # binary operations
            if type(node.op) not in ALLOWED_OPERATORS:
                raise TypeError("Operator not allowed")
            return ALLOWED_OPERATORS[type(node.op)](
                _eval(node.left),
                _eval(node.right)
            )

        elif isinstance(node, ast.UnaryOp):  # -x
            if isinstance(node.op, ast.USub):
                return -_eval(nod_
