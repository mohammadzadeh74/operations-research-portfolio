import pandas as pd
import pulp
from pathlib import Path


# ---------------------------------------------------------
# Project 4: Airline Revenue Management
# Fare Class Seat Inventory Optimization
# ---------------------------------------------------------


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)


def load_data():
    """Load all input datasets."""

    flights = pd.read_csv(DATA_DIR / "flights.csv")
    fare_classes = pd.read_csv(DATA_DIR / "fare_classes.csv")
    demand_forecasts = pd.read_csv(DATA_DIR / "demand_forecasts.csv")
    booking_scenarios = pd.read_csv(DATA_DIR / "booking_scenarios.csv")

    return flights, fare_classes, demand_forecasts, booking_scenarios


def get_flight_data(flight_id, scenario_id="BASE"):
    """
    Prepare one flight's data under a selected scenario.
    """

    flights, fare_classes, demand_forecasts, booking_scenarios = load_data()

    flight = flights[flights["flight_id"] == flight_id].iloc[0]
    scenario = booking_scenarios[booking_scenarios["scenario_id"] == scenario_id].iloc[0]

    flight_demand = demand_forecasts[demand_forecasts["flight_id"] == flight_id].copy()

    flight_demand["adjusted_fare_price"] = (
        flight_demand["fare_price"] * scenario["price_multiplier"]
    ).round(2)

    flight_demand["adjusted_forecasted_demand"] = (
        flight_demand["forecasted_demand"] * scenario["demand_multiplier"]
    ).round().astype(int)

    flight_demand["adjusted_demand_std"] = (
        flight_demand["demand_std"] * scenario["uncertainty_multiplier"]
    ).round().astype(int)

    flight_demand = flight_demand.merge(
        fare_classes[["fare_class", "class_rank", "description"]],
        on="fare_class",
        how="left"
    )

    return flight, flight_demand, scenario


def optimize_seat_allocation(flight_id, scenario_id="BASE"):
    """
    Deterministic seat allocation model.

    Decision:
        x[c] = seats allocated to fare class c

    Objective:
        Maximize expected revenue

    Constraints:
        Total allocated seats <= aircraft capacity
        Allocation for each fare class <= adjusted forecasted demand
    """

    flight, flight_demand, scenario = get_flight_data(flight_id, scenario_id)

    capacity = int(flight["seat_capacity"])
    fare_classes = flight_demand["fare_class"].tolist()

    prices = dict(zip(
        flight_demand["fare_class"],
        flight_demand["adjusted_fare_price"]
    ))

    demands = dict(zip(
        flight_demand["fare_class"],
        flight_demand["adjusted_forecasted_demand"]
    ))

    # -----------------------------------------------------
    # Build optimization model
    # -----------------------------------------------------

    model = pulp.LpProblem(
        name=f"Seat_Inventory_Optimization_{flight_id}_{scenario_id}",
        sense=pulp.LpMaximize
    )

    # Decision variables
    x = pulp.LpVariable.dicts(
        "allocated_seats",
        fare_classes,
        lowBound=0,
        cat="Integer"
    )

    # Objective function
    model += pulp.lpSum(prices[c] * x[c] for c in fare_classes), "Total_Expected_Revenue"

    # Aircraft capacity constraint
    model += (
        pulp.lpSum(x[c] for c in fare_classes) <= capacity,
        "Aircraft_Seat_Capacity"
    )

    # Demand upper-bound constraints
    for c in fare_classes:
        model += (
            x[c] <= demands[c],
            f"Demand_Limit_{c}"
        )

    # Solve
    model.solve(pulp.PULP_CBC_CMD(msg=False))

    # -----------------------------------------------------
    # Store results
    # -----------------------------------------------------

    results = []

    for c in fare_classes:
        allocated_seats = int(x[c].value())
        revenue = allocated_seats * prices[c]

        results.append({
            "flight_id": flight_id,
            "scenario_id": scenario_id,
            "fare_class": c,
            "fare_price": prices[c],
            "forecasted_demand": demands[c],
            "allocated_seats": allocated_seats,
            "expected_revenue": revenue
        })

    results_df = pd.DataFrame(results)

    total_revenue = results_df["expected_revenue"].sum()
    total_allocated = results_df["allocated_seats"].sum()
    unused_capacity = capacity - total_allocated

    summary = {
        "flight_id": flight_id,
        "flight_number": flight["flight_number"],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "aircraft_type": flight["aircraft_type"],
        "seat_capacity": capacity,
        "scenario_id": scenario_id,
        "scenario_name": scenario["scenario_name"],
        "solver_status": pulp.LpStatus[model.status],
        "total_allocated_seats": total_allocated,
        "unused_capacity": unused_capacity,
        "optimized_expected_revenue": total_revenue
    }

    summary_df = pd.DataFrame([summary])

    return results_df, summary_df


