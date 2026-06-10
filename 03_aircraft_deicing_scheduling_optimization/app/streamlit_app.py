import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st


# --------------------------------------------------
# Project paths
# --------------------------------------------------

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from generate_data import (
    generate_aircraft_schedule,
    generate_crews,
    generate_travel_times,
    save_datasets
)

from solve_model import solve_deicing_schedule

from visualize_results import (
    create_gantt_chart,
    create_flight_risk_ranking_chart,
    create_crew_utilization_chart
)


# --------------------------------------------------
# Streamlit page setup
# --------------------------------------------------

st.set_page_config(
    page_title="Aircraft De-Icing Scheduling Optimization",
    page_icon="✈️",
    layout="wide"
)

st.title("Aircraft Snow Removal and De-Icing Scheduling Optimization")

st.caption(
    "Interactive decision-support app for assigning aircraft to de-icing crews "
    "under winter-weather operating conditions."
)


# --------------------------------------------------
# Fixed internal app settings
# --------------------------------------------------

INTERNAL_RANDOM_SEED = 42
INTERNAL_SOLVER_TIME_LIMIT = 60
INTERNAL_SOLVER_GAP = 0.01


# --------------------------------------------------
# Required schemas for upload validation
# --------------------------------------------------

REQUIRED_COLUMNS = {
    "aircraft_schedule": [
        "aircraft_id",
        "flight_number",
        "scheduled_departure_min",
        "ready_time_min",
        "aircraft_type",
        "service_time_min",
        "gate",
        "passenger_load",
        "priority_score",
        "delay_penalty_per_min"
    ],
    "crews": [
        "crew_id",
        "shift_start_min",
        "shift_end_min",
        "overtime_cost_per_min",
        "home_pad"
    ],
    "travel_times": [
        "from_location",
        "to_location",
        "travel_time_min"
    ]
}


# --------------------------------------------------
# Business overview and assumptions
# --------------------------------------------------

with st.expander("Project Overview and Model Assumptions", expanded=True):
    st.markdown(
        """
        This dashboard supports **aircraft snow-removal and de-icing scheduling** during winter operations.

        The goal is to assign aircraft to available de-icing crews and determine the service sequence for each crew,
        while reducing departure delays, missed departure-buffer targets, and crew overtime.

        **How to use this dashboard:**

        1. Use the built-in sample dataset or upload your own compatible CSV files.
        2. Adjust the current operating scenario using the sidebar controls.
        3. Click **Run Optimization** when you are ready to solve.
        4. Review how the **Current Scenario** differs from the **Base Optimization**.
        5. Review the optimized crew schedule, flight risk ranking, crew utilization, and downloadable output tables.

        **Model assumptions included:**

        - Each aircraft must be assigned to exactly one crew.
        - Aircraft service cannot start before the aircraft is ready.
        - Each crew can serve only one aircraft at a time.
        - Gate-to-gate travel/setup time is included between jobs assigned to the same crew.
        - Departure delay is penalized when service completes after scheduled departure.
        - A preferred departure buffer is included, so flights can be flagged as **On Time**, **At Risk**, or **Delayed**.
        - Crew overtime is allowed but penalized.

        **Current model extensions not included yet:**

        - De-icing truck/equipment limits
        - Crew/equipment compatibility by aircraft type
        - De-icing pad capacity
        - Fluid holdover-time expiration
        - Crew break rules
        - Weather severity changing over time
        - Flight cancellation or deferral decisions
        """
    )


# --------------------------------------------------
# Helper functions
# --------------------------------------------------

def read_uploaded_csv(uploaded_file):
    if uploaded_file is None:
        return None

    try:
        return pd.read_csv(uploaded_file)
    except Exception as error:
        st.error(f"Could not read uploaded file: {error}")
        return None


def validate_required_columns(df, dataset_name):
    required = REQUIRED_COLUMNS[dataset_name]

    if df is None:
        return False, [f"{dataset_name}.csv was not uploaded."]

    missing_columns = [
        column for column in required
        if column not in df.columns
    ]

    if missing_columns:
        return False, missing_columns

    return True, []


