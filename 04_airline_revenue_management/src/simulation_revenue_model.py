import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------
# Project 4: Airline Revenue Management
# Simulation-Based Revenue Model
# ---------------------------------------------------------
#
# Purpose:
# Evaluate airline fare-class protection policies under uncertain demand.
#
# This model compares:
#   1. Baseline policy:
#      Accept demand in a simple low-to-high fare order until seats are full.
#
#   2. Protection policy:
#      Use booking limits/protection levels to avoid selling too many
#      seats to lower-fare passengers when higher-fare demand may arrive.
#
# Outputs:
#   - simulated_revenue_results.csv
#   - simulated_policy_summary.csv
#
# ---------------------------------------------------------


np.random.seed(42)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)


def load_data():
    """Load input and protection-level output data."""

    flights = pd.read_csv(DATA_DIR / "flights.csv")
    fare_classes = pd.read_csv(DATA_DIR / "fare_classes.csv")
    demand_forecasts = pd.read_csv(DATA_DIR / "demand_forecasts.csv")
    booking_scenarios = pd.read_csv(DATA_DIR / "booking_scenarios.csv")

    protection_levels = pd.read_csv(OUTPUT_DIR / "protection_levels.csv")

    return flights, fare_classes, demand_forecasts, booking_scenarios, protection_levels


def prepare_flight_scenario_data(flight_id, scenario_id):
    """
    Prepare adjusted fare-class data for a selected flight and scenario.
    """

    flights, fare_classes, demand_forecasts, booking_scenarios, protection_levels = load_data()

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

    flight_protection = protection_levels[
        (protection_levels["flight_id"] == flight_id)
        & (protection_levels["scenario_id"] == scenario_id)
    ][
        [
            "fare_class",
            "protected_seats_for_higher_classes",
            "booking_limit"
        ]
    ]

    flight_demand = flight_demand.merge(
        flight_protection,
        on="fare_class",
        how="left"
    )

    flight_demand = flight_demand.sort_values("class_rank").reset_index(drop=True)

    return flight, scenario, flight_demand


def generate_random_demand(row):
    """
    Generate one random demand value for a fare class.

    We use a normal distribution around the forecasted demand.
    Negative demand is not allowed.
    """

    demand = np.random.normal(
        loc=row["adjusted_forecasted_demand"],
        scale=max(1, row["adjusted_demand_std"])
    )

    demand = max(0, round(demand))

    # Adjust demand for cancellations and no-shows.
    # This approximates effective realized demand.
    cancellation_rate = row["cancellation_rate"]
    no_show_rate = row["no_show_rate"]

    effective_demand = demand * (1 - cancellation_rate) * (1 - no_show_rate)

    return int(round(effective_demand))


def simulate_baseline_policy(flight_demand, capacity):
    """
    Baseline policy:
    Accept passengers in low-to-high fare-class order until capacity is filled.

    This mimics a weak policy where early low-fare demand may consume seats
    before higher-fare demand arrives.
    """

    seats_remaining = capacity
    total_revenue = 0
    total_sold = 0
    total_denied_demand = 0

    fare_class_results = []

    # Low fare to high fare
    demand_order = flight_demand.sort_values("class_rank", ascending=True)

    for _, row in demand_order.iterrows():

        fare_class = row["fare_class"]
        price = row["adjusted_fare_price"]
        realized_demand = generate_random_demand(row)

        accepted = min(realized_demand, seats_remaining)
        denied = max(0, realized_demand - accepted)

        seats_remaining -= accepted
        total_sold += accepted
        total_denied_demand += denied
        total_revenue += accepted * price

        fare_class_results.append({
            "fare_class": fare_class,
            "policy": "Baseline",
            "realized_demand": realized_demand,
            "accepted_bookings": accepted,
            "denied_demand": denied,
            "revenue": accepted * price
        })

    return total_revenue, total_sold, seats_remaining, total_denied_demand, fare_class_results