def baseline_allocation(flight_id, scenario_id="BASE"):
    """
    Simple baseline policy:
    Allocate seats proportional to forecasted demand until capacity is reached.
    """

    flight, flight_demand, scenario = get_flight_data(flight_id, scenario_id)

    capacity = int(flight["seat_capacity"])

    total_demand = flight_demand["adjusted_forecasted_demand"].sum()

    baseline_rows = []

    for _, row in flight_demand.iterrows():
        fare_class = row["fare_class"]
        price = row["adjusted_fare_price"]
        demand = row["adjusted_forecasted_demand"]

        if total_demand > 0:
            allocated = round((demand / total_demand) * capacity)
        else:
            allocated = 0

        allocated = min(allocated, demand)

        baseline_rows.append({
            "flight_id": flight_id,
            "scenario_id": scenario_id,
            "fare_class": fare_class,
            "fare_price": price,
            "forecasted_demand": demand,
            "baseline_allocated_seats": allocated,
            "baseline_expected_revenue": allocated * price
        })

    baseline_df = pd.DataFrame(baseline_rows)

    # If rounding caused over-allocation, remove seats from lowest fare classes first
    while baseline_df["baseline_allocated_seats"].sum() > capacity:
        idx = baseline_df.sort_values("fare_price").index[0]
        baseline_df.loc[idx, "baseline_allocated_seats"] -= 1
        baseline_df.loc[idx, "baseline_expected_revenue"] = (
            baseline_df.loc[idx, "baseline_allocated_seats"]
            * baseline_df.loc[idx, "fare_price"]
        )

    return baseline_df


def compare_optimized_vs_baseline(flight_id, scenario_id="BASE"):
    """
    Compare optimized allocation with baseline allocation.
    """

    optimized_df, summary_df = optimize_seat_allocation(flight_id, scenario_id)
    baseline_df = baseline_allocation(flight_id, scenario_id)

    comparison = optimized_df.merge(
        baseline_df[
            [
                "fare_class",
                "baseline_allocated_seats",
                "baseline_expected_revenue"
            ]
        ],
        on="fare_class",
        how="left"
    )

    optimized_revenue = comparison["expected_revenue"].sum()
    baseline_revenue = comparison["baseline_expected_revenue"].sum()
    revenue_lift = optimized_revenue - baseline_revenue

    if baseline_revenue > 0:
        revenue_lift_pct = (revenue_lift / baseline_revenue) * 100
    else:
        revenue_lift_pct = 0

    comparison_summary = summary_df.copy()
    comparison_summary["baseline_expected_revenue"] = baseline_revenue
    comparison_summary["revenue_lift"] = revenue_lift
    comparison_summary["revenue_lift_pct"] = revenue_lift_pct

    return comparison, comparison_summary


def run_all_flights_all_scenarios():
    """
    Run optimization for every flight and every scenario.
    """

    flights, _, _, booking_scenarios = load_data()

    all_results = []
    all_summaries = []

    for flight_id in flights["flight_id"]:
        for scenario_id in booking_scenarios["scenario_id"]:
            comparison, comparison_summary = compare_optimized_vs_baseline(
                flight_id=flight_id,
                scenario_id=scenario_id
            )

            all_results.append(comparison)
            all_summaries.append(comparison_summary)

    all_results_df = pd.concat(all_results, ignore_index=True)
    all_summaries_df = pd.concat(all_summaries, ignore_index=True)

    all_results_df.to_csv(
        OUTPUT_DIR / "optimized_seat_allocations.csv",
        index=False
    )

    all_summaries_df.to_csv(
        OUTPUT_DIR / "scenario_results.csv",
        index=False
    )

    return all_results_df, all_summaries_df


if __name__ == "__main__":

    results, summaries = run_all_flights_all_scenarios()

    print("Optimization completed successfully.")
    print(f"Detailed results saved to: {OUTPUT_DIR / 'optimized_seat_allocations.csv'}")
    print(f"Scenario summary saved to: {OUTPUT_DIR / 'scenario_results.csv'}")

    print("\nSample scenario results:")
    print(summaries.head())