def validate_numeric_columns(aircraft_df, crews_df, travel_df):
    issues = []

    numeric_requirements = {
        "aircraft_schedule.csv": {
            "data": aircraft_df,
            "columns": [
                "scheduled_departure_min",
                "ready_time_min",
                "service_time_min",
                "passenger_load",
                "priority_score",
                "delay_penalty_per_min"
            ]
        },
        "crews.csv": {
            "data": crews_df,
            "columns": [
                "shift_start_min",
                "shift_end_min",
                "overtime_cost_per_min"
            ]
        },
        "travel_times.csv": {
            "data": travel_df,
            "columns": ["travel_time_min"]
        }
    }

    for file_name, requirement in numeric_requirements.items():
        df = requirement["data"]

        for column in requirement["columns"]:
            if column in df.columns:
                converted = pd.to_numeric(df[column], errors="coerce")

                if converted.isna().any():
                    issues.append(
                        f"{file_name}: column '{column}' contains non-numeric or missing values."
                    )

    return issues


def validate_uploaded_data(aircraft_df, crews_df, travel_df):
    validation_messages = []
    is_valid = True

    datasets = {
        "aircraft_schedule": aircraft_df,
        "crews": crews_df,
        "travel_times": travel_df
    }

    for dataset_name, df in datasets.items():
        valid_columns, missing_columns = validate_required_columns(
            df,
            dataset_name
        )

        if not valid_columns:
            is_valid = False

            if df is None:
                validation_messages.extend(missing_columns)
            else:
                validation_messages.append(
                    f"{dataset_name}.csv is missing required columns: {missing_columns}"
                )

    if not is_valid:
        return False, validation_messages

    numeric_issues = validate_numeric_columns(
        aircraft_df,
        crews_df,
        travel_df
    )

    if numeric_issues:
        is_valid = False
        validation_messages.extend(numeric_issues)

    return is_valid, validation_messages


def convert_numeric_columns(aircraft_df, crews_df, travel_df):
    aircraft_df = aircraft_df.copy()
    crews_df = crews_df.copy()
    travel_df = travel_df.copy()

    aircraft_numeric_columns = [
        "scheduled_departure_min",
        "ready_time_min",
        "service_time_min",
        "passenger_load",
        "priority_score",
        "delay_penalty_per_min"
    ]

    for column in aircraft_numeric_columns:
        aircraft_df[column] = pd.to_numeric(aircraft_df[column])

    crew_numeric_columns = [
        "shift_start_min",
        "shift_end_min",
        "overtime_cost_per_min"
    ]

    for column in crew_numeric_columns:
        crews_df[column] = pd.to_numeric(crews_df[column])

    travel_df["travel_time_min"] = pd.to_numeric(
        travel_df["travel_time_min"]
    )

    return aircraft_df, crews_df, travel_df


def apply_weather_adjustment(base_aircraft_df, base_weather, scenario_weather):
    """
    Adjust service times for the current scenario.
    """

    weather_multiplier = {
        "light": 1.0,
        "moderate": 1.3,
        "heavy": 1.7
    }

    scenario_aircraft_df = base_aircraft_df.copy()

    base_factor = weather_multiplier[base_weather]
    scenario_factor = weather_multiplier[scenario_weather]

    adjustment_ratio = scenario_factor / base_factor

    scenario_aircraft_df["service_time_min"] = (
        scenario_aircraft_df["service_time_min"] * adjustment_ratio
    ).round().astype(int)

    scenario_aircraft_df["weather_severity"] = scenario_weather

    return scenario_aircraft_df


def apply_current_scenario_inputs(
    base_aircraft_df,
    base_crews_df,
    scenario_weather,
    departure_volume,
    available_crews,
    base_weather
):
    """
    Create current-scenario aircraft and crew data from the base data.
    """

    scenario_aircraft_df = base_aircraft_df.copy()

    scenario_aircraft_df = scenario_aircraft_df.sort_values(
        by="scheduled_departure_min"
    ).reset_index(drop=True)

    scenario_aircraft_df = scenario_aircraft_df.head(departure_volume).copy()

    scenario_aircraft_df = apply_weather_adjustment(
        base_aircraft_df=scenario_aircraft_df,
        base_weather=base_weather,
        scenario_weather=scenario_weather
    )

    scenario_crews_df = base_crews_df.head(available_crews).copy()

    return scenario_aircraft_df, scenario_crews_df


