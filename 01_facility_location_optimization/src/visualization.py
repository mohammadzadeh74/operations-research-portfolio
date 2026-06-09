"""
visualization.py

This script visualizes the facility location optimization results.

The visualization shows:
1. Customer demand zones
2. Candidate facility locations
3. Selected facility locations
4. Assignment lines from customers to selected facilities

Author: Mo Moha
Project: Facility Location Optimization
"""

import os
import pandas as pd
import matplotlib.pyplot as plt


def load_results():
    """
    Load input datasets and optimization results.

    Returns
    -------
    facilities : pandas.DataFrame
        Candidate facility data.

    customers : pandas.DataFrame
        Customer zone data.

    selected_facilities : pandas.DataFrame
        Facilities selected by the optimization model.

    customer_assignments : pandas.DataFrame
        Customer-to-facility assignment results.
    """

    facilities = pd.read_csv("data/candidate_facilities.csv")
    customers = pd.read_csv("data/customer_zones.csv")
    selected_facilities = pd.read_csv("outputs/selected_facilities.csv")
    customer_assignments = pd.read_csv("outputs/customer_assignments.csv")

    return facilities, customers, selected_facilities, customer_assignments


def plot_facility_assignments(
    facilities,
    customers,
    selected_facilities,
    customer_assignments,
    save_path="outputs/facility_assignment_map.png"
):
    """
    Plot the selected facilities and customer assignments.

    Parameters
    ----------
    facilities : pandas.DataFrame
        All candidate facilities.

    customers : pandas.DataFrame
        Customer demand zones.

    selected_facilities : pandas.DataFrame
        Facilities selected by the optimization model.

    customer_assignments : pandas.DataFrame
        Customer assignment results.

    save_path : str
        Path where the plot should be saved.
    """

    plt.figure(figsize=(12, 9))

    # Plot all candidate facilities
    plt.scatter(
        facilities["x_coord"],
        facilities["y_coord"],
        marker="s",
        s=120,
        label="Candidate Facilities"
    )

    # Plot selected facilities
    plt.scatter(
        selected_facilities["x_coord"],
        selected_facilities["y_coord"],
        marker="*",
        s=350,
        label="Selected Facilities"
    )

    # Plot customer zones
    plt.scatter(
        customers["x_coord"],
        customers["y_coord"],
        marker="o",
        s=customers["demand"],
        alpha=0.6,
        label="Customer Zones"
    )

    # Draw assignment lines
    for _, row in customer_assignments.iterrows():
        customer_x = row["x_coord_customer"]
        customer_y = row["y_coord_customer"]
        facility_x = row["x_coord_facility"]
        facility_y = row["y_coord_facility"]

        plt.plot(
            [customer_x, facility_x],
            [customer_y, facility_y],
            linewidth=0.8,
            alpha=0.5
        )

    # Label selected facilities
    for _, row in selected_facilities.iterrows():
        plt.text(
            row["x_coord"] + 1,
            row["y_coord"] + 1,
            row["facility_id"],
            fontsize=10,
            fontweight="bold"
        )

    # Label customer zones
    for _, row in customers.iterrows():
        plt.text(
            row["x_coord"] + 0.8,
            row["y_coord"] + 0.8,
            row["customer_id"],
            fontsize=8
        )

    plt.title("Facility Location Optimization: Selected Facilities and Customer Assignments")
    plt.xlabel("X Coordinate")
    plt.ylabel("Y Coordinate")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    plt.savefig(save_path, dpi=300)
    plt.show()

    print(f"Visualization saved to: {save_path}")


def main():
    """
    Main function to generate visualization.
    """

    facilities, customers, selected_facilities, customer_assignments = load_results()

    plot_facility_assignments(
        facilities=facilities,
        customers=customers,
        selected_facilities=selected_facilities,
        customer_assignments=customer_assignments
    )


if __name__ == "__main__":
    main()