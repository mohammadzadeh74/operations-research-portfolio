import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------------
# Synthetic Data Generator
# Project 4: Airline Revenue Management
# ---------------------------------------------------------

np.random.seed(42)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------
# 1. Flights Data
# ---------------------------------------------------------

flights = pd.DataFrame({
    "flight_id": [f"FL{i:03d}" for i in range(1, 11)],
    "flight_number": [f"AA{100+i}" for i in range(1, 11)],
    "origin": ["BOS", "BOS", "ORD", "ATL", "DFW", "JFK", "LAX", "DEN", "SEA", "MIA"],
    "destination": ["ORD", "JFK", "LAX", "MIA", "SEA", "SFO", "JFK", "ATL", "DFW", "BOS"],
    "departure_date": pd.date_range(start="2026-07-01", periods=10, freq="D"),
    "aircraft_type": [
        "A320", "B737", "A321", "A320", "B737",
        "A321", "B757", "A320", "B737", "A321"
    ],
    "seat_capacity": [150, 160, 190, 150, 160, 190, 200, 150, 160, 190],
    "route_type": [
        "Business", "Business", "Leisure", "Leisure", "Mixed",
        "Business", "Business", "Mixed", "Leisure", "Leisure"
    ],
    "day_of_week": [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"
    ]
})

flights.to_csv(DATA_DIR / "flights.csv", index=False)

# ---------------------------------------------------------
# 2. Fare Classes Data
# ---------------------------------------------------------

fare_classes = pd.DataFrame({
    "fare_class": ["Basic", "Main", "Comfort", "First"],
    "class_rank": [1, 2, 3, 4],
    "description": [
        "Lowest fare with restrictions",
        "Standard economy fare",
        "Extra legroom or premium economy",
        "Highest fare cabin"
    ],
    "base_price": [120, 220, 380, 750]
})

fare_classes.to_csv(DATA_DIR / "fare_classes.csv", index=False)

# ---------------------------------------------------------
# 3. Demand Forecasts Data
# ---------------------------------------------------------

rows = []

for _, flight in flights.iterrows():
    capacity = flight["seat_capacity"]
    route_type = flight["route_type"]

    for _, fare in fare_classes.iterrows():
        fare_class = fare["fare_class"]
        base_price = fare["base_price"]

        # Demand assumptions by route type and fare class
        if route_type == "Business":
            demand_multiplier = {
                "Basic": 0.35,
                "Main": 0.45,
                "Comfort": 0.25,
                "First": 0.18
            }
        elif route_type == "Leisure":
            demand_multiplier = {
                "Basic": 0.65,
                "Main": 0.35,
                "Comfort": 0.12,
                "First": 0.06
            }
        else:
            demand_multiplier = {
                "Basic": 0.50,
                "Main": 0.40,
                "Comfort": 0.18,
                "First": 0.10
            }

        forecasted_demand = int(capacity * demand_multiplier[fare_class] * np.random.uniform(0.85, 1.15))
        demand_std = max(3, int(forecasted_demand * 0.20))

        rows.append({
            "flight_id": flight["flight_id"],
            "fare_class": fare_class,
            "fare_price": int(base_price * np.random.uniform(0.90, 1.15)),
            "forecasted_demand": forecasted_demand,
            "demand_std": demand_std,
            "cancellation_rate": round(np.random.uniform(0.02, 0.08), 3),
            "no_show_rate": round(np.random.uniform(0.01, 0.05), 3)
        })

demand_forecasts = pd.DataFrame(rows)
demand_forecasts.to_csv(DATA_DIR / "demand_forecasts.csv", index=False)

# ---------------------------------------------------------
# 4. Booking Scenarios Data
# ---------------------------------------------------------

booking_scenarios = pd.DataFrame({
    "scenario_id": [
        "BASE",
        "HIGH_DEMAND",
        "LOW_DEMAND",
        "BUSINESS_HEAVY",
        "LEISURE_HEAVY",
        "PRICE_PRESSURE"
    ],
    "scenario_name": [
        "Base Demand",
        "High Demand",
        "Low Demand",
        "Business-Heavy Route",
        "Leisure-Heavy Route",
        "Competitor Price Pressure"
    ],
    "demand_multiplier": [1.00, 1.25, 0.75, 1.10, 1.15, 0.95],
    "price_multiplier": [1.00, 1.05, 0.95, 1.10, 0.90, 0.85],
    "uncertainty_multiplier": [1.00, 1.15, 0.90, 1.10, 1.05, 1.20],
    "description": [
        "Normal forecasted demand and fare prices.",
        "Higher-than-normal passenger demand.",
        "Lower-than-normal passenger demand.",
        "More demand from higher-fare business travelers.",
        "More price-sensitive leisure demand.",
        "Lower prices due to competitor pressure."
    ]
})

booking_scenarios.to_csv(DATA_DIR / "booking_scenarios.csv", index=False)

print("Synthetic data created successfully.")
print(f"Files saved in: {DATA_DIR}")