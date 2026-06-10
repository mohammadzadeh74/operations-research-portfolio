import os
import sys
import shutil
import pandas as pd


# Allow this file to import from the src folder when run from project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from generate_data import generate_aircraft_schedule, generate_crews, generate_travel_times, save_datasets
from solve_model import solve_deicing_schedule


def run_single_scenario(
    scenario_name,
    num_aircraft,
    num_crews,
    weather_severity,
    departure_buffer_min,
    buffer_violation_cost_factor,
    seed,
    base_output_folder="outputs/scenarios"
):
    """
    Generate data, solve the de-icing scheduling model, and summarize results
    for one scenario.
    """

    scenario_folder_name = scenario_name.lower().replace(" ", "_")
    scenario_data_folder = os.path.join(base_output_folder, scenario_folder_name, "data")
    scenario_output_folder = os.path.join(base_output_folder, scenario_folder_name, "outputs")

    os.makedirs(scenario_data_folder, exist_ok=True)
    os.makedirs(scenario_output_folder, exist_ok=True)

    # Generate scenario-specific data
    aircraft_df = generate_aircraft_schedule(
        num_aircraft=num_aircraft,
        weather_severity=weather_severity,
        seed=seed
    )

    crews_df = generate_crews(
        num_crews=num_crews
    )

    travel_df = generate_travel_times(
        seed=seed
    )

    aircraft_path, crews_path, travel_path = save_datasets(
        aircraft_df=aircraft_df,
        crews_df=crews_df,
        travel_df=travel_df,
        output_folder=scenario_data_folder
    )

    # Solve model for this scenario
    schedule_df, crew_summary_df, flight_risk_summary_df, status, objective_value = solve_deicing_schedule(
        aircraft_path=aircraft_path,
        crews_path=crews_path,
        travel_path=travel_path,
        output_folder=scenario_output_folder,
        departure_buffer_min=departure_buffer_min,
        buffer_violation_cost_factor=buffer_violation_cost_factor,
        solver_time_limit=60,
        solver_gap=0.01
    )

    if schedule_df is None:
        return {
            "scenario": scenario_name,
            "solver_status": status,
            "objective_value": objective_value,
            "num_aircraft": num_aircraft,
            "num_crews": num_crews,
            "weather_severity": weather_severity,
            "departure_buffer_min": departure_buffer_min,
            "on_time_flights": None,
            "at_risk_flights": None,
            "delayed_flights": None,
            "total_delay_min": None,
            "total_buffer_violation_min": None,
            "total_overtime_min": None,
            "average_crew_utilization_percent": None
        }

    # Scenario-level metrics
    on_time_flights = (schedule_df["service_status"] == "On Time").sum()
    at_risk_flights = (schedule_df["service_status"] == "At Risk").sum()
    delayed_flights = (schedule_df["service_status"] == "Delayed").sum()

    total_delay = schedule_df["delay_min"].sum()
    total_buffer_violation = schedule_df["buffer_violation_min"].sum()
    total_weighted_delay_cost = schedule_df["weighted_delay_cost"].sum()
    total_weighted_buffer_cost = schedule_df["weighted_buffer_violation_cost"].sum()

    total_overtime = crew_summary_df["overtime_min"].sum()
    total_overtime_cost = crew_summary_df["overtime_cost"].sum()
    avg_utilization = crew_summary_df["utilization_percent"].mean()

    return {
        "scenario": scenario_name,
        "solver_status": status,
        "objective_value": round(objective_value, 2),
        "num_aircraft": num_aircraft,
        "num_crews": num_crews,
        "weather_severity": weather_severity,
        "departure_buffer_min": departure_buffer_min,
        "buffer_violation_cost_factor": buffer_violation_cost_factor,
        "on_time_flights": int(on_time_flights),
        "at_risk_flights": int(at_risk_flights),
        "delayed_flights": int(delayed_flights),
        "total_delay_min": round(total_delay, 2),
        "total_buffer_violation_min": round(total_buffer_violation, 2),
        "total_weighted_delay_cost": round(total_weighted_delay_cost, 2),
        "total_weighted_buffer_cost": round(total_weighted_buffer_cost, 2),
        "total_overtime_min": round(total_overtime, 2),
        "total_overtime_cost": round(total_overtime_cost, 2),
        "average_crew_utilization_percent": round(avg_utilization, 2),
        "scenario_output_folder": scenario_output_folder
    }


def run_scenario_analysis():
    """
    Run multiple aviation winter operations scenarios and compare outcomes.
    """

    scenarios = [
        {
            "scenario_name": "Base Case",
            "num_aircraft": 12,
            "num_crews": 3,
            "weather_severity": "moderate",
            "departure_buffer_min": 10,
            "buffer_violation_cost_factor": 0.25,
            "seed": 42
        },
        {
            "scenario_name": "Heavy Snow",
            "num_aircraft": 12,
            "num_crews": 3,
            "weather_severity": "heavy",
            "departure_buffer_min": 10,
            "buffer_violation_cost_factor": 0.25,
            "seed": 42
        },
        {
            "scenario_name": "Reduced Crew Availability",
            "num_aircraft": 12,
            "num_crews": 2,
            "weather_severity": "moderate",
            "departure_buffer_min": 10,
            "buffer_violation_cost_factor": 0.25,
            "seed": 42
        },
        {
            "scenario_name": "High Flight Volume",
            "num_aircraft": 16,
            "num_crews": 3,
            "weather_severity": "moderate",
            "departure_buffer_min": 10,
            "buffer_violation_cost_factor": 0.25,
            "seed": 42
        },
        {
            "scenario_name": "Tight Departure Buffer",
            "num_aircraft": 12,
            "num_crews": 3,
            "weather_severity": "moderate",
            "departure_buffer_min": 20,
            "buffer_violation_cost_factor": 0.25,
            "seed": 42
        }
    ]

    results = []

    print("\nRunning scenario analysis...\n")

    for scenario in scenarios:
        print("=" * 80)
        print(f"Running scenario: {scenario['scenario_name']}")
        print("=" * 80)

        result = run_single_scenario(**scenario)
        results.append(result)

    comparison_df = pd.DataFrame(results)

    os.makedirs("outputs", exist_ok=True)

    comparison_path = "outputs/scenario_comparison.csv"
    comparison_df.to_csv(comparison_path, index=False)

    print("\nScenario analysis complete.")
    print(f"Scenario comparison saved to: {comparison_path}")

    print("\nScenario comparison:")
    print(comparison_df)

    return comparison_df


if __name__ == "__main__":
    run_scenario_analysis()