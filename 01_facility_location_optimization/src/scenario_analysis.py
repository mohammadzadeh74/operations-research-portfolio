"""
scenario_analysis.py

This script runs multiple facility location optimization scenarios
and compares the results.

Scenarios include:
1. Base case
2. Maximum 3 facilities
3. Maximum 5 facilities
4. Low opening budget
5. High opening budget
6. Higher demand scenario

Author: Mo Moha
Project: Facility Location Optimization
"""

import os
import pandas as pd

from optimization_model import build_and_solve_model, extract_solution, load_data


def run_single_scenario(
    scenario_name,
    facilities,
    customers,
    transportation_costs,
    max_facilities=None,
    budget=None,
    demand_multiplier=1.0
):
    """
    Run one facility location optimization scenario.

    Parameters
    ----------
    scenario_name : str
        Name of the scenario.

    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    transportation_costs : pandas.DataFrame
        Transportation cost data.

    max_facilities : int or None
        Optional maximum number of facilities that can be opened.

    budget : float or None
        Optional maximum total facility opening budget.

    demand_multiplier : float
        Multiplier applied to customer demand.

    Returns
    -------
    dict
        Scenario result summary.
    """

    scenario_customers = customers.copy()
    scenario_customers["demand"] = (
        scenario_customers["demand"] * demand_multiplier
    ).round(0)

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

    total_demand = scenario_customers["demand"].sum()
    total_capacity_selected = selected_facilities["capacity"].sum()

    result = {
        "scenario_name": scenario_name,
        "solver_status": summary["solver_status"],
        "total_cost": summary["total_cost"],
        "number_of_selected_facilities": summary["number_of_selected_facilities"],
        "selected_facilities": ", ".join(summary["selected_facilities"]),
        "total_demand": total_demand,
        "selected_capacity": total_capacity_selected,
        "capacity_utilization": round(total_demand / total_capacity_selected, 3)
        if total_capacity_selected > 0 else None,
        "max_facilities": max_facilities,
        "budget": budget,
        "demand_multiplier": demand_multiplier
    }

    return result


def run_all_scenarios():
    """
    Run all predefined facility location scenarios.

    Returns
    -------
    pandas.DataFrame
        Scenario comparison table.
    """

    facilities, customers, transportation_costs = load_data()

    scenarios = [
        {
            "scenario_name": "Base Case",
            "max_facilities": None,
            "budget": None,
            "demand_multiplier": 1.0
        },
        {
            "scenario_name": "Max 3 Facilities",
            "max_facilities": 3,
            "budget": None,
            "demand_multiplier": 1.0
        },
        {
            "scenario_name": "Max 5 Facilities",
            "max_facilities": 5,
            "budget": None,
            "demand_multiplier": 1.0
        },
        {
            "scenario_name": "Low Budget",
            "max_facilities": None,
            "budget": 450000,
            "demand_multiplier": 1.0
        },
        {
            "scenario_name": "High Budget",
            "max_facilities": None,
            "budget": 700000,
            "demand_multiplier": 1.0
        },
        {
            "scenario_name": "Demand Growth 20%",
            "max_facilities": None,
            "budget": None,
            "demand_multiplier": 1.2
        }
    ]

    results = []

    for scenario in scenarios:
        result = run_single_scenario(
            scenario_name=scenario["scenario_name"],
            facilities=facilities,
            customers=customers,
            transportation_costs=transportation_costs,
            max_facilities=scenario["max_facilities"],
            budget=scenario["budget"],
            demand_multiplier=scenario["demand_multiplier"]
        )

        results.append(result)

    scenario_results = pd.DataFrame(results)

    return scenario_results


def save_scenario_results(scenario_results):
    """
    Save scenario results to the outputs folder.
    """

    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    scenario_results.to_csv("outputs/scenario_results.csv", index=False)


def main():
    """
    Main function to run and save scenario analysis.
    """

    scenario_results = run_all_scenarios()
    save_scenario_results(scenario_results)

    print("Scenario analysis completed.")
    print("\nScenario Results:")
    print(scenario_results)


if __name__ == "__main__":
    main()