def solve_case(
    aircraft_df,
    crews_df,
    travel_df,
    departure_buffer_min,
    buffer_violation_cost_factor,
    output_folder
):
    """
    Save dataframes to temporary CSVs and solve the de-icing model.
    """

    data_folder = os.path.join(output_folder, "data")
    result_folder = os.path.join(output_folder, "outputs")

    aircraft_path, crews_path, travel_path = save_datasets(
        aircraft_df=aircraft_df,
        crews_df=crews_df,
        travel_df=travel_df,
        output_folder=data_folder
    )

    schedule_df, crew_summary_df, flight_risk_summary_df, status, objective_value = solve_deicing_schedule(
        aircraft_path=aircraft_path,
        crews_path=crews_path,
        travel_path=travel_path,
        output_folder=result_folder,
        departure_buffer_min=departure_buffer_min,
        buffer_violation_cost_factor=buffer_violation_cost_factor,
        solver_time_limit=INTERNAL_SOLVER_TIME_LIMIT,
        solver_gap=INTERNAL_SOLVER_GAP
    )

    return {
        "schedule_df": schedule_df,
        "crew_summary_df": crew_summary_df,
        "flight_risk_summary_df": flight_risk_summary_df,
        "status": status,
        "objective_value": objective_value,
        "result_folder": result_folder
    }


def create_case_figures(case_result):
    """
    Create Plotly figures from a solved case.
    """

    result_folder = case_result["result_folder"]

    schedule_path = os.path.join(result_folder, "optimized_schedule.csv")
    crew_path = os.path.join(result_folder, "crew_summary.csv")
    risk_path = os.path.join(result_folder, "flight_delay_summary.csv")

    gantt_fig = create_gantt_chart(
        schedule_path=schedule_path,
        output_path=os.path.join(result_folder, "crew_gantt_chart.html")
    )

    risk_fig = create_flight_risk_ranking_chart(
        delay_path=risk_path,
        output_path=os.path.join(result_folder, "flight_risk_ranking_chart.html")
    )

    utilization_fig = create_crew_utilization_chart(
        crew_path=crew_path,
        output_path=os.path.join(result_folder, "crew_utilization_chart.html")
    )

    return gantt_fig, risk_fig, utilization_fig


def summarize_case(schedule_df, crew_summary_df):
    total_aircraft = len(schedule_df)
    on_time_flights = int((schedule_df["service_status"] == "On Time").sum())
    at_risk_flights = int((schedule_df["service_status"] == "At Risk").sum())
    delayed_flights = int((schedule_df["service_status"] == "Delayed").sum())

    total_delay = float(schedule_df["delay_min"].sum())
    total_buffer_violation = float(schedule_df["buffer_violation_min"].sum())
    total_overtime = float(crew_summary_df["overtime_min"].sum())

    average_utilization = float(crew_summary_df["utilization_percent"].mean())
    max_utilization = float(crew_summary_df["utilization_percent"].max())

    return {
        "total_aircraft": total_aircraft,
        "on_time_flights": on_time_flights,
        "at_risk_flights": at_risk_flights,
        "delayed_flights": delayed_flights,
        "total_delay": total_delay,
        "total_buffer_violation": total_buffer_violation,
        "total_overtime": total_overtime,
        "average_utilization": average_utilization,
        "max_utilization": max_utilization
    }


