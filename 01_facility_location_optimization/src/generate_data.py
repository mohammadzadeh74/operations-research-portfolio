"""
generate_data.py

This script generates synthetic data for a facility location optimization project.

The generated data includes:
1. Candidate facility locations
2. Customer demand zones
3. Transportation cost between each customer and facility

Author: Mo Moha
Project: Facility Location Optimization
"""

import os
import numpy as np
import pandas as pd


def create_project_folders():
    """
    Create required project folders if they do not already exist.
    """

    folders = ["data", "outputs"]

    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)


def generate_candidate_facilities(num_facilities=8, random_seed=42):
    """
    Generate synthetic candidate facility locations.

    Parameters
    ----------
    num_facilities : int
        Number of possible facility locations.

    random_seed : int
        Random seed for reproducibility.

    Returns
    -------
    pandas.DataFrame
        Dataset of candidate facilities.
    """

    np.random.seed(random_seed)

    facilities = pd.DataFrame({
        "facility_id": [f"F{i+1}" for i in range(num_facilities)],
        "facility_name": [f"Facility {i+1}" for i in range(num_facilities)],
        "x_coord": np.random.uniform(0, 100, num_facilities).round(2),
        "y_coord": np.random.uniform(0, 100, num_facilities).round(2),
        "opening_cost": np.random.randint(80000, 180000, num_facilities),
        "capacity": np.random.randint(400, 1000, num_facilities)
    })

    return facilities


def generate_customer_zones(num_customers=25, random_seed=42):
    """
    Generate synthetic customer demand zones.

    Parameters
    ----------
    num_customers : int
        Number of customer zones.

    random_seed : int
        Random seed for reproducibility.

    Returns
    -------
    pandas.DataFrame
        Dataset of customer zones.
    """

    np.random.seed(random_seed + 1)

    customers = pd.DataFrame({
        "customer_id": [f"C{i+1}" for i in range(num_customers)],
        "customer_name": [f"Customer Zone {i+1}" for i in range(num_customers)],
        "x_coord": np.random.uniform(0, 100, num_customers).round(2),
        "y_coord": np.random.uniform(0, 100, num_customers).round(2),
        "demand": np.random.randint(50, 200, num_customers)
    })

    return customers


def calculate_distance(x1, y1, x2, y2):
    """
    Calculate Euclidean distance between two points.

    Parameters
    ----------
    x1, y1 : float
        Coordinates of the first point.

    x2, y2 : float
        Coordinates of the second point.

    Returns
    -------
    float
        Distance between the two points.
    """

    distance = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    return round(distance, 2)


def generate_transportation_costs(customers, facilities, cost_per_distance_unit=12, service_radius=70):
    """
    Generate transportation cost between each customer and each candidate facility.

    Parameters
    ----------
    customers : pandas.DataFrame
        Customer zone dataset.

    facilities : pandas.DataFrame
        Candidate facility dataset.

    cost_per_distance_unit : float
        Transportation cost per unit of demand per distance unit.

    service_radius : float
        Maximum distance allowed between a customer and a facility.

    Returns
    -------
    pandas.DataFrame
        Dataset of customer-facility transportation costs.
    """

    records = []

    for _, customer in customers.iterrows():
        for _, facility in facilities.iterrows():

            distance = calculate_distance(
                customer["x_coord"],
                customer["y_coord"],
                facility["x_coord"],
                facility["y_coord"]
            )

            transportation_cost = distance * cost_per_distance_unit

            within_service_radius = 1 if distance <= service_radius else 0

            records.append({
                "customer_id": customer["customer_id"],
                "facility_id": facility["facility_id"],
                "distance": distance,
                "cost_per_unit": round(transportation_cost, 2),
                "within_service_radius": within_service_radius
            })

    transportation_costs = pd.DataFrame(records)

    return transportation_costs


def save_datasets(facilities, customers, transportation_costs):
    """
    Save generated datasets as CSV files.
    """

    facilities.to_csv("data/candidate_facilities.csv", index=False)
    customers.to_csv("data/customer_zones.csv", index=False)
    transportation_costs.to_csv("data/transportation_costs.csv", index=False)


def main():
    """
    Main function to generate and save all datasets.
    """

    create_project_folders()

    facilities = generate_candidate_facilities(num_facilities=8)
    customers = generate_customer_zones(num_customers=25)

    transportation_costs = generate_transportation_costs(
        customers=customers,
        facilities=facilities,
        cost_per_distance_unit=12,
        service_radius=70
    )

    save_datasets(facilities, customers, transportation_costs)

    print("Synthetic datasets generated successfully.")
    print("Files saved in the data/ folder:")
    print("- candidate_facilities.csv")
    print("- customer_zones.csv")
    print("- transportation_costs.csv")

    print("\nCandidate Facilities Preview:")
    print(facilities.head())

    print("\nCustomer Zones Preview:")
    print(customers.head())

    print("\nTransportation Costs Preview:")
    print(transportation_costs.head())


if __name__ == "__main__":
    main()