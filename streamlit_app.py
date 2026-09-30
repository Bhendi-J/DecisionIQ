import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="DecisionIQ - Security Intelligence",
    page_icon="🔐",
    layout="wide"
)

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

DATA_PATH = "outputs/anomaly_results.csv"

df = pd.read_csv(DATA_PATH)

# Convert boolean-like column if necessary
if df["is_anomaly"].dtype != bool:
    df["is_anomaly"] = df["is_anomaly"].astype(bool)

# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.title("🔐 DecisionIQ — Security Intelligence")
st.subheader("Login Anomaly Detection")

st.markdown(
    "Monitor login activity and identify potentially suspicious login behavior "
    "using Isolation Forest."
)

st.divider()

# --------------------------------------------------
# KPI CARDS
# --------------------------------------------------

total_logins = len(df)
anomalies = int(df["is_anomaly"].sum())
normal_logins = total_logins - anomalies
average_risk = round(df["risk_score"].mean(), 1)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Logins",
    total_logins
)

col2.metric(
    "Anomalies Detected",
    anomalies
)

col3.metric(
    "Normal Logins",
    normal_logins
)

col4.metric(
    "Average Risk",
    average_risk
)

st.divider()

# --------------------------------------------------
# ANOMALY DISTRIBUTION
# --------------------------------------------------

st.subheader("📊 Login Anomaly Distribution")

normal_count = int((df["is_anomaly"] == False).sum())
anomaly_count = int((df["is_anomaly"] == True).sum())

distribution_df = pd.DataFrame({
    "Status": ["Normal", "Anomaly"],
    "Count": [normal_count, anomaly_count]
})

fig_distribution = px.bar(
    distribution_df,
    x="Status",
    y="Count",
    title="Normal vs Anomalous Logins",
    text="Count"
)

fig_distribution.update_traces(
    textposition="outside"
)

fig_distribution.update_layout(
    height=400,
    showlegend=False
)

st.plotly_chart(
    fig_distribution,
    use_container_width=True
)

# --------------------------------------------------
# TWO COLUMN ANALYSIS
# --------------------------------------------------

left, right = st.columns(2)

# --------------------------------------------------
# RISK SCORE DISTRIBUTION
# --------------------------------------------------

with left:

    st.subheader("📈 Risk Score Distribution")

    fig_risk = px.histogram(
        df,
        x="risk_score",
        nbins=20,
        title="Distribution of Login Risk Scores"
    )

    fig_risk.update_layout(
        height=400
    )

    st.plotly_chart(
        fig_risk,
        use_container_width=True
    )

# --------------------------------------------------
# FEATURE ANALYSIS
# --------------------------------------------------

with right:

    st.subheader("🔎 Login Feature Analysis")

    feature_data = pd.DataFrame({
        "Feature": [
            "Failed Attempts",
            "New Device",
            "Location Difference",
            "Login Frequency"
        ],
        "Average": [
            df["failed_attempts"].mean(),
            df["new_device"].mean(),
            df["location_difference"].mean(),
            df["login_frequency"].mean()
        ]
    })

    fig_features = px.bar(
        feature_data,
        x="Feature",
        y="Average",
        title="Average Login Feature Values"
    )

    fig_features.update_layout(
        height=400,
        xaxis_tickangle=-30
    )

    st.plotly_chart(
        fig_features,
        use_container_width=True
    )

st.divider()

# --------------------------------------------------
# RECENT / DETECTED ANOMALIES
# --------------------------------------------------

st.subheader("🚨 Detected Anomalies")

anomaly_df = df[df["is_anomaly"] == True].copy()

display_columns = [
    "login_hour",
    "failed_attempts",
    "new_device",
    "login_frequency",
    "location_difference",
    "anomaly_score",
    "risk_score"
]

st.dataframe(
    anomaly_df[display_columns].head(10),
    use_container_width=True,
    hide_index=True
)

st.divider()

# --------------------------------------------------
# LIVE LOGIN ANALYSIS
# --------------------------------------------------

st.subheader("🔐 Analyze a Login")

st.write(
    "Enter login details below and send them to the Isolation Forest model."
)

col1, col2, col3 = st.columns(3)

with col1:

    login_hour = st.number_input(
        "Login Hour",
        min_value=0,
        max_value=23,
        value=10
    )

    failed_attempts = st.number_input(
        "Failed Attempts",
        min_value=0,
        max_value=50,
        value=0
    )

with col2:

    new_device = st.selectbox(
        "New Device",
        ["No", "Yes"]
    )

    login_frequency = st.number_input(
        "Login Frequency",
        min_value=0,
        max_value=100,
        value=5
    )

with col3:

    location_difference = st.selectbox(
        "Location Difference",
        ["No", "Yes"]
    )

st.write("")

analyze_button = st.button(
    "🔍 Analyze Login",
    use_container_width=True
)

# --------------------------------------------------
# CALL FASTAPI
# --------------------------------------------------

if analyze_button:

    payload = {
        "login_hour": login_hour,
        "failed_attempts": failed_attempts,
        "new_device": 1 if new_device == "Yes" else 0,
        "login_frequency": login_frequency,
        "location_difference": 1 if location_difference == "Yes" else 0
    }

    API_URL = "http://127.0.0.1:8000/anomaly/score"

    try:

        response = requests.post(
            API_URL,
            json=payload
        )

        if response.status_code == 200:

            result = response.json()

            st.divider()

            if result["is_anomaly"]:

                st.error(
                    "🚨 ANOMALOUS LOGIN DETECTED"
                )

            else:

                st.success(
                    "✅ LOGIN APPEARS NORMAL"
                )

            result_col1, result_col2 = st.columns(2)

            with result_col1:

                st.metric(
                    "Anomaly Score",
                    result["anomaly_score"]
                )

            with result_col2:

                st.metric(
                    "Risk Score",
                    result["risk_score"]
                )

        else:

            st.error(
                f"API Error: {response.status_code}"
            )

    except requests.exceptions.ConnectionError:

        st.error(
            "Could not connect to FastAPI. "
            "Make sure the FastAPI server is running."
        )