def build_comparison_table(base_result, scenario_result):
    base_summary = summarize_case(
        base_result["schedule_df"],
        base_result["crew_summary_df"]
    )

    scenario_summary = summarize_case(
        scenario_result["schedule_df"],
        scenario_result["crew_summary_df"]
    )

    rows = [
        {
            "Metric": "Aircraft scheduled",
            "Base Optimization": base_summary["total_aircraft"],
            "Current Scenario": scenario_summary["total_aircraft"],
            "Change": scenario_summary["total_aircraft"] - base_summary["total_aircraft"]
        },
        {
            "Metric": "On-time flights",
            "Base Optimization": base_summary["on_time_flights"],
            "Current Scenario": scenario_summary["on_time_flights"],
            "Change": scenario_summary["on_time_flights"] - base_summary["on_time_flights"]
        },
        {
            "Metric": "At-risk flights",
            "Base Optimization": base_summary["at_risk_flights"],
            "Current Scenario": scenario_summary["at_risk_flights"],
            "Change": scenario_summary["at_risk_flights"] - base_summary["at_risk_flights"]
        },
        {
            "Metric": "Delayed flights",
            "Base Optimization": base_summary["delayed_flights"],
            "Current Scenario": scenario_summary["delayed_flights"],
            "Change": scenario_summary["delayed_flights"] - base_summary["delayed_flights"]
        },
        {
            "Metric": "Total delay minutes",
            "Base Optimization": round(base_summary["total_delay"], 1),
            "Current Scenario": round(scenario_summary["total_delay"], 1),
            "Change": round(scenario_summary["total_delay"] - base_summary["total_delay"], 1)
        },
        {
            "Metric": "Total buffer violation minutes",
            "Base Optimization": round(base_summary["total_buffer_violation"], 1),
            "Current Scenario": round(scenario_summary["total_buffer_violation"], 1),
            "Change": round(
                scenario_summary["total_buffer_violation"]
                - base_summary["total_buffer_violation"],
                1
            )
        },
        {
            "Metric": "Total overtime minutes",
            "Base Optimization": round(base_summary["total_overtime"], 1),
            "Current Scenario": round(scenario_summary["total_overtime"], 1),
            "Change": round(scenario_summary["total_overtime"] - base_summary["total_overtime"], 1)
        },
        {
            "Metric": "Maximum crew utilization (%)",
            "Base Optimization": round(base_summary["max_utilization"], 1),
            "Current Scenario": round(scenario_summary["max_utilization"], 1),
            "Change": round(
                scenario_summary["max_utilization"]
                - base_summary["max_utilization"],
                1
            )
        }
    ]

    return pd.DataFrame(rows)


def show_kpis(summary):
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    with kpi1:
        st.metric("Aircraft Scheduled", summary["total_aircraft"])

    with kpi2:
        st.metric("Delayed Flights", summary["delayed_flights"])

    with kpi3:
        st.metric("At-Risk Flights", summary["at_risk_flights"])

    with kpi4:
        st.metric("Total Delay", f"{summary['total_delay']:.0f} min")

    with kpi5:
        st.metric("Crew Overtime", f"{summary['total_overtime']:.0f} min")


def interpret_solution(schedule_df, crew_summary_df):
    summary = summarize_case(schedule_df, crew_summary_df)

    st.markdown("### Current Scenario Interpretation")

    if summary["delayed_flights"] == 0 and summary["at_risk_flights"] == 0:
        st.success(
            "The schedule is healthy. All flights complete service before the departure-buffer target."
        )
    elif summary["delayed_flights"] == 0:
        st.warning(
            f"No flights are delayed, but {summary['at_risk_flights']} flight(s) miss the preferred buffer target."
        )
    elif summary["delayed_flights"] <= summary["total_aircraft"] * 0.35:
        st.warning(
            f"The schedule is feasible but tight. {summary['delayed_flights']} flight(s) are delayed "
            f"and {summary['at_risk_flights']} flight(s) are at risk."
        )
    else:
        st.error(
            f"The operation is disrupted. {summary['delayed_flights']} out of "
            f"{summary['total_aircraft']} flights are delayed."
        )

    busiest_crew_row = crew_summary_df.sort_values(
        by="utilization_percent",
        ascending=False
    ).iloc[0]

    st.write(
        f"The current optimized schedule creates **{summary['total_delay']:.0f} total delay minutes**, "
        f"**{summary['total_buffer_violation']:.0f} buffer violation minutes**, and "
        f"**{summary['total_overtime']:.0f} overtime minutes**."
    )

    st.write(
        f"The busiest crew is **{busiest_crew_row['crew_id']}** with "
        f"**{busiest_crew_row['utilization_percent']:.1f}% utilization**."
    )


