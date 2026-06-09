"""
scenario_visualization.py

This script visualizes the scenario analysis results for the
facility location optimization project.

The visualizations include:
1. Total cost by scenario
2. Capacity utilization by scenario

Author: Mo Moha
Project: Facility Location Optimization
"""

import os
import pandas as pd
import matplotlib.pyplot as plt


def load_scenario_results():
    """
    Load scenario analysis results.

    Returns
    -------
    pandas.DataFrame
        Scenario results table.
    """

    scenario_results = pd.read_csv("outputs/scenario_results.csv")

    return scenario_results


def plot_total_cost_by_scenario(
    scenario_results,
    save_path="outputs/scenario_total_cost.png"
):
    """
    Create a bar chart of total cost by scenario.

    Parameters
    ----------
    scenario_results : pandas.DataFrame
        Scenario results table.

    save_path : str
        Path where the chart should be saved.
    """

    plt.figure(figsize=(12, 7))

    plt.bar(
        scenario_results["scenario_name"],
        scenario_results["total_cost"]
    )

    plt.title("Total Cost by Facility Location Scenario")
    plt.xlabel("Scenario")
    plt.ylabel("Total Cost ($)")
    plt.xticks(rotation=30, ha="right")
    plt.grid(axis="y", alpha=0.4)

    # Add value labels above bars
    for index, value in enumerate(scenario_results["total_cost"]):
        plt.text(
            index,
            value,
            f"${value:,.0f}",
            ha="center",
            va="bottom",
            fontsize=9
        )

    plt.tight_layout()

    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    plt.savefig(save_path, dpi=300)
    plt.show()

    print(f"Total cost chart saved to: {save_path}")


def plot_capacity_utilization_by_scenario(
    scenario_results,
    save_path="outputs/scenario_capacity_utilization.png"
):
    """
    Create a bar chart of selected facility capacity utilization by scenario.

    Parameters
    ----------
    scenario_results : pandas.DataFrame
        Scenario results table.

    save_path : str
        Path where the chart should be saved.
    """

    plt.figure(figsize=(12, 7))

    utilization_percent = scenario_results["capacity_utilization"] * 100

    plt.bar(
        scenario_results["scenario_name"],
        utilization_percent
    )

    plt.title("Capacity Utilization by Facility Location Scenario")
    plt.xlabel("Scenario")
    plt.ylabel("Capacity Utilization (%)")
    plt.xticks(rotation=30, ha="right")
    plt.ylim(0, 110)
    plt.grid(axis="y", alpha=0.4)

    # Add value labels above bars
    for index, value in enumerate(utilization_percent):
        plt.text(
            index,
            value,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9
        )

    plt.tight_layout()

    if not os.path.exists("outputs"):
        os.makedirs("outputs")

    plt.savefig(save_path, dpi=300)
    plt.show()

    print(f"Capacity utilization chart saved to: {save_path}")


def main():
    """
    Main function to generate scenario visualizations.
    """

    scenario_results = load_scenario_results()

    plot_total_cost_by_scenario(scenario_results)
    plot_capacity_utilization_by_scenario(scenario_results)


if __name__ == "__main__":
    main()