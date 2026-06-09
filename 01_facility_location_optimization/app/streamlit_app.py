"""
streamlit_app.py

Interactive dashboard for the Regional Distribution Center Network Optimization project.

The dashboard allows stakeholders to:
1. Use sample synthetic data or upload their own input files
2. Adjust facility location scenario inputs
3. Run the optimization model
4. View selected distribution centers
5. View customer assignments
6. Visualize the optimized distribution network
7. Run dynamic scenario comparison

Author: Mo Moha
Project: Regional Distribution Center Network Optimization
"""

import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st


# Add src folder to Python path so Streamlit can import project functions
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))


from optimization_model import build_and_solve_model, extract_solution, load_data


def load_sample_data():
    """
    Load sample synthetic project data.

    Returns
    -------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    transportation_costs : pandas.DataFrame
        Transportation cost data.
    """

    facilities, customers, transportation_costs = load_data()

    return facilities, customers, transportation_costs


def load_uploaded_data(facilities_file, customers_file, transportation_file):
    """
    Load user-uploaded CSV files.

    Parameters
    ----------
    facilities_file : UploadedFile
        Uploaded candidate facilities CSV.

    customers_file : UploadedFile
        Uploaded customer zones CSV.

    transportation_file : UploadedFile
        Uploaded transportation costs CSV.

    Returns
    -------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    transportation_costs : pandas.DataFrame
        Transportation cost data.
    """

    facilities = pd.read_csv(facilities_file)
    customers = pd.read_csv(customers_file)
    transportation_costs = pd.read_csv(transportation_file)

    return facilities, customers, transportation_costs


def validate_input_data(facilities, customers, transportation_costs):
    """
    Validate required columns in uploaded or sample datasets.

    Parameters
    ----------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    transportation_costs : pandas.DataFrame
        Transportation cost data.

    Returns
    -------
    tuple
        is_valid : bool
            Whether all required columns exist.

        messages : list
            Validation messages.
    """

    required_facility_columns = {
        "facility_id",
        "facility_name",
        "x_coord",
        "y_coord",
        "opening_cost",
        "capacity"
    }

    required_customer_columns = {
        "customer_id",
        "customer_name",
        "x_coord",
        "y_coord",
        "demand"
    }

    required_transport_columns = {
        "customer_id",
        "facility_id",
        "distance",
        "cost_per_unit",
        "within_service_radius"
    }

    messages = []

    missing_facility_cols = required_facility_columns - set(facilities.columns)
    missing_customer_cols = required_customer_columns - set(customers.columns)
    missing_transport_cols = required_transport_columns - set(transportation_costs.columns)

    if missing_facility_cols:
        messages.append(
            f"Candidate facilities file is missing columns: {sorted(missing_facility_cols)}"
        )

    if missing_customer_cols:
        messages.append(
            f"Customer zones file is missing columns: {sorted(missing_customer_cols)}"
        )

    if missing_transport_cols:
        messages.append(
            f"Transportation costs file is missing columns: {sorted(missing_transport_cols)}"
        )

    is_valid = len(messages) == 0

    return is_valid, messages


def create_csv_download_button(dataframe, file_name, label):
    """
    Create a Streamlit download button for a dataframe.

    Parameters
    ----------
    dataframe : pandas.DataFrame
        Data to download.

    file_name : str
        Name of the downloaded CSV file.

    label : str
        Button label.
    """

    csv_data = dataframe.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=label,
        data=csv_data,
        file_name=file_name,
        mime="text/csv"
    )