def diagnose_model_issue(
    solver_status,
    aircraft_df,
    crews_df,
    departure_buffer_min,
    scenario_weather
):
    st.error(f"The optimization did not return a usable solution. Solver status: {solver_status}")

    total_service_time = aircraft_df["service_time_min"].sum()
    total_regular_crew_time = (
        crews_df["shift_end_min"] - crews_df["shift_start_min"]
    ).sum()

    diagnostic_df = pd.DataFrame({
        "Check": [
            "Number of aircraft",
            "Number of crews",
            "Total aircraft service time",
            "Total regular crew time",
            "Departure buffer target",
            "Weather condition"
        ],
        "Value": [
            len(aircraft_df),
            len(crews_df),
            f"{total_service_time:.0f} min",
            f"{total_regular_crew_time:.0f} min",
            f"{departure_buffer_min} min",
            str(scenario_weather).title()
        ]
    })

    st.subheader("Diagnostic Check")
    st.dataframe(diagnostic_df, use_container_width=True, hide_index=True)

    st.markdown("### Possible causes")

    st.write("- Too many aircraft are scheduled for the available crews.")
    st.write("- Heavy weather is increasing service times.")
    st.write("- The departure buffer target may be too strict.")
    st.write("- Aircraft ready times may be too close to scheduled departure times.")
    st.write("- Crew shifts may be too short for the selected schedule.")

    st.markdown("### Recommended adjustments")

    st.write("- Increase the number of available crews.")
    st.write("- Reduce the number of aircraft in the current scenario.")
    st.write("- Use a smaller departure buffer target.")
    st.write("- Test lighter weather assumptions.")
    st.write("- Review service-time assumptions in the input data.")


def make_download_button(df, label, file_name):
    csv_data = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=label,
        data=csv_data,
        file_name=file_name,
        mime="text/csv",
        use_container_width=True
    )


def show_current_scenario_results(case_result):
    schedule_df = case_result["schedule_df"]
    crew_summary_df = case_result["crew_summary_df"]
    flight_risk_summary_df = case_result["flight_risk_summary_df"]

    summary = summarize_case(schedule_df, crew_summary_df)

    show_kpis(summary)

    st.caption(
        f"Solver status: {case_result['status']} | "
        f"Objective value: {case_result['objective_value']:,.2f}"
    )

    interpret_solution(schedule_df, crew_summary_df)

    gantt_fig, risk_fig, utilization_fig = create_case_figures(case_result)

    st.markdown("### Optimized Crew Schedule")
    st.plotly_chart(
        gantt_fig,
        use_container_width=True,
        key="current_scenario_gantt_chart"
    )

    st.markdown("### Flight Risk Ranking")
    st.plotly_chart(
        risk_fig,
        use_container_width=True,
        key="current_scenario_risk_chart"
    )

    st.markdown("### Crew Utilization")
    st.plotly_chart(
        utilization_fig,
        use_container_width=True,
        key="current_scenario_utilization_chart"
    )

    table_tab1, table_tab2, table_tab3 = st.tabs([
        "Optimized Schedule",
        "Crew Summary",
        "Flight Risk Summary"
    ])

    with table_tab1:
        st.dataframe(schedule_df, use_container_width=True, hide_index=True)

    with table_tab2:
        st.dataframe(crew_summary_df, use_container_width=True, hide_index=True)

    with table_tab3:
        st.dataframe(flight_risk_summary_df, use_container_width=True, hide_index=True)

    st.markdown("### Download Results")

    d1, d2, d3 = st.columns(3)

    with d1:
        make_download_button(
            schedule_df,
            "Download Current Scenario Schedule",
            "current_scenario_optimized_schedule.csv"
        )

    with d2:
        make_download_button(
            crew_summary_df,
            "Download Current Scenario Crew Summary",
            "current_scenario_crew_summary.csv"
        )

    with d3:
        make_download_button(
            flight_risk_summary_df,
            "Download Current Scenario Flight Risk Summary",
            "current_scenario_flight_risk_summary.csv"
        )


# --------------------------------------------------
# Create sample base data
# --------------------------------------------------

sample_aircraft_df = generate_aircraft_schedule(
    num_aircraft=20,
    weather_severity="moderate",
    seed=INTERNAL_RANDOM_SEED
)

sample_crews_df = generate_crews(
    num_crews=6
)

sample_travel_df = generate_travel_times(
    seed=INTERNAL_RANDOM_SEED
)


# --------------------------------------------------
# Data source section
# --------------------------------------------------

st.subheader("Data Source")

data_source_tab1, data_source_tab2 = st.tabs([
    "Use Sample Data",
    "Upload Custom Data"
])

