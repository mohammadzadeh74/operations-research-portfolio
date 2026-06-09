import pandas as pd
import numpy as np
from math import sqrt
import os

np.random.seed(42)

# -----------------------------
# 1. Create depot data
# -----------------------------

depot = pd.DataFrame({
    "depot_id": ["D0"],
    "depot_name": ["Central Distribution Depot"],
    "x_coord": [50],
    "y_coord": [50]
})

# -----------------------------
# 2. Create customer data
# -----------------------------

num_customers = 25

zones = ["North", "South", "East", "West", "Central"]
priority_levels = ["Standard", "High", "Critical"]

customers = pd.DataFrame({
    "customer_id": [f"C{i}" for i in range(1, num_customers + 1)],
    "customer_name": [f"Retail Customer {i}" for i in range(1, num_customers + 1)],
    "zone": np.random.choice(zones, size=num_customers),
    "x_coord": np.random.randint(5, 96, size=num_customers),
    "y_coord": np.random.randint(5, 96, size=num_customers),
    "demand_units": np.random.randint(5, 26, size=num_customers),
    "priority_level": np.random.choice(priority_levels, size=num_customers, p=[0.65, 0.25, 0.10]),
    "service_time_min": np.random.randint(10, 31, size=num_customers)
})

# -----------------------------
# 3. Create vehicle data
# -----------------------------

vehicles = pd.DataFrame({
    "vehicle_id": ["V1", "V2", "V3", "V4", "V5"],
    "vehicle_type": ["Box Truck", "Box Truck", "Box Truck", "Van", "Van"],
    "capacity_units": [120, 120, 120, 80, 80],
    "fixed_cost": [130, 130, 130, 90, 90],
    "cost_per_mile": [2.40, 2.40, 2.40, 1.75, 1.75],
    "max_route_distance": [280, 280, 280, 180, 180]
})

# -----------------------------
# 4. Create distance matrix
# -----------------------------

locations = []

locations.append({
    "location_id": "D0",
    "location_type": "Depot",
    "x_coord": depot.loc[0, "x_coord"],
    "y_coord": depot.loc[0, "y_coord"]
})

for _, row in customers.iterrows():
    locations.append({
        "location_id": row["customer_id"],
        "location_type": "Customer",
        "x_coord": row["x_coord"],
        "y_coord": row["y_coord"]
    })

locations_df = pd.DataFrame(locations)

distance_records = []

for _, origin in locations_df.iterrows():
    for _, destination in locations_df.iterrows():
        dx = origin["x_coord"] - destination["x_coord"]
        dy = origin["y_coord"] - destination["y_coord"]

        # Euclidean distance with a 1.25 multiplier to mimic road distance
        distance = sqrt(dx**2 + dy**2) * 1.25

        distance_records.append({
            "from_id": origin["location_id"],
            "to_id": destination["location_id"],
            "distance_miles": round(distance, 2)
        })

distance_matrix = pd.DataFrame(distance_records)

# -----------------------------
# 5. Save files
# -----------------------------

os.makedirs("data", exist_ok=True)

depot.to_csv("data/depot.csv", index=False)
customers.to_csv("data/customers.csv", index=False)
vehicles.to_csv("data/vehicles.csv", index=False)
distance_matrix.to_csv("data/distance_matrix.csv", index=False)

print("Synthetic VRP dataset created successfully.")
print("Files saved inside the data/ folder.")
print(f"Number of customers: {len(customers)}")
print(f"Total demand: {customers['demand_units'].sum()} units")
print(f"Total vehicle capacity: {vehicles['capacity_units'].sum()} units")