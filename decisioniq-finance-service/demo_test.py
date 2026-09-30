"""
DecisionIQ Finance ML — Demo / Test Interface
================================================
A Streamlit-based local testing tool for the existing Finance ML models.
Run with:  streamlit run demo_test.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import sys

# ---------------------------------------------------------------------------
# Path setup — must come before app imports
# ---------------------------------------------------------------------------
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SERVICE_DIR)
sys.path.insert(0, SERVICE_DIR)

from app.schemas.finance_schema import RiskPredictRequest
from app.services.finance_service import FinanceService
from app.services.early_warning import generate_early_warning

# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="DecisionIQ — Finance Demo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* ---------- global ---------- */
    .block-container { padding-top: 1.5rem; }

    /* ---------- header banner ---------- */
    .hero-banner {
        background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
        border-radius: 14px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        color: #ffffff;
    }
    .hero-banner h1 { margin: 0; font-size: 2rem; font-weight: 700; }
    .hero-banner p  { margin: 0.4rem 0 0; opacity: 0.85; font-size: 1rem; }

    /* ---------- section cards ---------- */
    .card {
        background: #ffffff0a;
        border: 1px solid #ffffff15;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1rem;
    }

    /* ---------- risk badge ---------- */
    .risk-high {
        display: inline-block;
        background: linear-gradient(135deg, #e74c3c, #c0392b);
        color: #fff;
        padding: 6px 18px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: 0.5px;
    }
    .risk-low {
        display: inline-block;
        background: linear-gradient(135deg, #27ae60, #1e8449);
        color: #fff;
        padding: 6px 18px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: 0.5px;
    }

    /* ---------- warning badges ---------- */
    .warn-critical { color: #e74c3c; font-weight: 700; }
    .warn-elevated { color: #e67e22; font-weight: 700; }
    .warn-watch    { color: #f1c40f; font-weight: 700; }
    .warn-normal   { color: #2ecc71; font-weight: 700; }

    /* ---------- shap bar labels ---------- */
    .shap-up   { color: #e74c3c; font-weight: 600; }
    .shap-down { color: #27ae60; font-weight: 600; }

    /* ---------- disclaimer ---------- */
    .disclaimer {
        background: #1a1a2e;
        border-left: 4px solid #f1c40f;
        border-radius: 6px;
        padding: 0.8rem 1.2rem;
        font-size: 0.82rem;
        color: #ccc;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load the Finance Service (cached so models load once)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading Finance ML models …")
def load_service():
    return FinanceService(SERVICE_DIR)

service = load_service()

# ---------------------------------------------------------------------------
# Hero banner
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero-banner">
    <h1>📊 DecisionIQ — Finance ML Test Interface</h1>
    <p>Interact with the existing trained models as a business user. No metrics jargon — just forecasts, risks, and explanations.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 1. COMPANY SELECTION  (sidebar)
# ---------------------------------------------------------------------------
csv_path = os.path.join(SERVICE_DIR, "demo_sme_companies.csv")
if not os.path.exists(csv_path):
    st.error(f"❌ Demo CSV not found at `{csv_path}`. Please create it first.")
    st.stop()

df_companies = pd.read_csv(csv_path)

with st.sidebar:
    st.header("🏢 Company Selection")
    company_name = st.selectbox("Choose a company", df_companies["company"].tolist())
    row = df_companies[df_companies["company"] == company_name].iloc[0]

    st.markdown("---")
    st.subheader("Company Profile")
    st.markdown(f"**Sector:** {row['sector']}")
    st.markdown(f"**Employees:** {row['employees']}")
    st.markdown(f"**Revenue:** ${row['revenue']:,.0f}")
    st.markdown(f"**OPEX:** ${row['opex']:,.0f}")
    st.markdown(f"**AR Days:** {row['ar_days']}")
    st.markdown(f"**Inventory Days:** {row['inventory_days']}")
    st.markdown(f"**Loan:** ${row['loan']:,.0f}")

# ---------------------------------------------------------------------------
# Map CSV → model schema
# ---------------------------------------------------------------------------
try:
    req = RiskPredictRequest(
        sector=str(row["sector"]),
        employees=int(row["employees"]),
        revenue_usd=float(row["revenue"]),
        opex_usd=float(row["opex"]),
        accounts_receivable_days=float(row["ar_days"]),
        inventory_days=float(row["inventory_days"]),
        loan_balance_usd=float(row["loan"]),
        owner_injections_usd=0.0,
    )
except Exception as e:
    st.error(f"⚠️ Feature / preprocessing mapping error: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# 2. RISK PREDICTION
# ---------------------------------------------------------------------------
try:
    risk_res = service.predict_risk(req)
except Exception as e:
    st.error(f"⚠️ Model prediction error: {e}")
    st.stop()

prob_pct = risk_res.risk_probability * 100
badge_cls = "risk-high" if risk_res.risk_class == 1 else "risk-low"
badge_lbl = "HIGH RISK" if risk_res.risk_class == 1 else "LOW RISK"

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader(f"💼 {company_name}")
    st.markdown("#### Cash-Flow Stress Risk")
    st.markdown(f"<h1 style='margin:0;'>{prob_pct:.1f}%</h1>", unsafe_allow_html=True)
    st.markdown(f'<span class="{badge_cls}">{badge_lbl}</span>', unsafe_allow_html=True)
    st.caption("Predicted cash-flow stress probability from the XGBoost model.")

# ---------------------------------------------------------------------------
# 3. SHAP EXPLANATION  (horizontal bar chart)
# ---------------------------------------------------------------------------
with col_right:
    st.markdown("#### 🔍 Why is the risk at this level?")
    shap_features = risk_res.shap_features
    if shap_features:
        names = [f.feature.replace("_", " ").title() for f in shap_features]
        magnitudes = [f.magnitude for f in shap_features]
        colors = ["#e74c3c" if f.direction == "increases_risk" else "#27ae60" for f in shap_features]

        fig_shap, ax_shap = plt.subplots(figsize=(6, max(2.2, 0.55 * len(names))))
        fig_shap.patch.set_facecolor("#0e1117")
        ax_shap.set_facecolor("#0e1117")

        y_pos = np.arange(len(names))
        ax_shap.barh(y_pos, magnitudes, color=colors, height=0.55, edgecolor="none")
        ax_shap.set_yticks(y_pos)
        ax_shap.set_yticklabels(names, fontsize=10, color="#ddd")
        ax_shap.invert_yaxis()
        ax_shap.set_xlabel("Impact on prediction", fontsize=10, color="#aaa")
        ax_shap.tick_params(axis="x", colors="#aaa", labelsize=9)
        ax_shap.spines["top"].set_visible(False)
        ax_shap.spines["right"].set_visible(False)
        ax_shap.spines["bottom"].set_color("#444")
        ax_shap.spines["left"].set_color("#444")
        plt.tight_layout()
        st.pyplot(fig_shap)
        plt.close(fig_shap)

        legend_md = "  ".join(
            f'<span class="shap-{"up" if f.direction == "increases_risk" else "down"}">'
            f'{"↑" if f.direction == "increases_risk" else "↓"} {f.feature.replace("_"," ").title()}</span>'
            for f in shap_features
        )
        st.markdown(legend_md, unsafe_allow_html=True)
    else:
        st.info("No SHAP explanation available for this input.")

st.markdown("---")

# ---------------------------------------------------------------------------
# 4. EARLY WARNING
# ---------------------------------------------------------------------------
# We generate the early-warning later once we have forecast data, but calculate
# the cash-stress portion early so we can show it inline.
cash_warning = generate_early_warning(
    forecast_future=[],  # placeholder — updated below if forecast available
    cash_stress_probability=risk_res.risk_probability,
    distress_probability=None,
)

# ---------------------------------------------------------------------------
# 5. REVENUE FORECAST GRAPH  (matplotlib)
# ---------------------------------------------------------------------------
st.subheader("📈 90-Day Revenue Forecast")

try:
    summary = service.get_summary()
    historical = summary.forecast.historical
    future = summary.forecast.future
except Exception as e:
    st.warning(f"⚠️ Forecast could not be loaded: {e}")
    historical, future = [], []

if not historical and not future:
    st.warning("No forecast data available. Ensure the Prophet model is trained and the Online Retail dataset exists.")
else:
    # Build DataFrames
    def items_to_df(items):
        rows = [item.model_dump() if hasattr(item, "model_dump") else item for item in items]
        d = pd.DataFrame(rows)
        if not d.empty:
            d["ds"] = pd.to_datetime(d["ds"])
        return d

    df_hist = items_to_df(historical)
    df_fut = items_to_df(future)

    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    # --- Historical ---
    if not df_hist.empty:
        ax.plot(df_hist["ds"], df_hist["yhat"], color="#3498db", linewidth=1.2, label="Historical Revenue")

    # --- Forecast ---
    if not df_fut.empty:
        ax.plot(df_fut["ds"], df_fut["yhat"], color="#e67e22", linewidth=2, label="Forecast Revenue")
        if "yhat_lower" in df_fut.columns and "yhat_upper" in df_fut.columns:
            ax.fill_between(
                df_fut["ds"],
                df_fut["yhat_lower"],
                df_fut["yhat_upper"],
                color="#e67e22",
                alpha=0.15,
                label="Confidence Interval",
            )

    # --- Divider line ---
    if not df_hist.empty and not df_fut.empty:
        boundary = df_hist["ds"].max()
        ax.axvline(boundary, color="#95a5a6", linestyle="--", linewidth=1, alpha=0.7)
        ax.text(
            boundary, ax.get_ylim()[1] * 0.95,
            "  Forecast →", color="#95a5a6", fontsize=9, va="top",
        )

    ax.set_title("90-Day Revenue Forecast (Prophet)", fontsize=14, color="#eee", pad=12)
    ax.set_xlabel("Date", fontsize=11, color="#aaa")
    ax.set_ylabel("Revenue", fontsize=11, color="#aaa")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    fig.autofmt_xdate(rotation=30)
    ax.tick_params(colors="#aaa", labelsize=9)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.3, labelcolor="#ddd")
    for spine in ax.spines.values():
        spine.set_color("#333")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.caption(f"Forecast horizon: **90 days** · Historical data points: **{len(df_hist)}** · Forecast points: **{len(df_fut)}**")

    # --- Forecast Data Table ---
    with st.expander("📋 Forecast Data Table"):
        if not df_fut.empty:
            display_df = df_fut[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
            display_df.columns = ["Date", "Forecast Revenue", "Lower Bound", "Upper Bound"]
            display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # --- Update early warning with real forecast ---
    future_dict = [f.model_dump() if hasattr(f, "model_dump") else f for f in future]
    cash_warning = generate_early_warning(
        forecast_future=future_dict,
        cash_stress_probability=risk_res.risk_probability,
        distress_probability=None,
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# 6. EARLY WARNING
# ---------------------------------------------------------------------------
st.subheader("⚠️ Early Warning Signal")
signal = cash_warning["overall_financial_signal"]
signal_cls = {
    "critical": "warn-critical",
    "elevated": "warn-elevated",
    "watch": "warn-watch",
    "normal": "warn-normal",
}.get(signal, "warn-normal")

st.markdown(f'Signal: <span class="{signal_cls}">{signal.upper()}</span>', unsafe_allow_html=True)
st.markdown(f"**Reason:** {cash_warning['overall_message']}")

if cash_warning["active_warnings"]:
    for w in cash_warning["active_warnings"]:
        st.markdown(f"- `{w}`")

st.markdown("---")

# ---------------------------------------------------------------------------
# 7. WHAT-IF SCENARIO
# ---------------------------------------------------------------------------
st.subheader("🔄 What-If Scenario Simulation")
st.markdown("Adjust one or more financial inputs below. The **same XGBoost model** re-evaluates the modified inputs.")

wi_col1, wi_col2 = st.columns(2)

with wi_col1:
    st.markdown("**Current values** → modify with sliders / inputs")
    new_revenue = st.slider(
        "Revenue ($)",
        min_value=0.0,
        max_value=float(row["revenue"]) * 3,
        value=float(row["revenue"]),
        step=1000.0,
        format="$%,.0f",
    )
    new_opex = st.slider(
        "OPEX ($)",
        min_value=0.0,
        max_value=float(row["opex"]) * 3,
        value=float(row["opex"]),
        step=1000.0,
        format="$%,.0f",
    )
    new_loan = st.slider(
        "Loan ($)",
        min_value=0.0,
        max_value=float(row["loan"]) * 3,
        value=float(row["loan"]),
        step=1000.0,
        format="$%,.0f",
    )

with wi_col2:
    st.markdown("&nbsp;")  # spacer
    new_ar = st.slider(
        "AR Days",
        min_value=0.0,
        max_value=180.0,
        value=float(row["ar_days"]),
        step=5.0,
    )
    new_inv = st.slider(
        "Inventory Days",
        min_value=0.0,
        max_value=180.0,
        value=float(row["inventory_days"]),
        step=5.0,
    )

if st.button("▶  Run What-If Scenario", type="primary"):
    try:
        scenario_req = RiskPredictRequest(
            sector=str(row["sector"]),
            employees=int(row["employees"]),
            revenue_usd=new_revenue,
            opex_usd=new_opex,
            accounts_receivable_days=new_ar,
            inventory_days=new_inv,
            loan_balance_usd=new_loan,
            owner_injections_usd=0.0,
        )
        scenario_res = service.predict_risk(scenario_req)

        curr_risk = risk_res.risk_probability * 100
        scen_risk = scenario_res.risk_probability * 100
        diff = scen_risk - curr_risk

        r1, r2, r3 = st.columns(3)
        r1.metric("Current Risk", f"{curr_risk:.1f}%")
        r2.metric("Scenario Risk", f"{scen_risk:.1f}%", delta=f"{diff:+.1f} pp", delta_color="inverse")

        if diff > 0.5:
            interp = "📈 **Risk increased** under this scenario."
        elif diff < -0.5:
            interp = "📉 **Risk decreased** under this scenario."
        else:
            interp = "➡️ **Risk remained approximately unchanged.**"
        r3.markdown(f"<br>{interp}", unsafe_allow_html=True)

        # Show scenario SHAP
        with st.expander("🔍 Scenario SHAP Explanation"):
            for feat in scenario_res.shap_features:
                arrow = "↑" if feat.direction == "increases_risk" else "↓"
                colour = "red" if feat.direction == "increases_risk" else "green"
                st.markdown(f":{colour}[{arrow} **{feat.feature.replace('_',' ').title()}**] — impact {feat.magnitude:.4f}")

    except Exception as e:
        st.error(f"⚠️ What-If Error: {e}")

# ---------------------------------------------------------------------------
# Disclaimer footer
# ---------------------------------------------------------------------------
st.markdown("""
<div class="disclaimer">
    <strong>Disclaimer:</strong> Risk represents the model's predicted cash-flow stress probability
    based on the supplied financial inputs. It is an analytical signal, not a guarantee of
    future business performance. The model was trained on a synthetic prototype dataset and
    should be validated with real-world data before production use.
</div>
""", unsafe_allow_html=True)