with data_source_tab1:
    st.markdown(
        """
        The sample dataset represents a synthetic winter airport operation with aircraft, crews,
        and gate-to-gate travel/setup times.
        """
    )

    st.info(
        "Using sample data by default. To use your own files, upload all three required CSVs in the next tab."
    )

    template_col1, template_col2, template_col3 = st.columns(3)

    with template_col1:
        st.download_button(
            "Download aircraft_schedule.csv template",
            data=sample_aircraft_df.to_csv(index=False).encode("utf-8"),
            file_name="aircraft_schedule.csv",
            mime="text/csv",
            use_container_width=True
        )

    with template_col2:
        st.download_button(
            "Download crews.csv template",
            data=sample_crews_df.to_csv(index=False).encode("utf-8"),
            file_name="crews.csv",
            mime="text/csv",
            use_container_width=True
        )

    with template_col3:
        st.download_button(
            "Download travel_times.csv template",
            data=sample_travel_df.to_csv(index=False).encode("utf-8"),
            file_name="travel_times.csv",
            mime="text/csv",
            use_container_width=True
        )

with data_source_tab2:
    st.markdown(
        """
        Upload your own compatible CSV files. The app will use these files as the base dataset.
        The sidebar controls will then create the current scenario from your uploaded base data.
        """
    )

    uploaded_aircraft = st.file_uploader(
        "Upload aircraft_schedule.csv",
        type=["csv"]
    )

    uploaded_crews = st.file_uploader(
        "Upload crews.csv",
        type=["csv"]
    )

    uploaded_travel = st.file_uploader(
        "Upload travel_times.csv",
        type=["csv"]
    )


# --------------------------------------------------
# Select base data
# --------------------------------------------------

uploaded_aircraft_df = read_uploaded_csv(uploaded_aircraft)
uploaded_crews_df = read_uploaded_csv(uploaded_crews)
uploaded_travel_df = read_uploaded_csv(uploaded_travel)

using_uploaded_data = (
    uploaded_aircraft_df is not None
    and uploaded_crews_df is not None
    and uploaded_travel_df is not None
)

if using_uploaded_data:
    data_valid, validation_messages = validate_uploaded_data(
        uploaded_aircraft_df,
        uploaded_crews_df,
        uploaded_travel_df
    )

    if not data_valid:
        st.error("Uploaded files are not compatible with the required format.")

        for message in validation_messages:
            st.write(f"- {message}")

        st.markdown("### Required File Schemas")

        schema_rows = []

        for dataset_name, columns in REQUIRED_COLUMNS.items():
            for column in columns:
                schema_rows.append({
                    "File": f"{dataset_name}.csv",
                    "Required Column": column
                })

        st.dataframe(
            pd.DataFrame(schema_rows),
            use_container_width=True,
            hide_index=True
        )

        st.stop()

    base_aircraft_df, base_crews_df, base_travel_df = convert_numeric_columns(
        uploaded_aircraft_df,
        uploaded_crews_df,
        uploaded_travel_df
    )

    base_weather = "moderate"

    st.success("Uploaded files passed the format check and will be used as the base dataset.")

else:
    base_aircraft_df = sample_aircraft_df.copy()
    base_crews_df = sample_crews_df.copy()
    base_travel_df = sample_travel_df.copy()
    base_weather = "moderate"


# --------------------------------------------------
# Sidebar scenario controls
# --------------------------------------------------

st.sidebar.header("Current Scenario Controls")

st.sidebar.caption(
    "The base optimization uses default operating assumptions. "
    "The controls below modify only the current scenario."
)

max_aircraft = len(base_aircraft_df)
max_crews = len(base_crews_df)

default_aircraft = min(12, max_aircraft)
default_crews = min(3, max_crews)
default_weather = "moderate"
default_departure_buffer = 10
default_buffer_priority = 0.25


def reset_to_base_scenario():
    st.session_state.departure_volume = default_aircraft
    st.session_state.available_crews = default_crews
    st.session_state.scenario_weather = default_weather
    st.session_state.departure_buffer_min = default_departure_buffer
    st.session_state.buffer_violation_cost_factor = default_buffer_priority


if "departure_volume" not in st.session_state:
    st.session_state.departure_volume = default_aircraft

