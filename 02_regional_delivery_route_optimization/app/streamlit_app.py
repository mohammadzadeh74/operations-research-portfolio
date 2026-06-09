import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# --------------------------------------------------
# Project paths
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data"
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from solve_vrp import build_data_model, solve_cvrp
from plot_routes import (
    prepare_location_data,
    build_route_plot_dataframe,
    create_route_map
)

# --------------------------------------------------
# Streamlit page setup
# --------------------------------------------------

st.set_page_config(
    page_title="Regional Delivery Route Optimization",
    layout="wide"
)

st.title("Regional Delivery Route Optimization")
st.caption(
    "Interactive decision-support app for evaluating delivery routing scenarios "
    "under fleet, capacity, demand, and route-distance changes."
)

with st.expander("Project Overview and Model Assumptions", expanded=False):
    st.markdown(
        """
        This dashboard solves a **capacitated vehicle routing problem (CVRP)** for a regional delivery operation.

        The goal is to assign customer deliveries to available vehicles while minimizing total operating cost,
        subject to vehicle capacity and maximum route-distance limits.

        **How to use this dashboard:**

        1. Use the sample dataset or upload your own compatible CSV files.
        2. Adjust demand growth, fleet availability, vehicle capacity, or route-distance limits.
        3. Compare the current scenario against the base case.
        4. Review the optimized route map, vehicle-level summary, and stop-level route plan.
        5. Download the route outputs for reporting or operational use.

        **Model assumptions:**

        - Each customer is served exactly once.
        - Each route starts and ends at the depot.
        - Vehicle capacities cannot be exceeded.
        - Maximum route-distance limits must be respected.
        - Distances are based on the provided distance matrix.
        """
    )

# --------------------------------------------------
# Required schemas
# --------------------------------------------------

REQUIRED_COLUMNS = {
    "depot": ["depot_id", "depot_name", "x_coord", "y_coord"],
    "customers": [
        "customer_id",
        "customer_name",
        "zone",
        "x_coord",
        "y_coord",
        "demand_units",
        "priority_level",
        "service_time_min"
    ],
    "vehicles": [
        "vehicle_id",
        "vehicle_type",
        "capacity_units",
        "fixed_cost",
        "cost_per_mile",
        "max_route_distance"
    ],
    "distance_matrix": [
        "from_id",
        "to_id",
        "distance_miles"
    ]
}

# --------------------------------------------------
# Data loading
# --------------------------------------------------

@st.cache_data
def load_sample_data():
    depot = pd.read_csv(DATA_PATH / "depot.csv")
    customers = pd.read_csv(DATA_PATH / "customers.csv")
    vehicles = pd.read_csv(DATA_PATH / "vehicles.csv")
    distance_matrix_df = pd.read_csv(DATA_PATH / "distance_matrix.csv")

    return depot, customers, vehicles, distance_matrix_df


def read_uploaded_csv(uploaded_file):
    if uploaded_file is None:
        return None

    try:
        return pd.read_csv(uploaded_file)
    except Exception as error:
        st.error(f"Could not read uploaded file: {error}")
        return None


def validate_required_columns(df, dataset_name):
    """
    Check whether a dataframe has all required columns.
    """

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


