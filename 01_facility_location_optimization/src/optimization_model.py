"""
optimization_model.py

This script formulates and solves a facility location optimization model.

The model decides:
1. Which facilities to open
2. Which facility should serve each customer zone

Objective:
Minimize total cost = facility opening cost + transportation cost

Author: Mo Moha
Project: Facility Location Optimization
"""

import os
import pandas as pd
import pulp
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

def load_data():
    facilities = pd.read_csv(DATA_DIR / "candidate_facilities.csv")
    customers = pd.read_csv(DATA_DIR / "customer_zones.csv")
    transportation_costs = pd.read_csv(DATA_DIR / "transportation_costs.csv")
    return facilities, customers, transportation_costs


def build_and_solve_model(
    facilities,
    customers,
    transportation_costs,
    max_facilities=None,
    budget=None
):
    """
    Build and solve the facility location optimization model.

    Parameters
    ----------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    transportation_costs : pandas.DataFrame
        Customer-facility transportation cost data.

    max_facilities : int or None
        Optional limit on the number of facilities that can be opened.

    budget : float or None
        Optional limit on total facility opening cost.

    Returns
    -------
    model : pulp.LpProblem
        Solved optimization model.

    open_facility_vars : dict
        Binary decision variables for facility opening decisions.

    assignment_vars : dict
        Continuous decision variables for customer assignment amounts.
    """

    facility_ids = facilities["facility_id"].tolist()
    customer_ids = customers["customer_id"].tolist()

    demand = dict(zip(customers["customer_id"], customers["demand"]))
    capacity = dict(zip(facilities["facility_id"], facilities["capacity"]))
    opening_cost = dict(zip(facilities["facility_id"], facilities["opening_cost"]))

    transport_cost = {}
    service_allowed = {}

    for _, row in transportation_costs.iterrows():
        customer_id = row["customer_id"]
        facility_id = row["facility_id"]

        transport_cost[(customer_id, facility_id)] = row["cost_per_unit"]
        service_allowed[(customer_id, facility_id)] = row["within_service_radius"]

    model = pulp.LpProblem(
        name="Facility_Location_Optimization",
        sense=pulp.LpMinimize
    )

    open_facility_vars = pulp.LpVariable.dicts(
        "OpenFacility",
        facility_ids,
        lowBound=0,
        upBound=1,
        cat="Binary"
    )

    assignment_vars = pulp.LpVariable.dicts(
        "AssignDemand",
        [(i, j) for i in customer_ids for j in facility_ids],
        lowBound=0,
        cat="Continuous"
    )

    # Objective function:
    # Minimize facility opening cost + transportation cost
    model += (
        pulp.lpSum(opening_cost[j] * open_facility_vars[j] for j in facility_ids)
        +
        pulp.lpSum(
            transport_cost[(i, j)] * assignment_vars[(i, j)]
            for i in customer_ids
            for j in facility_ids
        )
    ), "Total_Cost"

    # Constraint 1:
    # Each customer's full demand must be satisfied.
    for i in customer_ids:
        model += (
            pulp.lpSum(assignment_vars[(i, j)] for j in facility_ids) == demand[i]
        ), f"Demand_Satisfaction_{i}"

    # Constraint 2:
    # Facility capacity cannot be exceeded.
    for j in facility_ids:
        model += (
            pulp.lpSum(assignment_vars[(i, j)] for i in customer_ids)
            <= capacity[j] * open_facility_vars[j]
        ), f"Capacity_Limit_{j}"

    # Constraint 3:
    # A customer can only be assigned to a facility within the service radius.
    for i in customer_ids:
        for j in facility_ids:
            model += (
                assignment_vars[(i, j)] <= demand[i] * service_allowed[(i, j)]
            ), f"Service_Radius_{i}_{j}"

    # Optional Constraint 4:
    # Limit the maximum number of facilities opened.
    if max_facilities is not None:
        model += (
            pulp.lpSum(open_facility_vars[j] for j in facility_ids) <= max_facilities
        ), "Maximum_Number_of_Facilities"

    # Optional Constraint 5:
    # Limit total facility opening cost.
    if budget is not None:
        model += (
            pulp.lpSum(opening_cost[j] * open_facility_vars[j] for j in facility_ids)
            <= budget
        ), "Facility_Opening_Budget"

    model.solve(pulp.PULP_CBC_CMD(msg=False))

    return model, open_facility_vars, assignment_vars