def plot_solution(facilities, customers, selected_facilities, customer_assignments):
    """
    Create a matplotlib figure for the facility location solution.

    Parameters
    ----------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    selected_facilities : pandas.DataFrame
        Selected facility data.

    customer_assignments : pandas.DataFrame
        Customer assignment results.

    Returns
    -------
    matplotlib.figure.Figure
        Facility assignment plot.
    """

    fig, ax = plt.subplots(figsize=(11, 8))

    ax.scatter(
        facilities["x_coord"],
        facilities["y_coord"],
        marker="s",
        s=120,
        label="Candidate Distribution Centers"
    )

    ax.scatter(
        selected_facilities["x_coord"],
        selected_facilities["y_coord"],
        marker="*",
        s=350,
        label="Selected Distribution Centers"
    )

    ax.scatter(
        customers["x_coord"],
        customers["y_coord"],
        marker="o",
        s=customers["demand"],
        alpha=0.6,
        label="Customer Zones"
    )

    for _, row in customer_assignments.iterrows():
        ax.plot(
            [row["x_coord_customer"], row["x_coord_facility"]],
            [row["y_coord_customer"], row["y_coord_facility"]],
            linewidth=0.8,
            alpha=0.35
        )

    for _, row in selected_facilities.iterrows():
        ax.text(
            row["x_coord"] + 1,
            row["y_coord"] + 1,
            row["facility_id"],
            fontsize=10,
            fontweight="bold"
        )

    ax.set_title("Optimized Distribution Center Network")
    ax.set_xlabel("X Coordinate")
    ax.set_ylabel("Y Coordinate")
    ax.grid(True, alpha=0.4)
    ax.legend()

    return fig


def calculate_facility_utilization(selected_facilities, customer_assignments):
    """
    Calculate selected facility utilization.

    Parameters
    ----------
    selected_facilities : pandas.DataFrame
        Selected facility data.

    customer_assignments : pandas.DataFrame
        Customer assignment results.

    Returns
    -------
    pandas.DataFrame
        Facility utilization table.
    """

    assigned_demand = (
        customer_assignments
        .groupby("facility_id")["assigned_demand"]
        .sum()
        .reset_index()
        .rename(columns={"assigned_demand": "total_assigned_demand"})
    )

    utilization = selected_facilities.merge(
        assigned_demand,
        on="facility_id",
        how="left"
    )

    utilization["total_assigned_demand"] = utilization["total_assigned_demand"].fillna(0)

    utilization["capacity_utilization"] = (
        utilization["total_assigned_demand"] / utilization["capacity"]
    )

    utilization["capacity_utilization_percent"] = (
        utilization["capacity_utilization"] * 100
    ).round(1)

    return utilization


def diagnose_infeasibility(facilities, customers, max_facilities=None, budget=None):
    """
    Provide a simple infeasibility diagnosis for stakeholder interpretation.

    Parameters
    ----------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data for the current scenario.

    max_facilities : int or None
        Maximum number of facilities allowed.

    budget : float or None
        Opening budget limit.

    Returns
    -------
    dict
        Infeasibility diagnosis summary.
    """

    total_demand = customers["demand"].sum()

    candidate_facilities = facilities.copy()

    if budget is not None:
        candidate_facilities = candidate_facilities[
            candidate_facilities["opening_cost"] <= budget
        ]

    if max_facilities is not None:
        max_capacity = (
            candidate_facilities
            .sort_values("capacity", ascending=False)
            .head(max_facilities)["capacity"]
            .sum()
        )
    else:
        max_capacity = candidate_facilities["capacity"].sum()

    capacity_gap = total_demand - max_capacity

    diagnosis = {
        "total_demand": total_demand,
        "max_possible_capacity": max_capacity,
        "capacity_gap": capacity_gap,
        "capacity_feasible": total_demand <= max_capacity
    }

    return diagnosis