def validate_numeric_columns(depot, customers, vehicles, distance_matrix_df):
    """
    Check whether important numeric fields can be used by the model.
    """

    issues = []

    numeric_requirements = {
        "depot.csv": {
            "data": depot,
            "columns": ["x_coord", "y_coord"]
        },
        "customers.csv": {
            "data": customers,
            "columns": [
                "x_coord",
                "y_coord",
                "demand_units",
                "service_time_min"
            ]
        },
        "vehicles.csv": {
            "data": vehicles,
            "columns": [
                "capacity_units",
                "fixed_cost",
                "cost_per_mile",
                "max_route_distance"
            ]
        },
        "distance_matrix.csv": {
            "data": distance_matrix_df,
            "columns": ["distance_miles"]
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


def validate_distance_matrix_coverage(depot, customers, distance_matrix_df):
    """
    Check whether distance matrix includes every depot/customer pair.
    """

    issues = []

    location_ids = (
        depot["depot_id"].tolist()
        + customers["customer_id"].tolist()
    )

    required_pairs = set()

    for from_id in location_ids:
        for to_id in location_ids:
            required_pairs.add((from_id, to_id))

    uploaded_pairs = set(
        zip(
            distance_matrix_df["from_id"],
            distance_matrix_df["to_id"]
        )
    )

    missing_pairs = required_pairs - uploaded_pairs

    if missing_pairs:
        sample_missing_pairs = list(missing_pairs)[:10]

        issues.append(
            f"distance_matrix.csv is missing {len(missing_pairs)} required origin-destination pairs. "
            f"Examples: {sample_missing_pairs}"
        )

    return issues


def validate_uploaded_data(depot, customers, vehicles, distance_matrix_df):
    """
    Run all format checks for uploaded files.
    """

    validation_messages = []
    is_valid = True

    datasets = {
        "depot": depot,
        "customers": customers,
        "vehicles": vehicles,
        "distance_matrix": distance_matrix_df
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
        depot,
        customers,
        vehicles,
        distance_matrix_df
    )

    if numeric_issues:
        is_valid = False
        validation_messages.extend(numeric_issues)

    matrix_issues = validate_distance_matrix_coverage(
        depot,
        customers,
        distance_matrix_df
    )

    if matrix_issues:
        is_valid = False
        validation_messages.extend(matrix_issues)

    if depot["depot_id"].iloc[0] != "D0":
        validation_messages.append(
            "Warning: The current solver expects the depot ID to be 'D0'. "
            "Please use depot_id = D0 for compatibility."
        )

    return is_valid, validation_messages


def convert_numeric_columns(depot, customers, vehicles, distance_matrix_df):
    """
    Convert numeric columns after validation.
    """

    depot = depot.copy()
    customers = customers.copy()
    vehicles = vehicles.copy()
    distance_matrix_df = distance_matrix_df.copy()

    depot["x_coord"] = pd.to_numeric(depot["x_coord"])
    depot["y_coord"] = pd.to_numeric(depot["y_coord"])

    customers["x_coord"] = pd.to_numeric(customers["x_coord"])
    customers["y_coord"] = pd.to_numeric(customers["y_coord"])
    customers["demand_units"] = pd.to_numeric(
        customers["demand_units"]
    ).astype(int)
    customers["service_time_min"] = pd.to_numeric(
        customers["service_time_min"]
    ).astype(int)

    vehicles["capacity_units"] = pd.to_numeric(
        vehicles["capacity_units"]
    ).astype(int)
    vehicles["fixed_cost"] = pd.to_numeric(vehicles["fixed_cost"])
    vehicles["cost_per_mile"] = pd.to_numeric(vehicles["cost_per_mile"])
    vehicles["max_route_distance"] = pd.to_numeric(
        vehicles["max_route_distance"]
    ).astype(int)

    distance_matrix_df["distance_miles"] = pd.to_numeric(
        distance_matrix_df["distance_miles"]
    )

    return depot, customers, vehicles, distance_matrix_df


# --------------------------------------------------
# Scenario input adjustments
# --------------------------------------------------

def apply_user_inputs(
    customers,
    vehicles,
    demand_growth_pct,
    available_vehicles,
    capacity_adjustment_pct,
    route_limit_adjustment_pct
):
    scenario_customers = customers.copy()
    scenario_vehicles = vehicles.iloc[:available_vehicles].copy()

    scenario_customers["demand_units"] = (
        scenario_customers["demand_units"]
        * (1 + demand_growth_pct / 100)
    ).round().astype(int)

    scenario_vehicles["capacity_units"] = (
        scenario_vehicles["capacity_units"]
        * (1 + capacity_adjustment_pct / 100)
    ).round().astype(int)

    scenario_vehicles["capacity_units"] = scenario_vehicles[
        "capacity_units"
    ].clip(lower=1)

    scenario_vehicles["max_route_distance"] = (
        scenario_vehicles["max_route_distance"]
        * (1 + route_limit_adjustment_pct / 100)
    ).round().astype(int)

    scenario_vehicles["max_route_distance"] = scenario_vehicles[
        "max_route_distance"
    ].clip(lower=1)

    return scenario_customers, scenario_vehicles


# --------------------------------------------------
# Solution extraction for app use
# --------------------------------------------------

def extract_solution_for_app(data, manager, routing, solution):
    route_records = []
    route_summary_records = []

    total_distance = 0
    total_load = 0
    total_operating_cost = 0

    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)

        route_distance = 0
        route_load = 0
        stop_sequence = 0

        vehicle_name = data["vehicles"].iloc[vehicle_id]["vehicle_id"]
        vehicle_type = data["vehicles"].iloc[vehicle_id]["vehicle_type"]
        vehicle_capacity = data["vehicles"].iloc[vehicle_id]["capacity_units"]
        fixed_cost = data["vehicles"].iloc[vehicle_id]["fixed_cost"]
        cost_per_mile = data["vehicles"].iloc[vehicle_id]["cost_per_mile"]
        max_route_distance = data["vehicles"].iloc[vehicle_id][
            "max_route_distance"
        ]

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            location_id = data["location_ids"][node_index]
            demand = data["demands"][node_index]

            route_load += demand

            route_records.append({
                "vehicle_id": vehicle_name,
                "vehicle_type": vehicle_type,
                "stop_sequence": stop_sequence,
                "location_id": location_id,
                "demand_units": demand,
                "route_load_so_far": route_load,
                "vehicle_capacity": vehicle_capacity
            })

            previous_index = index
            index = solution.Value(routing.NextVar(index))

            from_node = manager.IndexToNode(previous_index)
            to_node = manager.IndexToNode(index)

            route_distance += data["distance_matrix"][from_node][to_node]

            stop_sequence += 1

        node_index = manager.IndexToNode(index)
        location_id = data["location_ids"][node_index]

        route_records.append({
            "vehicle_id": vehicle_name,
            "vehicle_type": vehicle_type,
            "stop_sequence": stop_sequence,
            "location_id": location_id,
            "demand_units": 0,
            "route_load_so_far": route_load,
            "vehicle_capacity": vehicle_capacity
        })

        route_distance_miles = route_distance / 100

        if route_load > 0:
            route_travel_cost = route_distance_miles * cost_per_mile
            route_total_cost = route_travel_cost + fixed_cost
            vehicle_used = True
        else:
            route_travel_cost = 0
            route_total_cost = 0
            vehicle_used = False

        number_of_customer_stops = sum(
            1 for record in route_records
            if record["vehicle_id"] == vehicle_name
            and record["location_id"] != "D0"
        )

        if vehicle_capacity > 0:
            capacity_utilization = route_load / vehicle_capacity
        else:
            capacity_utilization = 0

        route_summary_records.append({
            "vehicle_id": vehicle_name,
            "vehicle_type": vehicle_type,
            "route_distance_miles": round(route_distance_miles, 2),
            "max_route_distance": max_route_distance,
            "route_load": route_load,
            "vehicle_capacity": vehicle_capacity,
            "capacity_utilization": round(capacity_utilization, 3),
            "number_of_customer_stops": number_of_customer_stops,
            "fixed_cost": fixed_cost,
            "cost_per_mile": cost_per_mile,
            "route_travel_cost": round(route_travel_cost, 2),
            "route_total_cost": round(route_total_cost, 2),
            "vehicle_used": vehicle_used
        })

        total_distance += route_distance_miles
        total_load += route_load
        total_operating_cost += route_total_cost

    route_df = pd.DataFrame(route_records)
    route_summary_df = pd.DataFrame(route_summary_records)

    result = {
        "route_df": route_df,
        "route_summary_df": route_summary_df,
        "total_distance": round(total_distance, 2),
        "total_load": total_load,
        "total_operating_cost": round(total_operating_cost, 2),
        "active_vehicles": int(route_summary_df["vehicle_used"].sum())
    }

    return result


# --------------------------------------------------
# Scenario solver
# --------------------------------------------------

def solve_scenario(depot, customers, vehicles, distance_matrix_df):
    total_demand = customers["demand_units"].sum()
    total_capacity = vehicles["capacity_units"].sum()

    if total_demand > total_capacity:
        return {
            "feasible": False,
            "reason": "Total customer demand exceeds total available fleet capacity."
        }

    data = build_data_model(
        depot,
        customers,
        vehicles,
        distance_matrix_df
    )

    manager, routing, solution = solve_cvrp(data)

    if solution is None:
        return {
            "feasible": False,
            "reason": (
                "No feasible routing plan was found. "
                "The current route distance limits or fleet configuration may be too restrictive."
            )
        }

    extracted = extract_solution_for_app(data, manager, routing, solution)

    return {
        "feasible": True,
        "data": data,
        **extracted
    }


# --------------------------------------------------
# Helper functions
# --------------------------------------------------

def get_max_utilization(result):
    used_routes = result["route_summary_df"][
        result["route_summary_df"]["vehicle_used"] == True
    ]

    if used_routes.empty:
        return 0

    return used_routes["capacity_utilization"].max()


def get_average_utilization(result):
    used_routes = result["route_summary_df"][
        result["route_summary_df"]["vehicle_used"] == True
    ]

    if used_routes.empty:
        return 0

    return used_routes["capacity_utilization"].mean()


def build_comparison_table(
    base_customers,
    base_vehicles,
    base_result,
    scenario_customers,
    scenario_vehicles,
    scenario_result
):
    comparison_rows = [
        {
            "Metric": "Total customer demand",
            "Base Case": base_customers["demand_units"].sum(),
            "Current Scenario": scenario_customers["demand_units"].sum(),
            "Change": (
                scenario_customers["demand_units"].sum()
                - base_customers["demand_units"].sum()
            ),
            "Format": "units"
        },
        {
            "Metric": "Total fleet capacity",
            "Base Case": base_vehicles["capacity_units"].sum(),
            "Current Scenario": scenario_vehicles["capacity_units"].sum(),
            "Change": (
                scenario_vehicles["capacity_units"].sum()
                - base_vehicles["capacity_units"].sum()
            ),
            "Format": "units"
        },
        {
            "Metric": "Available vehicles",
            "Base Case": len(base_vehicles),
            "Current Scenario": len(scenario_vehicles),
            "Change": len(scenario_vehicles) - len(base_vehicles),
            "Format": "count"
        },
        {
            "Metric": "Active vehicles",
            "Base Case": base_result["active_vehicles"],
            "Current Scenario": scenario_result["active_vehicles"],
            "Change": (
                scenario_result["active_vehicles"]
                - base_result["active_vehicles"]
            ),
            "Format": "count"
        },
        {
            "Metric": "Total delivery distance",
            "Base Case": base_result["total_distance"],
            "Current Scenario": scenario_result["total_distance"],
            "Change": (
                scenario_result["total_distance"]
                - base_result["total_distance"]
            ),
            "Format": "miles"
        },
        {
            "Metric": "Total operating cost",
            "Base Case": base_result["total_operating_cost"],
            "Current Scenario": scenario_result["total_operating_cost"],
            "Change": (
                scenario_result["total_operating_cost"]
                - base_result["total_operating_cost"]
            ),
            "Format": "currency"
        },
        {
            "Metric": "Maximum capacity utilization",
            "Base Case": get_max_utilization(base_result),
            "Current Scenario": get_max_utilization(scenario_result),
            "Change": (
                get_max_utilization(scenario_result)
                - get_max_utilization(base_result)
            ),
            "Format": "percent"
        },
        {
            "Metric": "Average capacity utilization",
            "Base Case": get_average_utilization(base_result),
            "Current Scenario": get_average_utilization(scenario_result),
            "Change": (
                get_average_utilization(scenario_result)
                - get_average_utilization(base_result)
            ),
            "Format": "percent"
        }
    ]

    comparison_df = pd.DataFrame(comparison_rows)

    return comparison_df


def format_comparison_table(comparison_df):
    display_df = comparison_df.copy()

    def format_value(value, value_format):
        if value_format == "currency":
            return f"${value:,.2f}"
        if value_format == "miles":
            return f"{value:,.2f} mi"
        if value_format == "percent":
            return f"{value * 100:.1f}%"
        if value_format == "units":
            return f"{int(value):,} units"
        if value_format == "count":
            return f"{int(value):,}"
        return value

    def format_change(value, value_format):
        sign = "+" if value > 0 else ""

        if value_format == "currency":
            return f"{sign}${value:,.2f}"
        if value_format == "miles":
            return f"{sign}{value:,.2f} mi"
        if value_format == "percent":
            return f"{sign}{value * 100:.1f}%"
        if value_format == "units":
            return f"{sign}{int(value):,} units"
        if value_format == "count":
            return f"{sign}{int(value):,}"
        return value

    display_df["Base Case"] = display_df.apply(
        lambda row: format_value(row["Base Case"], row["Format"]),
        axis=1
    )

    display_df["Current Scenario"] = display_df.apply(
        lambda row: format_value(row["Current Scenario"], row["Format"]),
        axis=1
    )

    display_df["Change"] = display_df.apply(
        lambda row: format_change(row["Change"], row["Format"]),
        axis=1
    )

    display_df = display_df.drop(columns=["Format"])

    return display_df


def diagnose_infeasibility(
    base_customers,
    base_vehicles,
    scenario_customers,
    scenario_vehicles,
    demand_growth_pct,
    available_vehicles,
    capacity_adjustment_pct,
    route_limit_adjustment_pct
):
    total_demand = scenario_customers["demand_units"].sum()
    total_capacity = scenario_vehicles["capacity_units"].sum()

    diagnosis = []
    recommendations = []

    if total_demand > total_capacity:
        capacity_gap = total_demand - total_capacity

        diagnosis.append(
            f"Total scenario demand is {total_demand:,} units, "
            f"but available fleet capacity is only {total_capacity:,} units."
        )

        diagnosis.append(
            f"The scenario has a capacity shortage of {capacity_gap:,} units."
        )

        recommendations.append("Increase the number of available vehicles.")
        recommendations.append(
            "Increase vehicle capacity using the capacity adjustment slider."
        )
        recommendations.append(
            "Reduce demand growth until total demand is less than or equal to available capacity."
        )

    else:
        diagnosis.append(
            "Total fleet capacity is sufficient, but the routing solver still could not find a feasible route plan."
        )

        diagnosis.append(
            "This usually means maximum route distance limits are too restrictive for the customer locations and available fleet."
        )

        recommendations.append(
            "Relax the maximum route distance adjustment slider."
        )
        recommendations.append("Increase the number of available vehicles.")
        recommendations.append(
            "Increase vehicle capacity if routes are also operating near full load."
        )

    if available_vehicles < len(base_vehicles):
        recommendations.append(
            "Restore one or more unavailable vehicles to increase routing flexibility."
        )

    if capacity_adjustment_pct < 0:
        recommendations.append(
            "Remove the negative capacity adjustment or increase vehicle capacity."
        )

    if route_limit_adjustment_pct < 0:
        recommendations.append(
            "Remove the negative route-distance adjustment or allow longer routes."
        )

    if demand_growth_pct > 0:
        recommendations.append(
            "Test a lower demand growth level to identify the highest feasible demand scenario."
        )

    unique_recommendations = []

    for item in recommendations:
        if item not in unique_recommendations:
            unique_recommendations.append(item)

    return diagnosis, unique_recommendations


def build_feasibility_test_table(scenario_customers, scenario_vehicles):
    total_demand = scenario_customers["demand_units"].sum()
    total_capacity = scenario_vehicles["capacity_units"].sum()
    capacity_gap = total_capacity - total_demand

    diagnostic_df = pd.DataFrame({
        "Check": [
            "Total customer demand",
            "Total fleet capacity",
            "Capacity surplus / shortage",
            "Available vehicles",
            "Minimum route distance limit",
            "Maximum route distance limit"
        ],
        "Value": [
            f"{total_demand:,} units",
            f"{total_capacity:,} units",
            f"{capacity_gap:+,} units",
            f"{len(scenario_vehicles)}",
            f"{scenario_vehicles['max_route_distance'].min():,.0f} mi",
            f"{scenario_vehicles['max_route_distance'].max():,.0f} mi"
        ]
    })

    return diagnostic_df


def build_operational_commentary(
    base_result,
    scenario_result,
    active_vehicles,
    total_available_vehicles
):
    used_routes = scenario_result["route_summary_df"][
        scenario_result["route_summary_df"]["vehicle_used"] == True
    ].copy()

    max_util = (
        used_routes["capacity_utilization"].max()
        if not used_routes.empty
        else 0
    )

    avg_util = (
        used_routes["capacity_utilization"].mean()
        if not used_routes.empty
        else 0
    )

    unused_vehicles = total_available_vehicles - active_vehicles

    cost_change = (
        scenario_result["total_operating_cost"]
        - base_result["total_operating_cost"]
    )

    distance_change = (
        scenario_result["total_distance"]
        - base_result["total_distance"]
    )

    comments = []

    comments.append(
        f"The current scenario uses {active_vehicles} out of "
        f"{total_available_vehicles} available vehicles."
    )

    if unused_vehicles > 0:
        comments.append(
            f"{unused_vehicles} vehicle(s) remain unused under the current scenario."
        )

    if cost_change < 0:
        comments.append(
            f"Operating cost decreases by ${abs(cost_change):,.2f} "
            "compared with the base case."
        )
    elif cost_change > 0:
        comments.append(
            f"Operating cost increases by ${cost_change:,.2f} "
            "compared with the base case."
        )
    else:
        comments.append("Operating cost is unchanged compared with the base case.")

    if distance_change < 0:
        comments.append(
            f"Total delivery distance decreases by {abs(distance_change):,.2f} miles "
            "compared with the base case."
        )
    elif distance_change > 0:
        comments.append(
            f"Total delivery distance increases by {distance_change:,.2f} miles "
            "compared with the base case."
        )
    else:
        comments.append(
            "Total delivery distance is unchanged compared with the base case."
        )

    if max_util >= 0.98:
        comments.append(
            "At least one route is operating essentially at full capacity, indicating a tight fleet plan."
        )

    if avg_util >= 0.95:
        comments.append(
            "Average vehicle utilization is very high, suggesting limited capacity slack."
        )
    elif avg_util <= 0.85:
        comments.append(
            "Average utilization is lower, indicating more operational buffer across the active fleet."
        )

    return comments


# --------------------------------------------------
# Load sample data
# --------------------------------------------------

sample_depot, sample_customers, sample_vehicles, sample_distance_matrix = (
    load_sample_data()
)

# --------------------------------------------------
# Sidebar: data mode and downloads
# --------------------------------------------------

st.sidebar.header("Data Source")

st.sidebar.caption(
    "Use the built-in sample dataset, or upload your own CSV files using the same format."
)

data_mode = st.sidebar.radio(
    "Choose data source",
    ["Use sample data", "Upload custom data"]
)

with st.sidebar.expander("Download sample input templates"):
    st.download_button(
        "Download depot.csv",
        data=sample_depot.to_csv(index=False).encode("utf-8"),
        file_name="depot.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.download_button(
        "Download customers.csv",
        data=sample_customers.to_csv(index=False).encode("utf-8"),
        file_name="customers.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.download_button(
        "Download vehicles.csv",
        data=sample_vehicles.to_csv(index=False).encode("utf-8"),
        file_name="vehicles.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.download_button(
        "Download distance_matrix.csv",
        data=sample_distance_matrix.to_csv(index=False).encode("utf-8"),
        file_name="distance_matrix.csv",
        mime="text/csv",
        use_container_width=True
    )

# --------------------------------------------------
# Load selected data
# --------------------------------------------------

if data_mode == "Use sample data":
    base_depot = sample_depot.copy()
    base_customers = sample_customers.copy()
    base_vehicles = sample_vehicles.copy()
    distance_matrix_df = sample_distance_matrix.copy()

else:
    st.sidebar.subheader("Upload Input CSV Files")

    uploaded_depot = st.sidebar.file_uploader(
        "Upload depot.csv",
        type=["csv"]
    )

    uploaded_customers = st.sidebar.file_uploader(
        "Upload customers.csv",
        type=["csv"]
    )

    uploaded_vehicles = st.sidebar.file_uploader(
        "Upload vehicles.csv",
        type=["csv"]
    )

    uploaded_distance_matrix = st.sidebar.file_uploader(
        "Upload distance_matrix.csv",
        type=["csv"]
    )

    base_depot = read_uploaded_csv(uploaded_depot)
    base_customers = read_uploaded_csv(uploaded_customers)
    base_vehicles = read_uploaded_csv(uploaded_vehicles)
    distance_matrix_df = read_uploaded_csv(uploaded_distance_matrix)

    data_valid, validation_messages = validate_uploaded_data(
        base_depot,
        base_customers,
        base_vehicles,
        distance_matrix_df
    )

    st.subheader("Uploaded Data Format Check")

    if data_valid:
        st.success("Uploaded files passed the format compatibility check.")

        (
            base_depot,
            base_customers,
            base_vehicles,
            distance_matrix_df
        ) = convert_numeric_columns(
            base_depot,
            base_customers,
            base_vehicles,
            distance_matrix_df
        )

    else:
        st.error("Uploaded files are not compatible with the required format.")

        for message in validation_messages:
            st.write(f"- {message}")

        st.markdown("### Required File Schemas")

        schema_tables = []

        for dataset_name, columns in REQUIRED_COLUMNS.items():
            for column in columns:
                schema_tables.append({
                    "File": f"{dataset_name}.csv",
                    "Required Column": column
                })

        st.dataframe(
            pd.DataFrame(schema_tables),
            use_container_width=True,
            hide_index=True
        )

        st.info(
            "Download the sample files from the sidebar, keep the same column names, "
            "replace the rows with your own data, and upload the revised CSV files."
        )

        st.stop()

# --------------------------------------------------
# Sidebar controls
# --------------------------------------------------

st.sidebar.header("Scenario Controls")

st.sidebar.caption(
    "Base case uses original demand, all vehicles, original vehicle capacities, "
    "and original route distance limits."
)

if "demand_growth_pct" not in st.session_state:
    st.session_state.demand_growth_pct = 0

if "available_vehicles" not in st.session_state:
    st.session_state.available_vehicles = len(base_vehicles)

if "capacity_adjustment_pct" not in st.session_state:
    st.session_state.capacity_adjustment_pct = 0

if "route_limit_adjustment_pct" not in st.session_state:
    st.session_state.route_limit_adjustment_pct = 0


def reset_to_base_case():
    st.session_state.demand_growth_pct = 0
    st.session_state.available_vehicles = len(base_vehicles)
    st.session_state.capacity_adjustment_pct = 0
    st.session_state.route_limit_adjustment_pct = 0


if st.session_state.available_vehicles > len(base_vehicles):
    st.session_state.available_vehicles = len(base_vehicles)

demand_growth_pct = st.sidebar.slider(
    "Demand Growth (%)",
    min_value=0,
    max_value=30,
    step=5,
    key="demand_growth_pct"
)

available_vehicles = st.sidebar.slider(
    "Available Vehicles",
    min_value=1,
    max_value=len(base_vehicles),
    step=1,
    key="available_vehicles"
)

capacity_adjustment_pct = st.sidebar.slider(
    "Vehicle Capacity Adjustment (%)",
    min_value=-20,
    max_value=30,
    step=5,
    key="capacity_adjustment_pct"
)

route_limit_adjustment_pct = st.sidebar.slider(
    "Maximum Route Distance Adjustment (%)",
    min_value=-20,
    max_value=20,
    step=5,
    key="route_limit_adjustment_pct"
)

st.sidebar.button(
    "Reset to Base Case",
    on_click=reset_to_base_case,
    use_container_width=True
)

# --------------------------------------------------
# Prepare scenario data
# --------------------------------------------------

scenario_customers, scenario_vehicles = apply_user_inputs(
    base_customers,
    base_vehicles,
    demand_growth_pct,
    available_vehicles,
    capacity_adjustment_pct,
    route_limit_adjustment_pct
)

# --------------------------------------------------
# Solve base and current scenario
# --------------------------------------------------

base_result = solve_scenario(
    base_depot,
    base_customers,
    base_vehicles,
    distance_matrix_df
)

scenario_result = solve_scenario(
    base_depot,
    scenario_customers,
    scenario_vehicles,
    distance_matrix_df
)

# --------------------------------------------------
# Base case check
# --------------------------------------------------

if not base_result["feasible"]:
    st.error(
        "The base case is infeasible. Please review the input data before running scenarios."
    )

    st.subheader("Base Case Diagnostic Check")

    diagnostic_df = build_feasibility_test_table(
        base_customers,
        base_vehicles
    )

    st.dataframe(
        diagnostic_df,
        use_container_width=True,
        hide_index=True
    )

    st.stop()

# --------------------------------------------------
# Scenario status
# --------------------------------------------------

st.subheader("Scenario Status")

scenario_total_demand = scenario_customers["demand_units"].sum()
scenario_total_capacity = scenario_vehicles["capacity_units"].sum()

status_col1, status_col2, status_col3 = st.columns(3)

status_col1.metric(
    "Current Scenario Demand",
    f"{scenario_total_demand:,} units"
)

status_col2.metric(
    "Current Scenario Fleet Capacity",
    f"{scenario_total_capacity:,} units"
)

status_col3.metric(
    "Vehicles Available",
    f"{len(scenario_vehicles)}"
)

# --------------------------------------------------
# Infeasible scenario display
# --------------------------------------------------

if not scenario_result["feasible"]:
    st.error(f"Infeasible scenario: {scenario_result['reason']}")

    st.subheader("Infeasibility Diagnosis")

    diagnostic_df = build_feasibility_test_table(
        scenario_customers,
        scenario_vehicles
    )

    st.dataframe(
        diagnostic_df,
        use_container_width=True,
        hide_index=True
    )

    diagnosis, recommendations = diagnose_infeasibility(
        base_customers,
        base_vehicles,
        scenario_customers,
        scenario_vehicles,
        demand_growth_pct,
        available_vehicles,
        capacity_adjustment_pct,
        route_limit_adjustment_pct
    )

    st.markdown("### Likely Cause")

    for item in diagnosis:
        st.write(f"- {item}")

    st.markdown("### Recommended Adjustments")

    for item in recommendations:
        st.write(f"- {item}")

    st.subheader("Base Case Reference")

    base_reference_df = pd.DataFrame({
        "Metric": [
            "Base customer demand",
            "Base fleet capacity",
            "Base operating cost",
            "Base delivery distance",
            "Base active vehicles",
            "Base maximum utilization"
        ],
        "Value": [
            f"{base_customers['demand_units'].sum():,} units",
            f"{base_vehicles['capacity_units'].sum():,} units",
            f"${base_result['total_operating_cost']:,.2f}",
            f"{base_result['total_distance']:,.2f} mi",
            f"{base_result['active_vehicles']}",
            f"{get_max_utilization(base_result) * 100:.1f}%"
        ]
    })

    st.dataframe(
        base_reference_df,
        use_container_width=True,
        hide_index=True
    )

    st.stop()

st.success("Feasible routing plan found.")

# --------------------------------------------------
# Base vs scenario comparison
# --------------------------------------------------

st.subheader("Base Case vs Current Scenario")

comparison_df = build_comparison_table(
    base_customers,
    base_vehicles,
    base_result,
    scenario_customers,
    scenario_vehicles,
    scenario_result
)

display_comparison_df = format_comparison_table(comparison_df)

st.dataframe(
    display_comparison_df,
    use_container_width=True,
    hide_index=True
)

# --------------------------------------------------
# KPI summary
# --------------------------------------------------

st.subheader("Current Scenario Performance")

cost_delta = (
    scenario_result["total_operating_cost"]
    - base_result["total_operating_cost"]
)

distance_delta = (
    scenario_result["total_distance"]
    - base_result["total_distance"]
)

active_vehicle_delta = (
    scenario_result["active_vehicles"]
    - base_result["active_vehicles"]
)

max_utilization = get_max_utilization(scenario_result) * 100

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

kpi_col1.metric(
    "Total Operating Cost",
    f"${scenario_result['total_operating_cost']:,.2f}",
    delta=f"{cost_delta:+.2f} vs base"
)

kpi_col2.metric(
    "Total Delivery Distance",
    f"{scenario_result['total_distance']:,.2f} mi",
    delta=f"{distance_delta:+.2f} mi vs base"
)

kpi_col3.metric(
    "Active Vehicles",
    f"{scenario_result['active_vehicles']}",
    delta=f"{active_vehicle_delta:+d} vs base"
)

kpi_col4.metric(
    "Maximum Capacity Utilization",
    f"{max_utilization:.1f}%"
)

# --------------------------------------------------
# Operational commentary
# --------------------------------------------------

st.subheader("Operational Interpretation")

comments = build_operational_commentary(
    base_result,
    scenario_result,
    scenario_result["active_vehicles"],
    len(scenario_vehicles)
)

for comment in comments:
    st.write(f"- {comment}")

# --------------------------------------------------
# Tabs for results
# --------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "Optimized Route Map",
    "Vehicle Summary",
    "Driver Stop Sequence",
    "Input Data"
])