def extract_solution(
    model,
    facilities,
    customers,
    transportation_costs,
    open_facility_vars,
    assignment_vars
):
    """
    Extract selected facilities and customer assignments from the solved model.

    Returns
    -------
    selected_facilities : pandas.DataFrame
        Facilities selected by the optimization model.

    customer_assignments : pandas.DataFrame
        Customer-to-facility assignment results.

    summary : dict
        High-level model results.
    """

    facility_ids = facilities["facility_id"].tolist()
    customer_ids = customers["customer_id"].tolist()

    selected_facility_ids = []

    for j in facility_ids:
        if open_facility_vars[j].value() is not None and open_facility_vars[j].value() > 0.5:
            selected_facility_ids.append(j)

    selected_facilities = facilities[
        facilities["facility_id"].isin(selected_facility_ids)
    ].copy()

    assignment_records = []

    for i in customer_ids:
        for j in facility_ids:
            assigned_amount = assignment_vars[(i, j)].value()

            if assigned_amount is not None and assigned_amount > 0.001:
                assignment_records.append({
                    "customer_id": i,
                    "facility_id": j,
                    "assigned_demand": round(assigned_amount, 2)
                })

    customer_assignments = pd.DataFrame(assignment_records)

    customer_assignments = customer_assignments.merge(
        customers,
        on="customer_id",
        how="left"
    )

    customer_assignments = customer_assignments.merge(
        facilities,
        on="facility_id",
        how="left",
        suffixes=("_customer", "_facility")
    )

    customer_assignments = customer_assignments.merge(
        transportation_costs,
        on=["customer_id", "facility_id"],
        how="left"
    )

    customer_assignments["assignment_cost"] = (
        customer_assignments["assigned_demand"]
        * customer_assignments["cost_per_unit"]
    ).round(2)

    summary = {
        "solver_status": pulp.LpStatus[model.status],
        "total_cost": round(pulp.value(model.objective), 2),
        "number_of_selected_facilities": len(selected_facility_ids),
        "selected_facilities": selected_facility_ids
    }

    return selected_facilities, customer_assignments, summary


def save_solution(selected_facilities, customer_assignments):
    """
    Save model outputs to the outputs folder.
    """

    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    selected_facilities.to_csv("outputs/selected_facilities.csv", index=False)
    customer_assignments.to_csv("outputs/customer_assignments.csv", index=False)


def main():
    """
    Main function to run the facility location optimization model.
    """

    facilities, customers, transportation_costs = load_data()

    model, open_facility_vars, assignment_vars = build_and_solve_model(
        facilities=facilities,
        customers=customers,
        transportation_costs=transportation_costs,
        max_facilities=None,
        budget=None
    )

    selected_facilities, customer_assignments, summary = extract_solution(
        model=model,
        facilities=facilities,
        customers=customers,
        transportation_costs=transportation_costs,
        open_facility_vars=open_facility_vars,
        assignment_vars=assignment_vars
    )

    save_solution(selected_facilities, customer_assignments)

    print("Facility location optimization completed.")
    print("\nModel Summary:")
    print(f"Solver Status: {summary['solver_status']}")
    print(f"Total Cost: ${summary['total_cost']:,.2f}")
    print(f"Number of Selected Facilities: {summary['number_of_selected_facilities']}")
    print(f"Selected Facilities: {summary['selected_facilities']}")

    print("\nSelected Facilities:")
    print(selected_facilities)

    print("\nCustomer Assignments Preview:")
    print(customer_assignments.head())


if __name__ == "__main__":
    main()