if "available_crews" not in st.session_state:
    st.session_state.available_crews = default_crews

if "scenario_weather" not in st.session_state:
    st.session_state.scenario_weather = default_weather

if "departure_buffer_min" not in st.session_state:
    st.session_state.departure_buffer_min = default_departure_buffer

if "buffer_violation_cost_factor" not in st.session_state:
    st.session_state.buffer_violation_cost_factor = default_buffer_priority

# Keep session state valid if uploaded data has fewer rows/crews
if st.session_state.departure_volume > max_aircraft:
    st.session_state.departure_volume = max_aircraft

if st.session_state.available_crews > max_crews:
    st.session_state.available_crews = max_crews

departure_volume = st.sidebar.slider(
    "Aircraft included in current scenario",
    min_value=1,
    max_value=max_aircraft,
    step=1,
    key="departure_volume"
)

available_crews = st.sidebar.slider(
    "Available crews in current scenario",
    min_value=1,
    max_value=max_crews,
    step=1,
    key="available_crews"
)

scenario_weather = st.sidebar.selectbox(
    "Current scenario weather",
    options=["light", "moderate", "heavy"],
    key="scenario_weather"
)

departure_buffer_min = st.sidebar.slider(
    "Departure buffer target",
    min_value=0,
    max_value=30,
    step=5,
    help="Preferred number of minutes between service completion and scheduled departure.",
    key="departure_buffer_min"
)

buffer_violation_cost_factor = st.sidebar.slider(
    "Buffer priority",
    min_value=0.0,
    max_value=1.0,
    step=0.05,
    help="Higher values make the optimizer care more about protecting the departure buffer.",
    key="buffer_violation_cost_factor"
)

st.sidebar.button(
    "Reset to Base Scenario",
    on_click=reset_to_base_scenario,
    use_container_width=True
)

run_optimization = st.sidebar.button(
    "Run Optimization",
    type="primary",
    use_container_width=True
)


# --------------------------------------------------
# Build current scenario data preview
# --------------------------------------------------

scenario_aircraft_df, scenario_crews_df = apply_current_scenario_inputs(
    base_aircraft_df=base_aircraft_df,
    base_crews_df=base_crews_df,
    scenario_weather=scenario_weather,
    departure_volume=departure_volume,
    available_crews=available_crews,
    base_weather=base_weather
)


# --------------------------------------------------
# Input data preview under tabs
# --------------------------------------------------

st.subheader("Input Data Preview")

input_tab1, input_tab2, input_tab3, input_tab4 = st.tabs([
    "Base Aircraft Dataset",
    "Current Scenario Aircraft",
    "Crews",
    "Travel / Setup Times"
])

with input_tab1:
    st.caption("Full base aircraft dataset available to the app.")
    st.dataframe(
        base_aircraft_df.head(20),
        use_container_width=True,
        hide_index=True
    )

with input_tab2:
    st.caption("Current scenario aircraft after applying sidebar controls.")
    st.dataframe(
        scenario_aircraft_df.head(20),
        use_container_width=True,
        hide_index=True
    )

with input_tab3:
    crew_view_tab1, crew_view_tab2 = st.tabs([
        "Base Crew Dataset",
        "Current Scenario Crews"
    ])

    with crew_view_tab1:
        st.dataframe(
            base_crews_df,
            use_container_width=True,
            hide_index=True
        )

    with crew_view_tab2:
        st.dataframe(
            scenario_crews_df,
            use_container_width=True,
            hide_index=True
        )