with tab1:
    st.markdown("### Optimized Route Map for Current Scenario")
    st.caption(
        "Each colored line represents one active vehicle route. "
        "The route starts at the depot, visits assigned customers, and returns to the depot."
    )

    locations = prepare_location_data(base_depot, scenario_customers)

    plot_df = build_route_plot_dataframe(
        scenario_result["route_df"],
        locations
    )

    route_map_fig = create_route_map(
        plot_df,
        scenario_result["route_summary_df"]
    )

    st.plotly_chart(route_map_fig, use_container_width=True)

with tab2:
    st.markdown("### Vehicle-Level Route Summary")
    st.caption(
        "This table summarizes each vehicle route, including distance, load, utilization, "
        "number of customer stops, and operating cost."
    )

    show_unused_vehicles = st.checkbox(
        "Show unused vehicles",
        value=False
    )

    display_route_summary = scenario_result["route_summary_df"].copy()

    display_route_summary["capacity_utilization"] = (
        display_route_summary["capacity_utilization"] * 100
    ).round(1)

    if not show_unused_vehicles:
        display_route_summary = display_route_summary[
            display_route_summary["vehicle_used"] == True
        ]

    st.dataframe(
        display_route_summary,
        use_container_width=True,
        hide_index=True
    )

    route_summary_csv = scenario_result["route_summary_df"].to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download Vehicle Route Summary CSV",
        data=route_summary_csv,
        file_name="route_summary_current_scenario.csv",
        mime="text/csv"
    )