def simulate_protection_policy(flight_demand, capacity):
    """
    Protection policy:
    Use booking limits for lower fare classes and preserve capacity for higher fares.

    Demand is processed low-to-high to reflect booking timing:
    lower-fare passengers often arrive earlier, while higher-fare passengers
    may arrive later.
    """

    seats_remaining = capacity
    total_revenue = 0
    total_sold = 0
    total_denied_demand = 0

    fare_class_results = []

    # Low fare to high fare
    demand_order = flight_demand.sort_values("class_rank", ascending=True)

    for _, row in demand_order.iterrows():

        fare_class = row["fare_class"]
        price = row["adjusted_fare_price"]
        realized_demand = generate_random_demand(row)

        booking_limit = int(row["booking_limit"])

        # How many seats have already been sold?
        seats_sold_so_far = capacity - seats_remaining

        # Remaining allowed bookings for this class under its booking limit
        allowed_by_booking_limit = max(0, booking_limit - seats_sold_so_far)

        # Highest fare class should be allowed to use remaining seats.
        if row["class_rank"] == demand_order["class_rank"].max():
            allowed_by_booking_limit = seats_remaining

        accepted = min(
            realized_demand,
            seats_remaining,
            allowed_by_booking_limit
        )

        denied = max(0, realized_demand - accepted)

        seats_remaining -= accepted
        total_sold += accepted
        total_denied_demand += denied
        total_revenue += accepted * price

        fare_class_results.append({
            "fare_class": fare_class,
            "policy": "Protection",
            "realized_demand": realized_demand,
            "accepted_bookings": accepted,
            "denied_demand": denied,
            "revenue": accepted * price
        })

    return total_revenue, total_sold, seats_remaining, total_denied_demand, fare_class_results


def run_simulation_for_flight_scenario(
    flight_id,
    scenario_id,
    n_simulations=1000
):
    """
    Run Monte Carlo simulation for one flight and one scenario.
    """

    flight, scenario, flight_demand = prepare_flight_scenario_data(
        flight_id,
        scenario_id
    )

    capacity = int(flight["seat_capacity"])

    simulation_summary_rows = []
    fare_class_detail_rows = []

    for sim in range(1, n_simulations + 1):

        (
            baseline_revenue,
            baseline_sold,
            baseline_unused,
            baseline_denied,
            baseline_class_results
        ) = simulate_baseline_policy(flight_demand, capacity)

        (
            protection_revenue,
            protection_sold,
            protection_unused,
            protection_denied,
            protection_class_results
        ) = simulate_protection_policy(flight_demand, capacity)

        revenue_lift = protection_revenue - baseline_revenue

        if baseline_revenue > 0:
            revenue_lift_pct = (revenue_lift / baseline_revenue) * 100
        else:
            revenue_lift_pct = 0

        simulation_summary_rows.append({
            "flight_id": flight_id,
            "flight_number": flight["flight_number"],
            "origin": flight["origin"],
            "destination": flight["destination"],
            "route_type": flight["route_type"],
            "aircraft_type": flight["aircraft_type"],
            "seat_capacity": capacity,
            "scenario_id": scenario_id,
            "scenario_name": scenario["scenario_name"],
            "simulation_id": sim,
            "baseline_revenue": baseline_revenue,
            "protection_revenue": protection_revenue,
            "revenue_lift": revenue_lift,
            "revenue_lift_pct": revenue_lift_pct,
            "baseline_sold_seats": baseline_sold,
            "protection_sold_seats": protection_sold,
            "baseline_unused_seats": baseline_unused,
            "protection_unused_seats": protection_unused,
            "baseline_denied_demand": baseline_denied,
            "protection_denied_demand": protection_denied,
            "baseline_load_factor": baseline_sold / capacity,
            "protection_load_factor": protection_sold / capacity
        })

        for row in baseline_class_results + protection_class_results:
            row.update({
                "flight_id": flight_id,
                "scenario_id": scenario_id,
                "simulation_id": sim
            })
            fare_class_detail_rows.append(row)

    simulation_summary_df = pd.DataFrame(simulation_summary_rows)
    fare_class_detail_df = pd.DataFrame(fare_class_detail_rows)

    return simulation_summary_df, fare_class_detail_df


