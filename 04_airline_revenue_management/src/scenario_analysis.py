import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)


def load_outputs():
    """Load optimization and protection-policy output files."""

    scenario_results = pd.read_csv(OUTPUT_DIR / "scenario_results.csv")
    protection_summary = pd.read_csv(OUTPUT_DIR / "protection_policy_summary.csv")
    protection_results = pd.read_csv(OUTPUT_DIR / "protection_policy_results.csv")
    protection_levels = pd.read_csv(OUTPUT_DIR / "protection_levels.csv")

    return scenario_results, protection_summary, protection_results, protection_levels


def create_combined_scenario_summary():
    """
    Combine baseline, deterministic optimization, and protection-policy results.
    """

    scenario_results, protection_summary, _, _ = load_outputs()

    combined = scenario_results.merge(
        protection_summary[
            [
                "flight_id",
                "scenario_id",
                "protection_policy_expected_revenue",
                "total_expected_sales",
                "unused_capacity"
            ]
        ],
        on=["flight_id", "scenario_id"],
        how="left",
        suffixes=("", "_protection")
    )

    combined["protection_vs_baseline_revenue_lift"] = (
        combined["protection_policy_expected_revenue"]
        - combined["baseline_expected_revenue"]
    )

    combined["protection_vs_baseline_revenue_lift_pct"] = (
        combined["protection_vs_baseline_revenue_lift"]
        / combined["baseline_expected_revenue"]
        * 100
    ).round(2)

    combined["optimization_vs_baseline_revenue_lift_pct"] = (
        combined["revenue_lift_pct"]
    ).round(2)

    combined["protection_vs_optimization_difference"] = (
        combined["protection_policy_expected_revenue"]
        - combined["optimized_expected_revenue"]
    ).round(2)

    combined = combined[
        [
            "flight_id",
            "flight_number",
            "origin",
            "destination",
            "aircraft_type",
            "seat_capacity",
            "scenario_id",
            "scenario_name",
            "solver_status",
            "baseline_expected_revenue",
            "optimized_expected_revenue",
            "protection_policy_expected_revenue",
            "revenue_lift",
            "optimization_vs_baseline_revenue_lift_pct",
            "protection_vs_baseline_revenue_lift",
            "protection_vs_baseline_revenue_lift_pct",
            "protection_vs_optimization_difference",
            "total_allocated_seats",
            "total_expected_sales",
            "unused_capacity",
            "unused_capacity_protection"
        ]
    ]

    combined.to_csv(
        OUTPUT_DIR / "combined_scenario_summary.csv",
        index=False
    )

    return combined


def create_fare_class_summary():
    """
    Summarize expected sales, revenue, booking limits, and protected seats
    by fare class across all flights and scenarios.
    """

    _, _, protection_results, protection_levels = load_outputs()

    fare_summary = protection_results.merge(
        protection_levels[
            [
                "flight_id",
                "scenario_id",
                "fare_class",
                "protected_seats_for_higher_classes",
                "booking_limit"
            ]
        ],
        on=["flight_id", "scenario_id", "fare_class"],
        how="left",
        suffixes=("", "_level")
    )

    fare_summary_grouped = (
        fare_summary
        .groupby("fare_class", as_index=False)
        .agg(
            avg_fare_price=("fare_price", "mean"),
            avg_forecasted_demand=("forecasted_demand", "mean"),
            avg_expected_sales=("expected_sales", "mean"),
            avg_booking_limit=("booking_limit", "mean"),
            avg_protected_seats=("protected_seats_for_higher_classes", "mean"),
            total_expected_revenue=("expected_revenue", "sum")
        )
    )

    fare_summary_grouped["avg_fare_price"] = fare_summary_grouped["avg_fare_price"].round(2)
    fare_summary_grouped["avg_forecasted_demand"] = fare_summary_grouped["avg_forecasted_demand"].round(2)
    fare_summary_grouped["avg_expected_sales"] = fare_summary_grouped["avg_expected_sales"].round(2)
    fare_summary_grouped["avg_booking_limit"] = fare_summary_grouped["avg_booking_limit"].round(2)
    fare_summary_grouped["avg_protected_seats"] = fare_summary_grouped["avg_protected_seats"].round(2)
    fare_summary_grouped["total_expected_revenue"] = fare_summary_grouped["total_expected_revenue"].round(2)

    fare_summary_grouped.to_csv(
        OUTPUT_DIR / "fare_class_summary.csv",
        index=False
    )

    return fare_summary_grouped


if __name__ == "__main__":

    combined = create_combined_scenario_summary()
    fare_summary = create_fare_class_summary()

    print("Scenario analysis completed successfully.")
    print(f"Combined summary saved to: {OUTPUT_DIR / 'combined_scenario_summary.csv'}")
    print(f"Fare-class summary saved to: {OUTPUT_DIR / 'fare_class_summary.csv'}")

    print("\nCombined scenario summary sample:")
    print(combined.head())

    print("\nFare-class summary:")
    print(fare_summary)