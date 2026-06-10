import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from io import BytesIO


# ---------------------------------------------------------
# Project 4: Airline Revenue Management Dashboard
# Fare-Class Protection and Seat Inventory Optimization
# ---------------------------------------------------------


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "outputs"


# ---------------------------------------------------------
# Page Config
# ---------------------------------------------------------

st.set_page_config(
    page_title="Airline Revenue Management Dashboard",
    page_icon="✈️",
    layout="wide"
)


# ---------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------

st.markdown(
    """
    <style>
    .main {
        background-color: #f7f9fc;
    }

    .hero-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #0284c7 100%);
        padding: 2.2rem 2.4rem;
        border-radius: 22px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.22);
    }

    .hero-title {
        font-size: 2.35rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
        letter-spacing: -0.03em;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #dbeafe;
        max-width: 980px;
        line-height: 1.55;
    }

    .section-card {
        background-color: #ffffff;
        color: #0f172a !important;
        padding: 1.25rem 1.35rem;
        border-radius: 18px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
        margin-bottom: 1rem;
        line-height: 1.6;
        font-size: 1rem;
    }

    .section-card b {
        color: #0f172a !important;
    }

    .metric-card {
        background-color: white;
        padding: 1.1rem 1.2rem;
        border-radius: 18px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 5px 16px rgba(15, 23, 42, 0.07);
        height: 128px;
    }

    .metric-label {
        font-size: 0.82rem;
        color: #64748b;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.35rem;
    }

    .metric-value {
        font-size: 1.65rem;
        color: #0f172a;
        font-weight: 800;
        margin-bottom: 0.15rem;
    }

    .metric-note {
        font-size: 0.82rem;
        color: #64748b;
    }

    .positive {
        color: #15803d;
        font-weight: 800;
    }

    .negative {
        color: #b91c1c;
        font-weight: 800;
    }

    .info-box {
        background-color: #eff6ff;
        border-left: 5px solid #2563eb;
        padding: 1rem 1.1rem;
        border-radius: 14px;
        color: #172554;
        margin-bottom: 1rem;
        line-height: 1.55;
    }

    .warning-box {
        background-color: #fffbeb;
        border-left: 5px solid #f59e0b;
        padding: 1rem 1.1rem;
        border-radius: 14px;
        color: #78350f;
        margin-bottom: 1rem;
        line-height: 1.55;
    }

    .success-box {
        background-color: #ecfdf5;
        border-left: 5px solid #10b981;
        padding: 1rem 1.1rem;
        border-radius: 14px;
        color: #064e3b;
        margin-bottom: 1rem;
        line-height: 1.55;
    }

    div[data-testid="stSidebar"] {
        background-color: #0f172a;
    }

    div[data-testid="stSidebar"] * {
        color: white;
    }

    div[data-testid="stSidebar"] .stSelectbox label,
    div[data-testid="stSidebar"] .stRadio label,
    div[data-testid="stSidebar"] .stCheckbox label,
    div[data-testid="stSidebar"] .stFileUploader label {
        color: white !important;
        font-weight: 700;
    }

    .small-caption {
        color: #64748b;
        font-size: 0.9rem;
        line-height: 1.45;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

@st.cache_data
def load_sample_data():
    """Load dashboard-ready output files from the outputs folder."""

    required_files = {
        "policy_summary": OUTPUT_DIR / "simulated_policy_summary.csv",
        "revenue_results": OUTPUT_DIR / "simulated_revenue_results.csv",
        "fare_class_results": OUTPUT_DIR / "simulated_fare_class_results.csv",
        "protection_levels": OUTPUT_DIR / "protection_levels.csv",
    }

    missing = [name for name, path in required_files.items() if not path.exists()]

    if missing:
        st.error(
            "Missing required output files. Please run the model pipeline first:\n\n"
            "1. python src/optimization_model.py\n"
            "2. python src/protection_level_model.py\n"
            "3. python src/simulation_revenue_model.py\n\n"
            f"Missing: {missing}"
        )
        st.stop()

    policy_summary = pd.read_csv(required_files["policy_summary"])
    revenue_results = pd.read_csv(required_files["revenue_results"])
    fare_class_results = pd.read_csv(required_files["fare_class_results"])
    protection_levels = pd.read_csv(required_files["protection_levels"])

    return policy_summary, revenue_results, fare_class_results, protection_levels


def load_uploaded_data(policy_file, revenue_file, fare_file, protection_file):
    """Load user-uploaded dashboard files."""

    policy_summary = pd.read_csv(policy_file)
    revenue_results = pd.read_csv(revenue_file)
    fare_class_results = pd.read_csv(fare_file)
    protection_levels = pd.read_csv(protection_file)

    return policy_summary, revenue_results, fare_class_results, protection_levels


def format_currency(value):
    return f"${value:,.0f}"


def format_percent(value):
    return f"{value * 100:.1f}%"


def dataframe_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    return output.getvalue()


def metric_card(label, value, note="", positive=None):
    if positive is True:
        value_class = "positive"
    elif positive is False:
        value_class = "negative"
    else:
        value_class = ""

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value {value_class}">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def clean_policy_summary(df):
    """Standardize numeric columns after upload or sample load."""

    numeric_cols = [
        "avg_baseline_revenue",
        "avg_protection_revenue",
        "avg_revenue_lift",
        "avg_revenue_lift_pct",
        "avg_baseline_sold_seats",
        "avg_protection_sold_seats",
        "avg_baseline_unused_seats",
        "avg_protection_unused_seats",
        "avg_baseline_denied_demand",
        "avg_protection_denied_demand",
        "avg_baseline_load_factor",
        "avg_protection_load_factor",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def get_business_interpretation(selected_row):
    revenue_lift = selected_row["avg_revenue_lift"]
    revenue_lift_pct = selected_row["avg_revenue_lift_pct"]
    baseline_lf = selected_row["avg_baseline_load_factor"]
    protection_lf = selected_row["avg_protection_load_factor"]
    unused_delta = (
        selected_row["avg_protection_unused_seats"]
        - selected_row["avg_baseline_unused_seats"]
    )

    if revenue_lift > 0:
        main_text = (
            f"The protection policy increases expected revenue by "
            f"{format_currency(revenue_lift)} per flight, or about "
            f"{revenue_lift_pct:.1f}% compared with the baseline policy. "
            "This suggests that protecting seats for higher-fare passengers is valuable "
            "under the selected demand scenario."
        )
    else:
        main_text = (
            f"The protection policy decreases expected revenue by "
            f"{format_currency(abs(revenue_lift))} in this selected case. "
            "This can happen when high-fare demand does not materialize and protected "
            "seats remain unused."
        )

    if protection_lf < baseline_lf:
        tradeoff_text = (
            f"The protection policy has a lower load factor "
            f"({format_percent(protection_lf)} vs. {format_percent(baseline_lf)}). "
            f"On average, it leaves about {unused_delta:.1f} more seats unused than the baseline. "
            "This is a common revenue-management tradeoff: fewer seats may be sold, "
            "but the seats that are sold are more valuable."
        )
    else:
        tradeoff_text = (
            f"The protection policy improves or maintains load factor "
            f"({format_percent(protection_lf)} vs. {format_percent(baseline_lf)}), "
            "while also improving revenue. This is a strong result for the selected scenario."
        )

    return main_text, tradeoff_text


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.markdown(
    """
    <div class="hero-container">
        <div class="hero-title">✈️ Airline Revenue Management Dashboard</div>
        <div class="hero-subtitle">
            Fare-class protection, booking-limit analysis, and simulation-based seat inventory optimization
            under uncertain passenger demand. This dashboard compares a simple baseline booking policy with
            a revenue-management protection policy that reserves capacity for higher-fare passengers.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

st.sidebar.markdown("## ✈️ Control Panel")

data_source = st.sidebar.radio(
    "Data Source",
    ["Use sample output files", "Upload custom output files"]
)

if data_source == "Use sample output files":
    policy_summary, revenue_results, fare_class_results, protection_levels = load_sample_data()
else:
    st.sidebar.markdown("### Upload Required Files")

    policy_file = st.sidebar.file_uploader(
        "simulated_policy_summary.csv",
        type=["csv"]
    )

    revenue_file = st.sidebar.file_uploader(
        "simulated_revenue_results.csv",
        type=["csv"]
    )

    fare_file = st.sidebar.file_uploader(
        "simulated_fare_class_results.csv",
        type=["csv"]
    )

    protection_file = st.sidebar.file_uploader(
        "protection_levels.csv",
        type=["csv"]
    )

    if not all([policy_file, revenue_file, fare_file, protection_file]):
        st.warning("Upload all four required files to run the dashboard.")
        st.stop()

    policy_summary, revenue_results, fare_class_results, protection_levels = load_uploaded_data(
        policy_file,
        revenue_file,
        fare_file,
        protection_file
    )

policy_summary = clean_policy_summary(policy_summary)

# Route type is kept as a descriptive field only.
filtered_policy_summary = policy_summary.copy()

st.sidebar.markdown("---")
st.sidebar.markdown("### Flight Selection")

flight_options = (
    policy_summary[["flight_id", "flight_number", "origin", "destination"]]
    .drop_duplicates()
    .sort_values("flight_id")
)

flight_options["label"] = (
    flight_options["flight_id"]
    + " | "
    + flight_options["flight_number"].astype(str)
    + " | "
    + flight_options["origin"]
    + " → "
    + flight_options["destination"]
)

selected_flight_label = st.sidebar.selectbox(
    "Select Flight",
    flight_options["label"].tolist()
)

selected_flight_id = flight_options.loc[
    flight_options["label"] == selected_flight_label,
    "flight_id"
].iloc[0]

scenario_options = (
    policy_summary[policy_summary["flight_id"] == selected_flight_id]
    [["scenario_id", "scenario_name"]]
    .drop_duplicates()
)

scenario_options["label"] = (
    scenario_options["scenario_id"] + " | " + scenario_options["scenario_name"]
)

selected_scenario_label = st.sidebar.selectbox(
    "Select Scenario",
    scenario_options["label"].tolist()
)

selected_scenario_id = scenario_options.loc[
    scenario_options["label"] == selected_scenario_label,
    "scenario_id"
].iloc[0]

st.sidebar.markdown("---")
st.sidebar.markdown("### Display Options")

show_tables = st.sidebar.checkbox("Show detailed tables", value=True)
show_interpretation = st.sidebar.checkbox("Show interpretation notes", value=True)


# ---------------------------------------------------------
# Selected Data
# ---------------------------------------------------------

selected_row = policy_summary[
    (policy_summary["flight_id"] == selected_flight_id)
    & (policy_summary["scenario_id"] == selected_scenario_id)
].iloc[0]

selected_revenue_results = revenue_results[
    (revenue_results["flight_id"] == selected_flight_id)
    & (revenue_results["scenario_id"] == selected_scenario_id)
].copy()

selected_fare_results = fare_class_results[
    (fare_class_results["flight_id"] == selected_flight_id)
    & (fare_class_results["scenario_id"] == selected_scenario_id)
].copy()

selected_protection = protection_levels[
    (protection_levels["flight_id"] == selected_flight_id)
    & (protection_levels["scenario_id"] == selected_scenario_id)
].copy()


# ---------------------------------------------------------
# KPI Cards for Selected Flight
# ---------------------------------------------------------

st.markdown("## Selected Flight Executive Summary")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    metric_card(
        "Baseline Revenue",
        format_currency(selected_row["avg_baseline_revenue"]),
        "Average over simulations"
    )

with kpi2:
    metric_card(
        "Protection Revenue",
        format_currency(selected_row["avg_protection_revenue"]),
        "Average over simulations",
        positive=True
    )

with kpi3:
    metric_card(
        "Revenue Lift",
        format_currency(selected_row["avg_revenue_lift"]),
        f"{selected_row['avg_revenue_lift_pct']:.1f}% improvement",
        positive=selected_row["avg_revenue_lift"] >= 0
    )

with kpi4:
    metric_card(
        "Protection Load Factor",
        format_percent(selected_row["avg_protection_load_factor"]),
        f"Baseline: {format_percent(selected_row['avg_baseline_load_factor'])}"
    )

kpi5, kpi6, kpi7, kpi8 = st.columns(4)

with kpi5:
    metric_card(
        "Unused Seats",
        f"{selected_row['avg_protection_unused_seats']:.1f}",
        "Avg. protection policy spoilage"
    )

with kpi6:
    metric_card(
        "Denied Demand",
        f"{selected_row['avg_protection_denied_demand']:.1f}",
        "Avg. rejected requests"
    )

with kpi7:
    metric_card(
        "Aircraft Capacity",
        f"{int(selected_row['seat_capacity'])}",
        selected_row["aircraft_type"]
    )

with kpi8:
    metric_card(
        "Route",
        f"{selected_row['origin']} → {selected_row['destination']}",
        selected_row["route_type"]
    )


# ---------------------------------------------------------
# Tabs
# ---------------------------------------------------------

tab_network, tab_overview, tab_flight, tab_scenario, tab_fare, tab_sim, tab_data = st.tabs(
    [
        "Network Overview",
        "Selected Flight Overview",
        "Flight Analysis",
        "Scenario Comparison",
        "Fare-Class Protection",
        "Simulation Results",
        "Data & Downloads",
    ]
)


# ---------------------------------------------------------
# Network Overview Tab
# ---------------------------------------------------------

with tab_network:
    st.markdown("### Network-Level Revenue Management Overview")

    st.markdown(
        """
        <div class="section-card">
            This tab summarizes how the fare-class protection policy performs across the full synthetic airline schedule.
            Instead of looking at one flight only, it evaluates whether the protection policy improves revenue across
            all flights, routes, and demand scenarios.
        </div>
        """,
        unsafe_allow_html=True
    )

    network_avg_baseline_revenue = filtered_policy_summary["avg_baseline_revenue"].mean()
    network_avg_protection_revenue = filtered_policy_summary["avg_protection_revenue"].mean()
    network_avg_revenue_lift = filtered_policy_summary["avg_revenue_lift"].mean()
    network_avg_revenue_lift_pct = filtered_policy_summary["avg_revenue_lift_pct"].mean()

    network_avg_baseline_lf = filtered_policy_summary["avg_baseline_load_factor"].mean()
    network_avg_protection_lf = filtered_policy_summary["avg_protection_load_factor"].mean()

    network_unused_delta = (
        filtered_policy_summary["avg_protection_unused_seats"].mean()
        - filtered_policy_summary["avg_baseline_unused_seats"].mean()
    )

    network_win_rate = (
        filtered_policy_summary["avg_protection_revenue"]
        > filtered_policy_summary["avg_baseline_revenue"]
    ).mean()

    n_flights = filtered_policy_summary["flight_id"].nunique()
    n_scenarios = filtered_policy_summary["scenario_id"].nunique()

    nkpi1, nkpi2, nkpi3, nkpi4 = st.columns(4)

    with nkpi1:
        metric_card(
            "Avg. Baseline Revenue",
            format_currency(network_avg_baseline_revenue),
            "Across flights and scenarios"
        )

    with nkpi2:
        metric_card(
            "Avg. Protection Revenue",
            format_currency(network_avg_protection_revenue),
            "Across flights and scenarios",
            positive=True
        )

    with nkpi3:
        metric_card(
            "Avg. Revenue Lift",
            format_currency(network_avg_revenue_lift),
            f"{network_avg_revenue_lift_pct:.1f}% average lift",
            positive=network_avg_revenue_lift >= 0
        )

    with nkpi4:
        metric_card(
            "Policy Win Rate",
            f"{network_win_rate * 100:.1f}%",
            "Flight-scenario cases where protection wins",
            positive=network_win_rate >= 0.5
        )

    nkpi5, nkpi6, nkpi7, nkpi8 = st.columns(4)

    with nkpi5:
        metric_card(
            "Baseline Load Factor",
            format_percent(network_avg_baseline_lf),
            "Average baseline utilization"
        )

    with nkpi6:
        metric_card(
            "Protection Load Factor",
            format_percent(network_avg_protection_lf),
            "Average protection utilization"
        )

    with nkpi7:
        metric_card(
            "Unused Seat Increase",
            f"{network_unused_delta:.1f}",
            "Additional unused seats under protection"
        )

    with nkpi8:
        metric_card(
            "Schedule Scope",
            f"{n_flights} flights",
            f"{n_scenarios} demand scenarios"
        )

    if show_interpretation:
        st.markdown(
            f"""
            <div class="success-box">
                <b>Network-level interpretation:</b><br>
                Across the analyzed schedule, the protection policy increases average expected revenue from
                <b>{format_currency(network_avg_baseline_revenue)}</b> to
                <b>{format_currency(network_avg_protection_revenue)}</b>, creating an average lift of
                <b>{format_currency(network_avg_revenue_lift)}</b> per flight-scenario case.
                This suggests that protecting capacity for higher-fare passengers is generally valuable across the network.
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="warning-box">
                <b>Tradeoff:</b><br>
                The protection policy reduces average load factor from
                <b>{format_percent(network_avg_baseline_lf)}</b> to
                <b>{format_percent(network_avg_protection_lf)}</b>.
                This means the policy earns more revenue on average, but it may leave more seats unused.
                That is a realistic revenue-management tradeoff between revenue quality and aircraft utilization.
            </div>
            """,
            unsafe_allow_html=True
        )

    c1, c2 = st.columns(2)

    with c1:
        scenario_network = (
            filtered_policy_summary
            .groupby("scenario_name", as_index=False)
            .agg(
                avg_revenue_lift=("avg_revenue_lift", "mean"),
                avg_revenue_lift_pct=("avg_revenue_lift_pct", "mean"),
                avg_baseline_revenue=("avg_baseline_revenue", "mean"),
                avg_protection_revenue=("avg_protection_revenue", "mean")
            )
        )

        fig = px.bar(
            scenario_network,
            x="scenario_name",
            y="avg_revenue_lift",
            text="avg_revenue_lift",
            title="Average Revenue Lift by Scenario"
        )

        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(
            xaxis_title="Scenario",
            yaxis_title="Average Revenue Lift",
            yaxis_tickprefix="$"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        route_network = (
            filtered_policy_summary
            .groupby("route_type", as_index=False)
            .agg(
                avg_revenue_lift=("avg_revenue_lift", "mean"),
                avg_revenue_lift_pct=("avg_revenue_lift_pct", "mean"),
                avg_baseline_load_factor=("avg_baseline_load_factor", "mean"),
                avg_protection_load_factor=("avg_protection_load_factor", "mean")
            )
        )

        fig = px.bar(
            route_network,
            x="route_type",
            y="avg_revenue_lift",
            text="avg_revenue_lift",
            title="Average Revenue Lift by Route Type"
        )

        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(
            xaxis_title="Route Type",
            yaxis_title="Average Revenue Lift",
            yaxis_tickprefix="$"
        )
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)

    with c3:
        network_revenue_long = filtered_policy_summary[
            [
                "flight_id",
                "scenario_name",
                "avg_baseline_revenue",
                "avg_protection_revenue"
            ]
        ].melt(
            id_vars=["flight_id", "scenario_name"],
            var_name="Policy",
            value_name="Average Revenue"
        )

        network_revenue_long["Policy"] = network_revenue_long["Policy"].replace({
            "avg_baseline_revenue": "Baseline",
            "avg_protection_revenue": "Protection"
        })

        fig = px.box(
            network_revenue_long,
            x="Policy",
            y="Average Revenue",
            title="Revenue Distribution Across All Flight-Scenario Cases"
        )

        fig.update_layout(
            yaxis_title="Average Revenue",
            yaxis_tickprefix="$"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        load_gap = (
            filtered_policy_summary
            .groupby("scenario_name", as_index=False)
            .agg(
                avg_baseline_load_factor=("avg_baseline_load_factor", "mean"),
                avg_protection_load_factor=("avg_protection_load_factor", "mean")
            )
        )

        load_gap["load_factor_gap_pp"] = (
            load_gap["avg_baseline_load_factor"]
            - load_gap["avg_protection_load_factor"]
        ) * 100

        fig = px.bar(
            load_gap,
            x="scenario_name",
            y="load_factor_gap_pp",
            text="load_factor_gap_pp",
            title="Load Factor Reduction from Protection Policy by Scenario"
        )

        fig.update_traces(texttemplate="%{text:.1f} pp", textposition="outside")
        fig.update_layout(
            xaxis_title="Scenario",
            yaxis_title="Load Factor Reduction",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Top Flight-Scenario Cases by Revenue Lift")

    top_cases = (
        filtered_policy_summary
        .sort_values("avg_revenue_lift", ascending=False)
        .head(10)
        .copy()
    )

    top_cases_display = top_cases[
        [
            "flight_id",
            "flight_number",
            "origin",
            "destination",
            "route_type",
            "scenario_name",
            "avg_baseline_revenue",
            "avg_protection_revenue",
            "avg_revenue_lift",
            "avg_revenue_lift_pct",
            "avg_baseline_load_factor",
            "avg_protection_load_factor"
        ]
    ].copy()

    top_cases_display["avg_baseline_revenue"] = top_cases_display["avg_baseline_revenue"].map(format_currency)
    top_cases_display["avg_protection_revenue"] = top_cases_display["avg_protection_revenue"].map(format_currency)
    top_cases_display["avg_revenue_lift"] = top_cases_display["avg_revenue_lift"].map(format_currency)
    top_cases_display["avg_revenue_lift_pct"] = top_cases_display["avg_revenue_lift_pct"].map(lambda x: f"{x:.1f}%")
    top_cases_display["avg_baseline_load_factor"] = top_cases_display["avg_baseline_load_factor"].map(format_percent)
    top_cases_display["avg_protection_load_factor"] = top_cases_display["avg_protection_load_factor"].map(format_percent)

    st.dataframe(top_cases_display, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# Selected Flight Overview Tab
# ---------------------------------------------------------

with tab_overview:
    st.markdown("### Selected Flight Overview")

    st.markdown(
        """
<div class="section-card">
This section focuses on the selected flight and demand scenario. It compares the simple baseline policy against the fare-class protection policy.
<br><br>
<b>The dashboard compares two policies:</b>
<br><br>
<b>Baseline Policy:</b> accepts low-fare demand first until the aircraft fills up.
<br><br>
<b>Protection Policy:</b> uses booking limits to restrict lower-fare sales and protect capacity for higher-fare demand.
</div>
        """,
        unsafe_allow_html=True
    )

    if show_interpretation:
        main_text, tradeoff_text = get_business_interpretation(selected_row)

        st.markdown(
            f"""
            <div class="success-box">
            <b>Business Interpretation:</b><br>
            {main_text}
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="warning-box">
            <b>Revenue Management Tradeoff:</b><br>
            {tradeoff_text}
            </div>
            """,
            unsafe_allow_html=True
        )

    c1, c2 = st.columns(2)

    with c1:
        revenue_compare = pd.DataFrame({
            "Policy": ["Baseline", "Protection"],
            "Expected Revenue": [
                selected_row["avg_baseline_revenue"],
                selected_row["avg_protection_revenue"],
            ]
        })

        fig = px.bar(
            revenue_compare,
            x="Policy",
            y="Expected Revenue",
            text="Expected Revenue",
            title="Baseline vs Protection Policy Revenue"
        )

        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(yaxis_tickprefix="$", yaxis_title="Expected Revenue")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        load_compare = pd.DataFrame({
            "Policy": ["Baseline", "Protection"],
            "Load Factor": [
                selected_row["avg_baseline_load_factor"],
                selected_row["avg_protection_load_factor"],
            ]
        })

        fig = px.bar(
            load_compare,
            x="Policy",
            y="Load Factor",
            text="Load Factor",
            title="Load Factor Tradeoff"
        )

        fig.update_traces(texttemplate="%{text:.1%}", textposition="outside")
        fig.update_layout(
            yaxis_tickformat=".0%",
            yaxis_title="Load Factor",
            yaxis_range=[0, 1.05]
        )
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# Flight Analysis Tab
# ---------------------------------------------------------

with tab_flight:
    st.markdown("### Selected Flight Analysis")

    st.markdown(
        f"""
        <div class="section-card">
        <b>Selected Flight:</b> {selected_row['flight_number']} 
        ({selected_row['origin']} → {selected_row['destination']})<br>
        <b>Aircraft:</b> {selected_row['aircraft_type']} with {int(selected_row['seat_capacity'])} seats<br>
        <b>Scenario:</b> {selected_row['scenario_name']}<br>
        <b>Route Type:</b> {selected_row['route_type']}
        </div>
        """,
        unsafe_allow_html=True
    )

    if show_interpretation:
        st.markdown(
            """
            <div class="info-box">
            This tab shows how stable the selected flight result is across simulated passenger demand outcomes.
            A higher protection revenue distribution indicates that the protection policy performs better under uncertainty.
            </div>
            """,
            unsafe_allow_html=True
        )

    c1, c2 = st.columns(2)

    with c1:
        revenue_distribution = selected_revenue_results[
            ["baseline_revenue", "protection_revenue"]
        ].melt(
            var_name="Policy",
            value_name="Revenue"
        )

        revenue_distribution["Policy"] = revenue_distribution["Policy"].replace({
            "baseline_revenue": "Baseline",
            "protection_revenue": "Protection"
        })

        fig = px.box(
            revenue_distribution,
            x="Policy",
            y="Revenue",
            points=False,
            title="Revenue Distribution Across Simulations"
        )

        fig.update_layout(yaxis_tickprefix="$", yaxis_title="Revenue")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        lift_fig = px.histogram(
            selected_revenue_results,
            x="revenue_lift",
            nbins=35,
            title="Distribution of Revenue Lift"
        )

        lift_fig.update_layout(
            xaxis_title="Protection Revenue - Baseline Revenue",
            yaxis_title="Simulation Count",
            xaxis_tickprefix="$"
        )
        st.plotly_chart(lift_fig, use_container_width=True)

    c3, c4 = st.columns(2)

    with c3:
        seat_compare = pd.DataFrame({
            "Metric": ["Sold Seats", "Unused Seats", "Denied Demand"],
            "Baseline": [
                selected_row["avg_baseline_sold_seats"],
                selected_row["avg_baseline_unused_seats"],
                selected_row["avg_baseline_denied_demand"],
            ],
            "Protection": [
                selected_row["avg_protection_sold_seats"],
                selected_row["avg_protection_unused_seats"],
                selected_row["avg_protection_denied_demand"],
            ],
        })

        seat_compare_long = seat_compare.melt(
            id_vars="Metric",
            var_name="Policy",
            value_name="Average Count"
        )

        fig = px.bar(
            seat_compare_long,
            x="Metric",
            y="Average Count",
            color="Policy",
            barmode="group",
            title="Seat Utilization and Demand Tradeoff"
        )

        st.plotly_chart(fig, use_container_width=True)

    with c4:
        selected_policy_row = pd.DataFrame([selected_row]).T.reset_index()
        selected_policy_row.columns = ["Metric", "Value"]

        st.markdown("#### Selected Scenario Metrics")
        st.dataframe(selected_policy_row, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# Scenario Comparison Tab
# ---------------------------------------------------------

with tab_scenario:
    st.markdown("### Scenario Comparison for Selected Flight")

    st.markdown(
        """
        <div class="section-card">
            This tab compares the selected flight across all demand scenarios.
            It helps answer whether the protection policy is still useful under high demand, low demand,
            business-heavy demand, leisure-heavy demand, and competitor price pressure.
        </div>
        """,
        unsafe_allow_html=True
    )

    flight_scenarios = filtered_policy_summary[
        filtered_policy_summary["flight_id"] == selected_flight_id
    ].copy()

    c1, c2 = st.columns(2)

    with c1:
        fig = px.bar(
            flight_scenarios,
            x="scenario_name",
            y="avg_revenue_lift",
            text="avg_revenue_lift",
            title="Revenue Lift by Scenario"
        )

        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(
            xaxis_title="Scenario",
            yaxis_title="Average Revenue Lift",
            yaxis_tickprefix="$"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        scenario_load = flight_scenarios[
            [
                "scenario_name",
                "avg_baseline_load_factor",
                "avg_protection_load_factor"
            ]
        ].melt(
            id_vars="scenario_name",
            var_name="Policy",
            value_name="Load Factor"
        )

        scenario_load["Policy"] = scenario_load["Policy"].replace({
            "avg_baseline_load_factor": "Baseline",
            "avg_protection_load_factor": "Protection"
        })

        fig = px.line(
            scenario_load,
            x="scenario_name",
            y="Load Factor",
            color="Policy",
            markers=True,
            title="Load Factor by Scenario"
        )

        fig.update_layout(
            xaxis_title="Scenario",
            yaxis_title="Load Factor",
            yaxis_tickformat=".0%",
            yaxis_range=[0, 1.05]
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### All Flight-Scenario Results")

    scenario_table = filtered_policy_summary.copy()
    scenario_table["avg_baseline_revenue"] = scenario_table["avg_baseline_revenue"].map(format_currency)
    scenario_table["avg_protection_revenue"] = scenario_table["avg_protection_revenue"].map(format_currency)
    scenario_table["avg_revenue_lift"] = scenario_table["avg_revenue_lift"].map(format_currency)
    scenario_table["avg_revenue_lift_pct"] = scenario_table["avg_revenue_lift_pct"].map(lambda x: f"{x:.1f}%")
    scenario_table["avg_baseline_load_factor"] = scenario_table["avg_baseline_load_factor"].map(format_percent)
    scenario_table["avg_protection_load_factor"] = scenario_table["avg_protection_load_factor"].map(format_percent)

    st.dataframe(scenario_table, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# Fare-Class Protection Tab
# ---------------------------------------------------------

with tab_fare:
    st.markdown("### Fare-Class Protection and Booking Limits")

    if show_interpretation:
        st.markdown(
            """
            <div class="info-box">
            <b>How to read this section:</b><br>
            A booking limit controls how many total seats may be sold before a lower fare class is restricted.
            A protected-seat value indicates how many seats are reserved for higher fare classes.
            Lower fare classes usually have tighter booking limits because they can dilute revenue if they consume capacity too early.
            </div>
            """,
            unsafe_allow_html=True
        )

    selected_protection_sorted = selected_protection.sort_values("class_rank")

    c1, c2 = st.columns(2)

    with c1:
        fig = px.bar(
            selected_protection_sorted,
            x="fare_class",
            y="booking_limit",
            text="booking_limit",
            title="Booking Limit by Fare Class"
        )

        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_title="Fare Class",
            yaxis_title="Booking Limit"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = px.bar(
            selected_protection_sorted,
            x="fare_class",
            y="protected_seats_for_higher_classes",
            text="protected_seats_for_higher_classes",
            title="Seats Protected for Higher Fare Classes"
        )

        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_title="Fare Class",
            yaxis_title="Protected Seats"
        )
        st.plotly_chart(fig, use_container_width=True)

    fare_policy_summary = (
        selected_fare_results
        .groupby(["fare_class", "policy"], as_index=False)
        .agg(
            avg_realized_demand=("realized_demand", "mean"),
            avg_accepted_bookings=("accepted_bookings", "mean"),
            avg_denied_demand=("denied_demand", "mean"),
            avg_revenue=("revenue", "mean")
        )
    )

    c3, c4 = st.columns(2)

    with c3:
        fig = px.bar(
            fare_policy_summary,
            x="fare_class",
            y="avg_revenue",
            color="policy",
            barmode="group",
            title="Average Revenue by Fare Class and Policy"
        )

        fig.update_layout(
            xaxis_title="Fare Class",
            yaxis_title="Average Revenue",
            yaxis_tickprefix="$"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        fig = px.bar(
            fare_policy_summary,
            x="fare_class",
            y="avg_denied_demand",
            color="policy",
            barmode="group",
            title="Average Denied Demand by Fare Class"
        )

        fig.update_layout(
            xaxis_title="Fare Class",
            yaxis_title="Average Denied Demand"
        )
        st.plotly_chart(fig, use_container_width=True)

    if show_tables:
        st.markdown("#### Protection-Level Table")
        st.dataframe(selected_protection_sorted, use_container_width=True, hide_index=True)

        st.markdown("#### Fare-Class Simulation Summary")
        st.dataframe(fare_policy_summary.round(2), use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# Simulation Results Tab
# ---------------------------------------------------------

with tab_sim:
    st.markdown("### Simulation Results for Selected Flight and Scenario")

    st.markdown(
        f"""
        <div class="section-card">
        These charts summarize 1,000 Monte Carlo demand simulations for the selected flight:
        <b>{selected_row['flight_number']} ({selected_row['origin']} → {selected_row['destination']})</b>
        under the selected scenario: <b>{selected_row['scenario_name']}</b>.
        <br><br>
        Each simulation creates a possible demand realization and compares revenue from the baseline policy
        against revenue from the protection policy.
        </div>
        """,
        unsafe_allow_html=True
    )

    c1, c2 = st.columns(2)

    with c1:
        fig = px.scatter(
            selected_revenue_results,
            x="baseline_revenue",
            y="protection_revenue",
            title="Simulation Outcomes: Baseline vs Protection Revenue",
            opacity=0.45
        )

        max_val = max(
            selected_revenue_results["baseline_revenue"].max(),
            selected_revenue_results["protection_revenue"].max()
        )

        fig.add_shape(
            type="line",
            x0=0,
            y0=0,
            x1=max_val,
            y1=max_val,
            line=dict(
                color="red",
                width=3,
                dash="dash"
            )
        )

        fig.add_annotation(
            x=max_val * 0.72,
            y=max_val * 0.72,
            text="Equal revenue line",
            showarrow=False,
            font=dict(color="red", size=13),
            bgcolor="rgba(255,255,255,0.80)"
        )

        fig.update_layout(
            xaxis_title="Baseline Revenue",
            yaxis_title="Protection Revenue",
            xaxis_tickprefix="$",
            yaxis_tickprefix="$"
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        selected_revenue_results["protection_wins"] = (
            selected_revenue_results["protection_revenue"]
            > selected_revenue_results["baseline_revenue"]
        )

        win_rate = selected_revenue_results["protection_wins"].mean()

        win_df = pd.DataFrame({
            "Outcome": ["Protection Higher", "Baseline Higher or Tie"],
            "Share": [win_rate, 1 - win_rate]
        })

        fig = px.pie(
            win_df,
            names="Outcome",
            values="Share",
            title="Simulation Win Rate"
        )

        st.plotly_chart(fig, use_container_width=True)

    if show_interpretation:
        st.markdown(
            """
            <div class="info-box">
            <b>Scatter plot interpretation:</b><br>
            Dots above the red dashed line mean the protection policy generated more revenue than the baseline.
            Dots below the red dashed line mean the baseline generated more revenue.
            The protection policy does not need to win every simulation; the main question is whether it wins often
            and improves expected revenue on average.
            </div>
            """,
            unsafe_allow_html=True
        )

    if show_tables:
        st.markdown("#### Simulation-Level Revenue Results")
        st.dataframe(
            selected_revenue_results.head(500),
            use_container_width=True,
            hide_index=True
        )

        st.caption("Showing first 500 simulation rows for performance.")


# ---------------------------------------------------------
# Data and Downloads Tab
# ---------------------------------------------------------

with tab_data:
    st.markdown("### Data Preview and Downloads")

    st.markdown(
        """
        <div class="section-card">
        Use this section to preview the model output files and download selected analysis results.
        </div>
        """,
        unsafe_allow_html=True
    )

    data_choice = st.selectbox(
        "Choose data table to preview",
        [
            "Simulated Policy Summary",
            "Selected Revenue Simulation Results",
            "Selected Fare-Class Simulation Results",
            "Selected Protection Levels",
            "Full Protection Levels",
        ]
    )

    if data_choice == "Simulated Policy Summary":
        preview_df = policy_summary
    elif data_choice == "Selected Revenue Simulation Results":
        preview_df = selected_revenue_results
    elif data_choice == "Selected Fare-Class Simulation Results":
        preview_df = selected_fare_results
    elif data_choice == "Selected Protection Levels":
        preview_df = selected_protection
    else:
        preview_df = protection_levels

    st.dataframe(preview_df.head(1000), use_container_width=True, hide_index=True)
    st.caption("Preview limited to first 1,000 rows when applicable.")

    st.markdown("#### Download Outputs")

    d1, d2, d3, d4 = st.columns(4)

    with d1:
        st.download_button(
            label="Download Policy Summary CSV",
            data=dataframe_to_csv_bytes(policy_summary),
            file_name="simulated_policy_summary.csv",
            mime="text/csv"
        )

    with d2:
        st.download_button(
            label="Download Selected Flight CSV",
            data=dataframe_to_csv_bytes(selected_revenue_results),
            file_name=f"{selected_flight_id}_{selected_scenario_id}_simulation_results.csv",
            mime="text/csv"
        )

    with d3:
        st.download_button(
            label="Download Protection Levels CSV",
            data=dataframe_to_csv_bytes(selected_protection),
            file_name=f"{selected_flight_id}_{selected_scenario_id}_protection_levels.csv",
            mime="text/csv"
        )

    with d4:
        st.download_button(
            label="Download Excel Summary",
            data=dataframe_to_excel_bytes(preview_df),
            file_name="airline_revenue_management_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

st.markdown("---")
st.markdown(
    """
    <div class="small-caption">
    <b>Model note:</b> This portfolio project uses synthetic data and a simulation-based revenue management framework.
    The protection policy is designed for decision-support demonstration and is not a production airline revenue management system.
    </div>
    """,
    unsafe_allow_html=True
)