def run_all_simulations(n_simulations=1000):
    """
    Run simulation for all flights and all scenarios.
    """

    flights, _, _, booking_scenarios, _ = load_data()

    all_summary_rows = []
    all_detail_rows = []

    for flight_id in flights["flight_id"]:
        for scenario_id in booking_scenarios["scenario_id"]:

            summary_df, detail_df = run_simulation_for_flight_scenario(
                flight_id=flight_id,
                scenario_id=scenario_id,
                n_simulations=n_simulations
            )

            all_summary_rows.append(summary_df)
            all_detail_rows.append(detail_df)

    simulated_revenue_results = pd.concat(all_summary_rows, ignore_index=True)
    simulated_fare_class_results = pd.concat(all_detail_rows, ignore_index=True)

    simulated_revenue_results.to_csv(
        OUTPUT_DIR / "simulated_revenue_results.csv",
        index=False
    )

    simulated_fare_class_results.to_csv(
        OUTPUT_DIR / "simulated_fare_class_results.csv",
        index=False
    )

    policy_summary = (
        simulated_revenue_results
        .groupby(
            [
                "flight_id",
                "flight_number",
                "origin",
                "destination",
                "route_type",
                "aircraft_type",
                "seat_capacity",
                "scenario_id",
                "scenario_name"
            ],
            as_index=False
        )
        .agg(
            avg_baseline_revenue=("baseline_revenue", "mean"),
            avg_protection_revenue=("protection_revenue", "mean"),
            avg_revenue_lift=("revenue_lift", "mean"),
            avg_revenue_lift_pct=("revenue_lift_pct", "mean"),
            avg_baseline_sold_seats=("baseline_sold_seats", "mean"),
            avg_protection_sold_seats=("protection_sold_seats", "mean"),
            avg_baseline_unused_seats=("baseline_unused_seats", "mean"),
            avg_protection_unused_seats=("protection_unused_seats", "mean"),
            avg_baseline_denied_demand=("baseline_denied_demand", "mean"),
            avg_protection_denied_demand=("protection_denied_demand", "mean"),
            avg_baseline_load_factor=("baseline_load_factor", "mean"),
            avg_protection_load_factor=("protection_load_factor", "mean")
        )
    )

    rounded_columns = [
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
        "avg_protection_load_factor"
    ]

    for col in rounded_columns:
        policy_summary[col] = policy_summary[col].round(2)

    policy_summary.to_csv(
        OUTPUT_DIR / "simulated_policy_summary.csv",
        index=False
    )

    return simulated_revenue_results, simulated_fare_class_results, policy_summary


if __name__ == "__main__":

    simulated_results, fare_class_results, policy_summary = run_all_simulations(
        n_simulations=1000
    )

    print("Simulation-based revenue model completed successfully.")
    print(f"Simulation results saved to: {OUTPUT_DIR / 'simulated_revenue_results.csv'}")
    print(f"Fare-class simulation details saved to: {OUTPUT_DIR / 'simulated_fare_class_results.csv'}")
    print(f"Policy summary saved to: {OUTPUT_DIR / 'simulated_policy_summary.csv'}")

    print("\nPolicy summary sample:")
    print(policy_summary.head())

    print("\nOverall average results:")
    print({
        "avg_baseline_revenue": round(policy_summary["avg_baseline_revenue"].mean(), 2),
        "avg_protection_revenue": round(policy_summary["avg_protection_revenue"].mean(), 2),
        "avg_revenue_lift": round(policy_summary["avg_revenue_lift"].mean(), 2),
        "avg_revenue_lift_pct": round(policy_summary["avg_revenue_lift_pct"].mean(), 2),
        "avg_baseline_load_factor": round(policy_summary["avg_baseline_load_factor"].mean(), 2),
        "avg_protection_load_factor": round(policy_summary["avg_protection_load_factor"].mean(), 2)
    })