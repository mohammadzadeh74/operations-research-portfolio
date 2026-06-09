import os
import pandas as pd
import plotly.express as px


def load_scenario_results():
    """
    Load scenario analysis results.
    """

    scenario_results = pd.read_csv("outputs/scenario_results.csv")

    return scenario_results


def prepare_data(scenario_results):
    """
    Prepare scenario results for visualization.
    """

    # Keep only feasible scenarios for numeric plots
    feasible_results = scenario_results[
        scenario_results["feasible"] == True
    ].copy()

    # Make scenario names easier to read in plots
    feasible_results["scenario"] = feasible_results["scenario"].astype(str)

    return feasible_results


def plot_total_operating_cost(feasible_results):
    """
    Create bar chart comparing total operating cost by scenario.
    """

    fig = px.bar(
        feasible_results,
        x="scenario",
        y="total_operating_cost",
        text="total_operating_cost",
        title="Total Operating Cost by Fleet Planning Scenario",
        labels={
            "scenario": "Scenario",
            "total_operating_cost": "Total Operating Cost ($)"
        }
    )

    fig.update_traces(
        texttemplate="$%{text:,.0f}",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_tickangle=-30,
        yaxis_title="Total Operating Cost ($)",
        xaxis_title="Scenario",
        height=600
    )

    return fig


def plot_total_distance(feasible_results):
    """
    Create bar chart comparing total delivery distance by scenario.
    """

    fig = px.bar(
        feasible_results,
        x="scenario",
        y="total_distance_miles",
        text="total_distance_miles",
        title="Total Delivery Distance by Fleet Planning Scenario",
        labels={
            "scenario": "Scenario",
            "total_distance_miles": "Total Delivery Distance (miles)"
        }
    )

    fig.update_traces(
        texttemplate="%{text:,.0f} mi",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_tickangle=-30,
        yaxis_title="Total Delivery Distance (miles)",
        xaxis_title="Scenario",
        height=600
    )

    return fig


def plot_capacity_utilization(feasible_results):
    """
    Create grouped bar chart comparing average and maximum utilization.
    """

    utilization_df = feasible_results[
        [
            "scenario",
            "average_capacity_utilization",
            "maximum_capacity_utilization"
        ]
    ].copy()

    utilization_long = utilization_df.melt(
        id_vars="scenario",
        value_vars=[
            "average_capacity_utilization",
            "maximum_capacity_utilization"
        ],
        var_name="utilization_metric",
        value_name="utilization_value"
    )

    utilization_long["utilization_metric"] = utilization_long[
        "utilization_metric"
    ].replace({
        "average_capacity_utilization": "Average Utilization",
        "maximum_capacity_utilization": "Maximum Utilization"
    })

    utilization_long["utilization_percent"] = (
        utilization_long["utilization_value"] * 100
    )

    fig = px.bar(
        utilization_long,
        x="scenario",
        y="utilization_percent",
        color="utilization_metric",
        barmode="group",
        text="utilization_percent",
        title="Vehicle Capacity Utilization by Scenario",
        labels={
            "scenario": "Scenario",
            "utilization_percent": "Capacity Utilization (%)",
            "utilization_metric": "Metric"
        }
    )

    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_tickangle=-30,
        yaxis_title="Capacity Utilization (%)",
        xaxis_title="Scenario",
        height=600
    )

    return fig


def main():
    os.makedirs("outputs", exist_ok=True)

    scenario_results = load_scenario_results()
    feasible_results = prepare_data(scenario_results)

    cost_fig = plot_total_operating_cost(feasible_results)
    distance_fig = plot_total_distance(feasible_results)
    utilization_fig = plot_capacity_utilization(feasible_results)

    cost_path = "outputs/scenario_cost_comparison.html"
    distance_path = "outputs/scenario_distance_comparison.html"
    utilization_path = "outputs/scenario_utilization_comparison.html"

    cost_fig.write_html(cost_path)
    distance_fig.write_html(distance_path)
    utilization_fig.write_html(utilization_path)

    print("\nScenario visualization files created successfully.")
    print(f"Cost comparison saved to: {cost_path}")
    print(f"Distance comparison saved to: {distance_path}")
    print(f"Utilization comparison saved to: {utilization_path}")

    cost_fig.show()
    distance_fig.show()
    utilization_fig.show()


if __name__ == "__main__":
    main()