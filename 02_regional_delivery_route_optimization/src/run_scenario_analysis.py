import os
import sys
import pandas as pd

# Allow this script to import functions from solve_vrp.py
sys.path.append("src")

from solve_vrp import build_data_model, solve_cvrp, extract_solution


def load_base_data():
    """
    Load original project data.
    """

    depot = pd.read_csv("data/depot.csv")
    customers = pd.read_csv("data/customers.csv")
    vehicles = pd.read_csv("data/vehicles.csv")
    distance_matrix_df = pd.read_csv("data/distance_matrix.csv")

    return depot, customers, vehicles, distance_matrix_df


def apply_scenario(customers, vehicles, scenario_name):
    """
    Modify customer or vehicle data based on the scenario.
    """

    scenario_customers = customers.copy()
    scenario_vehicles = vehicles.copy()

    if scenario_name == "Base Case":
        pass

    elif scenario_name == "Demand Growth 10%":
        scenario_customers["demand_units"] = (
            scenario_customers["demand_units"] * 1.10
        ).round().astype(int)

    elif scenario_name == "Demand Growth 20%":
        scenario_customers["demand_units"] = (
            scenario_customers["demand_units"] * 1.20
        ).round().astype(int)

    elif scenario_name == "Reduced Fleet":
        # Keep only the first 4 vehicles.
        # This tests whether the current fleet can still serve all demand
        # after one vehicle is unavailable.
        scenario_vehicles = scenario_vehicles.iloc[:4].copy()

    elif scenario_name == "Tight Route Limit":
        # Reduce each vehicle's maximum allowed route distance by 15%.
        scenario_vehicles["max_route_distance"] = (
            scenario_vehicles["max_route_distance"] * 0.85
        ).round().astype(int)

    elif scenario_name == "Expanded Capacity":
        # Increase each vehicle's capacity by 15%.
        scenario_vehicles["capacity_units"] = (
            scenario_vehicles["capacity_units"] * 1.15
        ).round().astype(int)

    else:
        raise ValueError(f"Unknown scenario: {scenario_name}")

    return scenario_customers, scenario_vehicles


def create_scenario_file_name(scenario_name):
    """
    Convert scenario name into a clean file name.
    """

    scenario_file_name = (
        scenario_name
        .lower()
        .replace(" ", "_")
        .replace("%", "pct")
    )

    return scenario_file_name


def save_scenario_route_outputs(scenario_name):
    """
    Save scenario-specific copies of optimized routes and route summary.

    Note:
    extract_solution() writes the latest solved route to:
    - data/optimized_routes.csv
    - data/route_summary.csv

    This function copies those files into scenario-specific outputs.
    """

    scenario_file_name = create_scenario_file_name(scenario_name)

    os.makedirs("outputs/scenarios", exist_ok=True)

    optimized_routes = pd.read_csv("data/optimized_routes.csv")
    route_summary = pd.read_csv("data/route_summary.csv")

    optimized_routes_path = (
        f"outputs/scenarios/{scenario_file_name}_optimized_routes.csv"
    )

    route_summary_path = (
        f"outputs/scenarios/{scenario_file_name}_route_summary.csv"
    )

    optimized_routes.to_csv(optimized_routes_path, index=False)
    route_summary.to_csv(route_summary_path, index=False)

    print(f"Scenario route file saved to: {optimized_routes_path}")
    print(f"Scenario summary file saved to: {route_summary_path}")


def summarize_solution(
    scenario_name,
    customers,
    vehicles,
    route_summary_df,
    feasible
):
    """
    Create one-row summary for each scenario.
    """

    total_demand = customers["demand_units"].sum()
    total_capacity = vehicles["capacity_units"].sum()

    if not feasible:
        return {
            "scenario": scenario_name,
            "feasible": False,
            "total_demand": total_demand,
            "total_capacity": total_capacity,
            "active_vehicles": None,
            "total_distance_miles": None,
            "total_operating_cost": None,
            "average_capacity_utilization": None,
            "maximum_capacity_utilization": None
        }

    used_routes = route_summary_df[route_summary_df["vehicle_used"] == True]

    active_vehicles = len(used_routes)
    total_distance = route_summary_df["route_distance_miles"].sum()
    total_operating_cost = route_summary_df["route_total_cost"].sum()

    average_utilization = used_routes["capacity_utilization"].mean()
    maximum_utilization = used_routes["capacity_utilization"].max()

    return {
        "scenario": scenario_name,
        "feasible": True,
        "total_demand": total_demand,
        "total_capacity": total_capacity,
        "active_vehicles": active_vehicles,
        "total_distance_miles": round(total_distance, 2),
        "total_operating_cost": round(total_operating_cost, 2),
        "average_capacity_utilization": round(average_utilization, 3),
        "maximum_capacity_utilization": round(maximum_utilization, 3)
    }


def run_single_scenario(
    scenario_name,
    depot,
    base_customers,
    base_vehicles,
    distance_matrix_df
):
    """
    Run one scenario and return the summary row.
    """

    print("\n" + "=" * 60)
    print(f"Running scenario: {scenario_name}")
    print("=" * 60)

    customers, vehicles = apply_scenario(
        base_customers,
        base_vehicles,
        scenario_name
    )

    data = build_data_model(
        depot,
        customers,
        vehicles,
        distance_matrix_df
    )

    total_demand = sum(data["demands"])
    total_capacity = sum(data["vehicle_capacities"])

    print(f"Total demand: {total_demand}")
    print(f"Total capacity: {total_capacity}")

    if total_demand > total_capacity:
        print("Scenario infeasible before solving: demand exceeds capacity.")

        return summarize_solution(
            scenario_name,
            customers,
            vehicles,
            route_summary_df=None,
            feasible=False
        )

    manager, routing, solution = solve_cvrp(data)

    if solution is None:
        print("Scenario infeasible after solving.")
        print("Possible reason: route distance limits may be too restrictive.")

        return summarize_solution(
            scenario_name,
            customers,
            vehicles,
            route_summary_df=None,
            feasible=False
        )

    # Extract solution using the existing function.
    # This writes the latest solved files to:
    # data/optimized_routes.csv
    # data/route_summary.csv
    _, route_summary_df = extract_solution(
        data,
        manager,
        routing,
        solution
    )

    # Save scenario-specific route files.
    save_scenario_route_outputs(scenario_name)

    summary_row = summarize_solution(
        scenario_name,
        customers,
        vehicles,
        route_summary_df,
        feasible=True
    )

    return summary_row


def main():
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("outputs/scenarios", exist_ok=True)

    depot, customers, vehicles, distance_matrix_df = load_base_data()

    scenario_names = [
        "Base Case",
        "Demand Growth 10%",
        "Demand Growth 20%",
        "Reduced Fleet",
        "Tight Route Limit",
        "Expanded Capacity"
    ]

    scenario_results = []

    for scenario_name in scenario_names:
        summary_row = run_single_scenario(
            scenario_name,
            depot,
            customers,
            vehicles,
            distance_matrix_df
        )

        scenario_results.append(summary_row)

    scenario_results_df = pd.DataFrame(scenario_results)

    output_path = "outputs/scenario_results.csv"
    scenario_results_df.to_csv(output_path, index=False)

    print("\n" + "=" * 60)
    print("Scenario Analysis Summary")
    print("=" * 60)
    print(scenario_results_df)

    print(f"\nScenario results saved to: {output_path}")
    print("Scenario-specific route files saved inside: outputs/scenarios/")


if __name__ == "__main__":
    main()