def run_dynamic_scenario_comparison(
    facilities,
    customers,
    transportation_costs,
    current_demand_growth_percent,
    current_max_facilities,
    current_budget
):
    """
    Run a dynamic scenario comparison based on the user's current dashboard settings.

    Parameters
    ----------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    transportation_costs : pandas.DataFrame
        Transportation cost data.

    current_demand_growth_percent : int or float
        Current demand growth percentage selected by the user.

    current_max_facilities : int or None
        Current maximum facility limit selected by the user.

    current_budget : float or None
        Current opening budget selected by the user.

    Returns
    -------
    pandas.DataFrame
        Scenario comparison results.
    """

    scenario_definitions = [
        {
            "scenario_name": "Current Scenario",
            "demand_growth_percent": current_demand_growth_percent,
            "max_facilities": current_max_facilities,
            "budget": current_budget
        },
        {
            "scenario_name": "No Facility Limit",
            "demand_growth_percent": current_demand_growth_percent,
            "max_facilities": None,
            "budget": current_budget
        },
        {
            "scenario_name": "Max 3 Centers",
            "demand_growth_percent": current_demand_growth_percent,
            "max_facilities": 3,
            "budget": current_budget
        },
        {
            "scenario_name": "Max 4 Centers",
            "demand_growth_percent": current_demand_growth_percent,
            "max_facilities": 4,
            "budget": current_budget
        },
        {
            "scenario_name": "No Budget Limit",
            "demand_growth_percent": current_demand_growth_percent,
            "max_facilities": current_max_facilities,
            "budget": None
        },
        {
            "scenario_name": "Demand Growth +10%",
            "demand_growth_percent": min(current_demand_growth_percent + 10, 50),
            "max_facilities": current_max_facilities,
            "budget": current_budget
        }
    ]

    scenario_results = []

    for scenario in scenario_definitions:

        scenario_customers = customers.copy()
        demand_multiplier = 1 + scenario["demand_growth_percent"] / 100

        scenario_customers["demand"] = (
            scenario_customers["demand"] * demand_multiplier
        ).round(0)

        model, open_facility_vars, assignment_vars = build_and_solve_model(
            facilities=facilities,
            customers=scenario_customers,
            transportation_costs=transportation_costs,
            max_facilities=scenario["max_facilities"],
            budget=scenario["budget"]
        )

        selected_facilities, customer_assignments, summary = extract_solution(
            model=model,
            facilities=facilities,
            customers=scenario_customers,
            transportation_costs=transportation_costs,
            open_facility_vars=open_facility_vars,
            assignment_vars=assignment_vars
        )

        total_demand = scenario_customers["demand"].sum()

        if summary["solver_status"] == "Optimal":
            selected_capacity = selected_facilities["capacity"].sum()

            capacity_utilization = (
                total_demand / selected_capacity
                if selected_capacity > 0
                else None
            )

            selected_facility_ids = ", ".join(summary["selected_facilities"])
            total_cost = summary["total_cost"]
            number_selected = summary["number_of_selected_facilities"]

        else:
            selected_capacity = None
            capacity_utilization = None
            selected_facility_ids = "Infeasible"
            total_cost = None
            number_selected = None

        scenario_results.append({
            "scenario_name": scenario["scenario_name"],
            "solver_status": summary["solver_status"],
            "demand_growth_percent": scenario["demand_growth_percent"],
            "max_facilities": (
                "No limit"
                if scenario["max_facilities"] is None
                else scenario["max_facilities"]
            ),
            "budget": (
                "No limit"
                if scenario["budget"] is None
                else scenario["budget"]
            ),
            "total_cost": total_cost,
            "number_of_selected_centers": number_selected,
            "selected_centers": selected_facility_ids,
            "total_demand": total_demand,
            "selected_capacity": selected_capacity,
            "capacity_utilization": capacity_utilization
        })

    scenario_results = pd.DataFrame(scenario_results)

    return scenario_results


def plot_scenario_total_cost(scenario_results):
    """
    Plot total cost by scenario.

    Parameters
    ----------
    scenario_results : pandas.DataFrame
        Scenario comparison results.

    Returns
    -------
    matplotlib.figure.Figure
        Total cost scenario comparison chart.
    """

    feasible_results = scenario_results[
        scenario_results["solver_status"] == "Optimal"
    ].copy()

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.bar(
        feasible_results["scenario_name"],
        feasible_results["total_cost"]
    )

    ax.set_title("Total Cost by Scenario")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Total Cost ($)")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.4)

    for index, value in enumerate(feasible_results["total_cost"]):
        ax.text(
            index,
            value,
            f"${value:,.0f}",
            ha="center",
            va="bottom",
            fontsize=8
        )

    fig.tight_layout()

    return fig