with tab3:
    st.markdown("### Driver Stop Sequence")
    st.caption(
        "This table shows the exact visit order for each vehicle. "
        "It can be used as a driver-level route assignment file."
    )

    route_plan_display = scenario_result["route_df"].copy()

    show_depot_rows = st.checkbox(
        "Show depot start/end rows",
        value=True
    )

    if not show_depot_rows:
        route_plan_display = route_plan_display[
            route_plan_display["location_id"] != "D0"
        ]

    st.dataframe(
        route_plan_display,
        use_container_width=True,
        hide_index=True
    )

    route_plan_csv = scenario_result["route_df"].to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download Driver Stop Sequence CSV",
        data=route_plan_csv,
        file_name="optimized_routes_current_scenario.csv",
        mime="text/csv"
    )

with tab4:
    st.markdown("### Input Data")
    st.caption(
        "Preview the base input data and the adjusted current-scenario data used by the solver."
    )

    input_tab1, input_tab2 = st.tabs([
        "Current Scenario Inputs",
        "Base Input Data"
    ])

    with input_tab1:
        st.markdown("#### Current Scenario Customer Demand Preview")
        st.caption(
            "Customer demand after applying the demand-growth slider."
        )

        st.dataframe(
            scenario_customers.head(10),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### Current Scenario Vehicle Fleet")
        st.caption(
            "Vehicle fleet after applying the available-vehicle, capacity, and route-distance controls."
        )

        st.dataframe(
            scenario_vehicles,
            use_container_width=True,
            hide_index=True
        )

    with input_tab2:
        st.markdown("#### Base Customer Data Preview")

        st.dataframe(
            base_customers.head(10),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### Base Vehicle Fleet")

        st.dataframe(
            base_vehicles,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### Depot")

        st.dataframe(
            base_depot,
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### Distance Matrix Preview")

        st.dataframe(
            distance_matrix_df.head(20),
            use_container_width=True,
            hide_index=True
        )