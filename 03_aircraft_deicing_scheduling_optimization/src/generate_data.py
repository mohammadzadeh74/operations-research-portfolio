import os
import pandas as pd
import numpy as np


def generate_aircraft_schedule(num_aircraft=12, weather_severity="moderate", seed=42):
    """
    Generate a synthetic winter flight schedule for aircraft snow-removal/de-icing.

    Times are represented as minutes from the start of the day.
    Example:
        420 = 7:00 AM
        480 = 8:00 AM
        720 = 12:00 PM
    """

    np.random.seed(seed)

    aircraft_types = ["regional", "narrow_body", "wide_body"]
    gates = [f"G{i}" for i in range(1, 9)]

    weather_multiplier = {
        "light": 1.0,
        "moderate": 1.3,
        "heavy": 1.7
    }

    base_service_time = {
        "regional": 25,
        "narrow_body": 40,
        "wide_body": 60
    }

    if weather_severity not in weather_multiplier:
        raise ValueError(
            "weather_severity must be one of: light, moderate, heavy"
        )

    aircraft_data = []

    for i in range(num_aircraft):
        aircraft_id = f"A{i + 1:03d}"
        flight_number = f"DL{1000 + i}"

        aircraft_type = np.random.choice(
            aircraft_types,
            p=[0.25, 0.55, 0.20]
        )

        gate = np.random.choice(gates)

        # Flights depart between 8:00 AM and 12:00 PM
        scheduled_departure = np.random.randint(480, 720)

        # Aircraft becomes ready 45 to 120 minutes before departure
        ready_time = scheduled_departure - np.random.randint(45, 120)

        service_time = int(
            base_service_time[aircraft_type]
            * weather_multiplier[weather_severity]
            * np.random.uniform(0.90, 1.15)
        )

        passenger_load = {
            "regional": np.random.randint(45, 80),
            "narrow_body": np.random.randint(120, 190),
            "wide_body": np.random.randint(220, 330)
        }[aircraft_type]

        priority_score = np.random.randint(1, 6)

        # Delay penalty combines passenger load and operational priority.
        delay_penalty_per_min = round(
            2.0 + 0.03 * passenger_load + 1.5 * priority_score,
            2
        )

        aircraft_data.append({
            "aircraft_id": aircraft_id,
            "flight_number": flight_number,
            "scheduled_departure_min": scheduled_departure,
            "ready_time_min": ready_time,
            "aircraft_type": aircraft_type,
            "service_time_min": service_time,
            "gate": gate,
            "passenger_load": passenger_load,
            "priority_score": priority_score,
            "delay_penalty_per_min": delay_penalty_per_min,
            "weather_severity": weather_severity
        })

    aircraft_df = pd.DataFrame(aircraft_data)

    aircraft_df = aircraft_df.sort_values(
        by="scheduled_departure_min"
    ).reset_index(drop=True)

    return aircraft_df


def generate_crews(num_crews=3):
    """
    Generate synthetic de-icing/snow-removal crew availability.
    """

    crew_data = []

    for k in range(num_crews):
        crew_data.append({
            "crew_id": f"C{k + 1}",
            "shift_start_min": 420,       # 7:00 AM
            "shift_end_min": 720,         # 12:00 PM
            "overtime_cost_per_min": 4.0,
            "home_pad": "PAD1"
        })

    return pd.DataFrame(crew_data)


def generate_travel_times(gates=None, seed=42):
    """
    Generate synthetic travel/setup times between gates and pad locations.
    """

    np.random.seed(seed)

    if gates is None:
        gates = [f"G{i}" for i in range(1, 9)] + ["PAD1"]

    travel_data = []

    for from_location in gates:
        for to_location in gates:
            if from_location == to_location:
                travel_time = 0
            else:
                travel_time = np.random.randint(3, 12)

            travel_data.append({
                "from_location": from_location,
                "to_location": to_location,
                "travel_time_min": travel_time
            })

    return pd.DataFrame(travel_data)


def save_datasets(aircraft_df, crews_df, travel_df, output_folder="data"):
    """
    Save generated datasets directly inside the data folder.
    """

    os.makedirs(output_folder, exist_ok=True)

    aircraft_path = os.path.join(output_folder, "aircraft_schedule.csv")
    crews_path = os.path.join(output_folder, "crews.csv")
    travel_path = os.path.join(output_folder, "travel_times.csv")

    aircraft_df.to_csv(aircraft_path, index=False)
    crews_df.to_csv(crews_path, index=False)
    travel_df.to_csv(travel_path, index=False)

    return aircraft_path, crews_path, travel_path


if __name__ == "__main__":
    aircraft_df = generate_aircraft_schedule(
        num_aircraft=12,
        weather_severity="moderate",
        seed=42
    )

    crews_df = generate_crews(
        num_crews=3
    )

    travel_df = generate_travel_times(
        seed=42
    )

    aircraft_path, crews_path, travel_path = save_datasets(
        aircraft_df=aircraft_df,
        crews_df=crews_df,
        travel_df=travel_df,
        output_folder="data"
    )

    print("Synthetic data created successfully.")
    print("\nFiles saved to:")
    print(f"- {aircraft_path}")
    print(f"- {crews_path}")
    print(f"- {travel_path}")

    print("\nAircraft schedule preview:")
    print(aircraft_df.head())

    print("\nCrew schedule preview:")
    print(crews_df.head())

    print("\nTravel time preview:")
    print(travel_df.head())