def plot_scenario_capacity_utilization(scenario_results):
    """
    Plot capacity utilization by scenario.

    Parameters
    ----------
    scenario_results : pandas.DataFrame
        Scenario comparison results.

    Returns
    -------
    matplotlib.figure.Figure
        Capacity utilization scenario comparison chart.
    """

    feasible_results = scenario_results[
        scenario_results["solver_status"] == "Optimal"
    ].copy()

    feasible_results["capacity_utilization_percent"] = (
        feasible_results["capacity_utilization"] * 100
    )

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.bar(
        feasible_results["scenario_name"],
        feasible_results["capacity_utilization_percent"]
    )

    ax.set_title("Capacity Utilization by Scenario")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Capacity Utilization (%)")
    ax.set_ylim(0, 120)
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.4)

    for index, value in enumerate(feasible_results["capacity_utilization_percent"]):
        ax.text(
            index,
            value,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8
        )

    fig.tight_layout()

    return fig


def main():
    """
    Main Streamlit app.
    """

    st.set_page_config(
        page_title="Regional Distribution Network Optimization",
        page_icon="📦",
        layout="wide"
    )

    st.title("Regional Distribution Center Network Optimization")

    st.write(
        """
        This dashboard helps evaluate where to open distribution centers and how to assign
        customer demand zones while minimizing total cost. Users can work with the built-in
        synthetic sample data or upload their own CSV files.
        """
    )

    st.sidebar.header("Scenario Controls")

    data_source = st.sidebar.radio(
        "Data Source",
        options=["Use sample data", "Upload my own data"]
    )

    sample_facilities, sample_customers, sample_transportation_costs = load_sample_data()

    st.sidebar.subheader("Sample Data Downloads")

    create_csv_download_button(
        dataframe=sample_facilities,
        file_name="sample_candidate_facilities.csv",
        label="Download Facility Sample"
    )

    create_csv_download_button(
        dataframe=sample_customers,
        file_name="sample_customer_zones.csv",
        label="Download Customer Sample"
    )

    create_csv_download_button(
        dataframe=sample_transportation_costs,
        file_name="sample_transportation_costs.csv",
        label="Download Transportation Sample"
    )

    if data_source == "Use sample data":
        facilities = sample_facilities
        customers = sample_customers
        transportation_costs = sample_transportation_costs

    else:
        st.subheader("Upload Custom Input Files")

        st.write(
            """
            Upload three CSV files using the same structure as the sample templates:
            candidate facilities, customer zones, and transportation costs.
            """
        )

        facilities_file = st.file_uploader(
            "Upload candidate facilities CSV",
            type=["csv"]
        )

        customers_file = st.file_uploader(
            "Upload customer zones CSV",
            type=["csv"]
        )

        transportation_file = st.file_uploader(
            "Upload transportation costs CSV",
            type=["csv"]
        )

        if not facilities_file or not customers_file or not transportation_file:
            st.info("Please upload all three CSV files to run the optimization.")
            return

        facilities, customers, transportation_costs = load_uploaded_data(
            facilities_file=facilities_file,
            customers_file=customers_file,
            transportation_file=transportation_file
        )

    is_valid, validation_messages = validate_input_data(
        facilities=facilities,
        customers=customers,
        transportation_costs=transportation_costs
    )

    if not is_valid:
        st.error("Input data validation failed.")

        for message in validation_messages:
            st.write(message)

        return

    demand_growth_percent = st.sidebar.slider(
        "Demand Growth (%)",
        min_value=0,
        max_value=50,
        value=0,
        step=5
    )

    max_facilities_option = st.sidebar.selectbox(
        "Maximum Number of Distribution Centers",
        options=["No limit", 2, 3, 4, 5, 6, 7, 8],
        index=0
    )

    budget_option = st.sidebar.selectbox(
        "Opening Budget",
        options=[
            "No budget limit",
            350000,
            450000,
            550000,
            700000,
            900000
        ],
        index=0
    )

    run_scenario_comparison = st.sidebar.checkbox(
        "Run Scenario Comparison",
        value=True
    )

    run_model = st.sidebar.button("Run Optimization")

    demand_multiplier = 1 + demand_growth_percent / 100

    scenario_customers = customers.copy()
    scenario_customers["demand"] = (
        scenario_customers["demand"] * demand_multiplier
    ).round(0)

    max_facilities = (
        None
        if max_facilities_option == "No limit"
        else int(max_facilities_option)
    )

    budget = (
        None
        if budget_option == "No budget limit"
        else float(budget_option)
    )

    st.subheader("Input Data Preview")

    st.write(
        """
        Only the first few rows are shown here. Download the sample files from the sidebar
        if you want to review the required input structure.
        """
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("Candidate Distribution Centers")
        st.dataframe(facilities.head(5), use_container_width=True)
        st.caption(f"Showing 5 of {len(facilities)} rows")

    with col2:
        st.write("Customer Zones")
        st.dataframe(scenario_customers.head(5), use_container_width=True)
        st.caption(f"Showing 5 of {len(scenario_customers)} rows")

    with col3:
        st.write("Transportation Costs")
        st.dataframe(transportation_costs.head(5), use_container_width=True)
        st.caption(f"Showing 5 of {len(transportation_costs)} rows")

    if run_model:

        model, open_facility_vars, assignment_vars = build_and_solve_model(
            facilities=facilities,
            customers=scenario_customers,
            transportation_costs=transportation_costs,
            max_facilities=max_facilities,
            budget=budget
        )

        selected_facilities, customer_assignments, summary = extract_solution(
            model=model,
            facilities=facilities,
            customers=scenario_customers,
            transportation_costs=transportation_costs,
            open_facility_vars=open_facility_vars,
            assignment_vars=assignment_vars
        )

        st.subheader("Optimization Results")

        if summary["solver_status"] != "Optimal":

            diagnosis = diagnose_infeasibility(
                facilities=facilities,
                customers=scenario_customers,
                max_facilities=max_facilities,
                budget=budget
            )

            st.error(f"Solver status: {summary['solver_status']}")

            st.write(
                """
                The selected scenario is infeasible. This means the model could not find
                a distribution network that satisfies all demand while respecting the selected
                constraints.
                """
            )

            st.subheader("Infeasibility Diagnosis")

            diag_col1, diag_col2, diag_col3 = st.columns(3)

            with diag_col1:
                st.metric(
                    "Scenario Total Demand",
                    f"{diagnosis['total_demand']:,.0f}"
                )

            with diag_col2:
                st.metric(
                    "Maximum Possible Capacity",
                    f"{diagnosis['max_possible_capacity']:,.0f}"
                )

            with diag_col3:
                st.metric(
                    "Capacity Gap",
                    f"{diagnosis['capacity_gap']:,.0f}"
                )

            if not diagnosis["capacity_feasible"]:
                st.warning(
                    f"""
                    Capacity appears to be the main issue. Under the selected facility limit,
                    the network can provide at most {diagnosis['max_possible_capacity']:,.0f}
                    units of capacity, but the scenario requires {diagnosis['total_demand']:,.0f}
                    units of demand.

                    The capacity gap is {diagnosis['capacity_gap']:,.0f} units.
                    """
                )

                st.write(
                    """
                    Recommended actions:

                    - Increase the maximum number of distribution centers.
                    - Reduce demand growth.
                    - Add more facility capacity.
                    - Relax other service constraints if appropriate.
                    """
                )

            else:
                st.info(
                    """
                    Total capacity appears sufficient, so infeasibility may be caused by
                    other constraints, such as service-radius restrictions, budget limits,
                    or customer-facility assignment restrictions.
                    """
                )

                st.write(
                    """
                    Recommended actions:

                    - Increase the opening budget.
                    - Increase the maximum service radius.
                    - Allow more distribution centers to open.
                    - Review whether each customer has at least one eligible facility.
                    """
                )

            return

        metric_col1, metric_col2, metric_col3 = st.columns(3)

        with metric_col1:
            st.metric(
                "Total Cost",
                f"${summary['total_cost']:,.0f}"
            )

        with metric_col2:
            st.metric(
                "Selected Distribution Centers",
                summary["number_of_selected_facilities"]
            )

        with metric_col3:
            total_demand = scenario_customers["demand"].sum()
            total_capacity = selected_facilities["capacity"].sum()
            utilization = total_demand / total_capacity if total_capacity > 0 else 0

            st.metric(
                "Capacity Utilization",
                f"{utilization * 100:.1f}%"
            )

        st.write("Selected Distribution Center IDs:")
        st.success(", ".join(summary["selected_facilities"]))

        st.subheader("Selected Distribution Centers")

        st.dataframe(selected_facilities, use_container_width=True)

        create_csv_download_button(
            dataframe=selected_facilities,
            file_name="selected_distribution_centers.csv",
            label="Download Selected Distribution Centers"
        )

        st.subheader("Facility Utilization")

        facility_utilization = calculate_facility_utilization(
            selected_facilities=selected_facilities,
            customer_assignments=customer_assignments
        )

        utilization_view = facility_utilization[
            [
                "facility_id",
                "facility_name",
                "capacity",
                "total_assigned_demand",
                "capacity_utilization_percent"
            ]
        ]

        st.dataframe(utilization_view, use_container_width=True)

        create_csv_download_button(
            dataframe=utilization_view,
            file_name="facility_utilization.csv",
            label="Download Facility Utilization"
        )

        st.subheader("Network Visualization")

        fig = plot_solution(
            facilities=facilities,
            customers=scenario_customers,
            selected_facilities=selected_facilities,
            customer_assignments=customer_assignments
        )

        st.pyplot(fig)

        st.subheader("Customer Assignments")

        st.dataframe(customer_assignments.head(20), use_container_width=True)
        st.caption(f"Showing 20 of {len(customer_assignments)} assignment rows")

        create_csv_download_button(
            dataframe=customer_assignments,
            file_name="customer_assignments.csv",
            label="Download Full Customer Assignments"
        )

        if run_scenario_comparison:

            st.subheader("Dynamic Scenario Comparison")

            st.write(
                """
                This section compares the current scenario with alternative network
                design assumptions. It helps evaluate how sensitive the solution is
                to facility limits, budget limits, and demand growth.
                """
            )

            scenario_results = run_dynamic_scenario_comparison(
                facilities=facilities,
                customers=customers,
                transportation_costs=transportation_costs,
                current_demand_growth_percent=demand_growth_percent,
                current_max_facilities=max_facilities,
                current_budget=budget
            )

            scenario_display = scenario_results.copy()

            scenario_display["total_cost"] = scenario_display["total_cost"].apply(
                lambda x: f"${x:,.0f}" if pd.notnull(x) else "Infeasible"
            )

            scenario_display["capacity_utilization"] = scenario_display[
                "capacity_utilization"
            ].apply(
                lambda x: f"{x * 100:.1f}%" if pd.notnull(x) else "Infeasible"
            )

            st.dataframe(scenario_display, use_container_width=True)

            create_csv_download_button(
                dataframe=scenario_results,
                file_name="dynamic_scenario_comparison.csv",
                label="Download Scenario Comparison"
            )

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.pyplot(plot_scenario_total_cost(scenario_results))

            with chart_col2:
                st.pyplot(plot_scenario_capacity_utilization(scenario_results))

    else:
        st.info("Adjust scenario controls and click 'Run Optimization' to solve the model.")


if __name__ == "__main__":
    main()