with input_tab4:
    st.dataframe(
        base_travel_df.head(50),
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# Status before optimization
# --------------------------------------------------

st.markdown("---")

status_col1, status_col2, status_col3, status_col4 = st.columns(4)

with status_col1:
    st.metric("Aircraft in Dataset", len(base_aircraft_df))

with status_col2:
    st.metric("Aircraft Scheduled", len(scenario_aircraft_df))

with status_col3:
    st.metric("Crews Available", len(scenario_crews_df))

with status_col4:
    st.metric("Weather Scenario", scenario_weather.title())

st.info(
    "Adjust the sidebar controls, then click **Run Optimization**. "
    "The model will not solve automatically when a control is changed."
)


# --------------------------------------------------
# Run optimization
# --------------------------------------------------

if run_optimization:
    st.markdown("---")
    st.subheader("Optimization Results")

    with st.spinner("Solving base optimization and current scenario..."):

        temp_dir = tempfile.mkdtemp()

        base_output_folder = os.path.join(temp_dir, "base_optimization")
        scenario_output_folder = os.path.join(temp_dir, "current_scenario")

        # Base optimization always uses default operating assumptions
        base_case_aircraft_df = base_aircraft_df.sort_values(
            by="scheduled_departure_min"
        ).head(default_aircraft).copy()

        base_case_crews_df = base_crews_df.head(default_crews).copy()

        base_case_aircraft_df = apply_weather_adjustment(
            base_aircraft_df=base_case_aircraft_df,
            base_weather=base_weather,
            scenario_weather=default_weather
        )

        base_result = solve_case(
            aircraft_df=base_case_aircraft_df,
            crews_df=base_case_crews_df,
            travel_df=base_travel_df,
            departure_buffer_min=default_departure_buffer,
            buffer_violation_cost_factor=default_buffer_priority,
            output_folder=base_output_folder
        )

        scenario_result = solve_case(
            aircraft_df=scenario_aircraft_df,
            crews_df=scenario_crews_df,
            travel_df=base_travel_df,
            departure_buffer_min=departure_buffer_min,
            buffer_violation_cost_factor=buffer_violation_cost_factor,
            output_folder=scenario_output_folder
        )

    if base_result["schedule_df"] is None:
        diagnose_model_issue(
            solver_status=base_result["status"],
            aircraft_df=base_case_aircraft_df,
            crews_df=base_case_crews_df,
            departure_buffer_min=default_departure_buffer,
            scenario_weather="base optimization"
        )
        st.stop()

    if scenario_result["schedule_df"] is None:
        diagnose_model_issue(
            solver_status=scenario_result["status"],
            aircraft_df=scenario_aircraft_df,
            crews_df=scenario_crews_df,
            departure_buffer_min=departure_buffer_min,
            scenario_weather=scenario_weather
        )
        st.stop()

    st.success("Optimization completed successfully.")

    # --------------------------------------------------
    # Base vs Current Scenario Comparison
    # --------------------------------------------------

    st.markdown("### Base Optimization vs Current Scenario")

    comparison_df = build_comparison_table(
        base_result=base_result,
        scenario_result=scenario_result
    )

    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True
    )

    base_summary = summarize_case(
        base_result["schedule_df"],
        base_result["crew_summary_df"]
    )

    scenario_summary = summarize_case(
        scenario_result["schedule_df"],
        scenario_result["crew_summary_df"]
    )

    delay_change = (
        scenario_summary["total_delay"]
        - base_summary["total_delay"]
    )

    delayed_flight_change = (
        scenario_summary["delayed_flights"]
        - base_summary["delayed_flights"]
    )

    overtime_change = (
        scenario_summary["total_overtime"]
        - base_summary["total_overtime"]
    )

    st.markdown("### Comparison Interpretation")

    if delay_change > 0:
        st.warning(
            f"Compared with the base optimization, the current scenario increases total delay by "
            f"**{delay_change:.0f} minutes** and changes delayed flights by "
            f"**{delayed_flight_change:+d}**."
        )
    elif delay_change < 0:
        st.success(
            f"Compared with the base optimization, the current scenario reduces total delay by "
            f"**{abs(delay_change):.0f} minutes** and changes delayed flights by "
            f"**{delayed_flight_change:+d}**."
        )
    else:
        st.info(
            "The current scenario has the same total delay as the base optimization."
        )

    if overtime_change > 0:
        st.warning(
            f"Crew overtime increases by **{overtime_change:.0f} minutes** compared with the base optimization."
        )
    elif overtime_change < 0:
        st.success(
            f"Crew overtime decreases by **{abs(overtime_change):.0f} minutes** compared with the base optimization."
        )
    else:
        st.info("Crew overtime is unchanged compared with the base optimization.")

    st.markdown("---")

    # --------------------------------------------------
    # Current Scenario Detailed Results
    # --------------------------------------------------

    st.markdown("## Current Optimized Schedule")

    show_current_scenario_results(
        case_result=scenario_result
    )

else:
    st.stop()