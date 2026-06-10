import pandas as pd
import numpy as np
from scipy.stats import norm
from pathlib import Path


# ---------------------------------------------------------
# Project 4: Airline Revenue Management
# Fare Class Protection Level Model
# ---------------------------------------------------------
#
# This model uses a simplified Expected Marginal Seat Revenue logic.
#
# Idea:
# Lower-fare classes should not be allowed to consume all seats if
# there is expected future demand from higher-fare passengers.
#
# The model calculates:
#   - seats protected for higher fare classes
#   - booking limits for lower fare classes
#   - expected revenue under the protection policy
#
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
    Prepare one flight's fare-class demand and price data
    under a selected scenario.
    """

    flights, fare_classes, demand_forecasts, booking_scenarios = load_data()

    flight = flights[flights["flight_id"] == flight_id].iloc[0]
    scenario = booking_scenarios[
        booking_scenarios["scenario_id"] == scenario_id
    ].iloc[0]

    flight_demand = demand_forecasts[
        demand_forecasts["flight_id"] == flight_id
    ].copy()

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

    # Rank from low fare to high fare:
    # Basic = 1, Main = 2, Comfort = 3, First = 4
    flight_demand = flight_demand.sort_values("class_rank").reset_index(drop=True)

    return flight, flight_demand, scenario


def calculate_protection_levels(flight_id, scenario_id="BASE"):
    """
    Calculate nested fare-class protection levels.

    For each fare class, we calculate how many seats should be protected
    for all higher fare classes.

    Example:
        booking_limit_for_Basic =
            capacity - protected seats for Main + Comfort + First

        booking_limit_for_Main =
            capacity - protected seats for Comfort + First

        booking_limit_for_Comfort =
            capacity - protected seats for First

        First has no booking limit from protection because it is highest fare.
    """

    flight, flight_demand, scenario = get_flight_data(flight_id, scenario_id)

    capacity = int(flight["seat_capacity"])

    rows = []

    for _, current_class in flight_demand.iterrows():

        fare_class = current_class["fare_class"]
        class_rank = current_class["class_rank"]
        current_price = current_class["adjusted_fare_price"]

        higher_classes = flight_demand[
            flight_demand["class_rank"] > class_rank
        ].copy()

        if higher_classes.empty:
            protected_seats = 0
            booking_limit = capacity
            protection_reason = "Highest fare class; no higher class to protect."
        else:
            # Aggregate higher-fare demand
            higher_mean_demand = higher_classes["adjusted_forecasted_demand"].sum()

            # Combine standard deviations assuming independent demand
            higher_std_demand = np.sqrt(
                np.sum(higher_classes["adjusted_demand_std"] ** 2)
            )

            # Weighted average higher fare
            weighted_higher_price = np.average(
                higher_classes["adjusted_fare_price"],
                weights=higher_classes["adjusted_forecasted_demand"]
            )

            # EMSR-style critical ratio
            # Protect seats when probability of selling to a higher fare
            # justifies rejecting a lower fare.
            critical_ratio = 1 - (current_price / weighted_higher_price)

            # Keep the ratio inside a stable range
            critical_ratio = max(0.01, min(0.99, critical_ratio))

            z_value = norm.ppf(critical_ratio)

            protected_seats = higher_mean_demand + z_value * higher_std_demand
            protected_seats = int(round(max(0, protected_seats)))

            protected_seats = min(protected_seats, capacity)

            booking_limit = max(0, capacity - protected_seats)

            protection_reason = (
                f"Protecting seats for higher fare classes: "
                f"{', '.join(higher_classes['fare_class'].tolist())}"
            )

        rows.append({
            "flight_id": flight_id,
            "scenario_id": scenario_id,
            "fare_class": fare_class,
            "class_rank": class_rank,
            "fare_price": current_price,
            "forecasted_demand": current_class["adjusted_forecasted_demand"],
            "demand_std": current_class["adjusted_demand_std"],
            "protected_seats_for_higher_classes": protected_seats,
            "booking_limit": booking_limit,
            "protection_reason": protection_reason
        })

    protection_df = pd.DataFrame(rows)

    return protection_df


def simulate_protection_policy(flight_id, scenario_id="BASE"):
    """
    Simulate expected sales and revenue using the protection limits.

    Sales rule:
        expected sales for each fare class =
        min(forecasted demand, booking limit remaining for that class)

    This is a simplified approximation for portfolio demonstration.
    """

    flight, flight_demand, scenario = get_flight_data(flight_id, scenario_id)
    protection_df = calculate_protection_levels(flight_id, scenario_id)

    capacity = int(flight["seat_capacity"])

    results = []

    seats_sold_total = 0

    # Sell from high fare to low fare to represent nested protection.
    simulation_df = protection_df.sort_values(
        "class_rank",
        ascending=False
    ).reset_index(drop=True)

    for _, row in simulation_df.iterrows():

        fare_class = row["fare_class"]
        fare_price = row["fare_price"]
        forecasted_demand = row["forecasted_demand"]

        remaining_capacity = capacity - seats_sold_total

        expected_sales = min(forecasted_demand, remaining_capacity)

        seats_sold_total += expected_sales

        expected_revenue = expected_sales * fare_price

        results.append({
            "flight_id": flight_id,
            "scenario_id": scenario_id,
            "fare_class": fare_class,
            "class_rank": row["class_rank"],
            "fare_price": fare_price,
            "forecasted_demand": forecasted_demand,
            "booking_limit": row["booking_limit"],
            "protected_seats_for_higher_classes": row[
                "protected_seats_for_higher_classes"
            ],
            "expected_sales": expected_sales,
            "expected_revenue": expected_revenue
        })

    results_df = pd.DataFrame(results)

    # Return in low-to-high fare order for readability
    results_df = results_df.sort_values("class_rank").reset_index(drop=True)

    summary = {
        "flight_id": flight_id,
        "flight_number": flight["flight_number"],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "aircraft_type": flight["aircraft_type"],
        "seat_capacity": capacity,
        "scenario_id": scenario_id,
        "scenario_name": scenario["scenario_name"],
        "total_expected_sales": results_df["expected_sales"].sum(),
        "unused_capacity": capacity - results_df["expected_sales"].sum(),
        "protection_policy_expected_revenue": results_df[
            "expected_revenue"
        ].sum()
    }

    summary_df = pd.DataFrame([summary])

    return protection_df, results_df, summary_df


def run_all_flights_all_scenarios():
    """
    Run protection-level model for every flight and every scenario.
    """

    flights, _, _, booking_scenarios = load_data()

    all_protection_rows = []
    all_sales_rows = []
    all_summary_rows = []

    for flight_id in flights["flight_id"]:
        for scenario_id in booking_scenarios["scenario_id"]:

            protection_df, results_df, summary_df = simulate_protection_policy(
                flight_id=flight_id,
                scenario_id=scenario_id
            )

            all_protection_rows.append(protection_df)
            all_sales_rows.append(results_df)
            all_summary_rows.append(summary_df)

    protection_all = pd.concat(all_protection_rows, ignore_index=True)
    sales_all = pd.concat(all_sales_rows, ignore_index=True)
    summary_all = pd.concat(all_summary_rows, ignore_index=True)

    protection_all.to_csv(
        OUTPUT_DIR / "protection_levels.csv",
        index=False
    )

    sales_all.to_csv(
        OUTPUT_DIR / "protection_policy_results.csv",
        index=False
    )

    summary_all.to_csv(
        OUTPUT_DIR / "protection_policy_summary.csv",
        index=False
    )

    return protection_all, sales_all, summary_all


if __name__ == "__main__":

    protection_levels, policy_results, policy_summary = run_all_flights_all_scenarios()

    print("Protection-level model completed successfully.")
    print(f"Protection levels saved to: {OUTPUT_DIR / 'protection_levels.csv'}")
    print(f"Policy results saved to: {OUTPUT_DIR / 'protection_policy_results.csv'}")
    print(f"Policy summary saved to: {OUTPUT_DIR / 'protection_policy_summary.csv'}")

    print("\nSample protection-level results:")
    print(protection_levels.head())

    print("\nSample policy summary:")
    print(policy_summary.head())