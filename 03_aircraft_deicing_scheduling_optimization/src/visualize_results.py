import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def minutes_to_datetime(minutes):
    """
    Convert minutes from midnight into a timestamp for Plotly timeline charts.
    We use a dummy date because the actual date does not matter.
    """
    return pd.Timestamp("2026-01-01") + pd.to_timedelta(minutes, unit="m")


def create_gantt_chart(
    schedule_path="outputs/optimized_schedule.csv",
    output_path="outputs/crew_gantt_chart.html"
):
    """
    Create a Gantt chart showing aircraft service schedule by crew.
    """

    schedule_df = pd.read_csv(schedule_path)

    schedule_df["start_datetime"] = schedule_df["start_time_min"].apply(minutes_to_datetime)
    schedule_df["completion_datetime"] = schedule_df["completion_time_min"].apply(minutes_to_datetime)

    fig = px.timeline(
        schedule_df,
        x_start="start_datetime",
        x_end="completion_datetime",
        y="assigned_crew",
        color="service_status",
        text="flight_number",
        hover_data=[
            "aircraft_id",
            "flight_number",
            "gate",
            "aircraft_type",
            "ready_time",
            "scheduled_departure",
            "buffer_target_completion",
            "completion_time",
            "delay_min",
            "buffer_violation_min",
            "crew_sequence_order"
        ],
        title="Optimized Aircraft De-Icing Schedule by Crew"
    )

    fig.update_yaxes(
        autorange="reversed",
        title="Crew"
    )

    fig.update_xaxes(
        title="Time",
        tickformat="%H:%M"
    )

    fig.update_traces(
        textposition="inside"
    )

    fig.update_layout(
        height=520,
        legend_title_text="Service Status",
        margin=dict(l=40, r=40, t=70, b=40)
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path)

    return fig


def create_flight_risk_ranking_chart(
    delay_path="outputs/flight_delay_summary.csv",
    output_path="outputs/flight_risk_ranking_chart.html"
):
    """
    Create a stakeholder-friendly flight risk ranking chart.

    Instead of showing delay and buffer violation as separate bars,
    this chart ranks flights by buffer violation minutes.

    Interpretation:
    - Delayed flights have positive delay.
    - At-risk flights are not delayed but violate the departure buffer.
    - On-time flights complete before the buffer target.
    """

    delay_df = pd.read_csv(delay_path)

    if "buffer_violation_min" not in delay_df.columns:
        delay_df["buffer_violation_min"] = 0

    if "service_status" not in delay_df.columns:
        delay_df["service_status"] = delay_df["delay_min"].apply(
            lambda x: "Delayed" if x > 0 else "On Time"
        )

    delay_df = delay_df.sort_values(
        by=["buffer_violation_min", "delay_min"],
        ascending=False
    ).reset_index(drop=True)

    fig = px.bar(
        delay_df,
        x="flight_number",
        y="buffer_violation_min",
        color="service_status",
        text="buffer_violation_min",
        hover_data=[
            "aircraft_id",
            "assigned_crew",
            "scheduled_departure",
            "buffer_target_completion",
            "completion_time",
            "delay_min",
            "buffer_violation_min",
            "delay_penalty_per_min",
            "weighted_delay_cost",
            "weighted_buffer_violation_cost"
        ],
        title="Flight Risk Ranking by Departure Buffer Violation"
    )

    fig.update_traces(
        texttemplate="%{text:.0f}",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="Flight Number",
        yaxis_title="Buffer Violation Minutes",
        legend_title_text="Service Status",
        height=520,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path)

    return fig


def create_delay_summary_chart(
    delay_path="outputs/flight_delay_summary.csv",
    output_path="outputs/delay_summary_chart.html"
):
    """
    Keep a delay-focused chart for technical review.

    This chart shows actual departure delay only.
    The main stakeholder chart should be the flight risk ranking chart.
    """

    delay_df = pd.read_csv(delay_path)

    delay_df = delay_df.sort_values(
        by="delay_min",
        ascending=False
    ).reset_index(drop=True)

    fig = px.bar(
        delay_df,
        x="flight_number",
        y="delay_min",
        color="service_status" if "service_status" in delay_df.columns else None,
        text="delay_min",
        hover_data=[
            "aircraft_id",
            "assigned_crew",
            "scheduled_departure",
            "completion_time",
            "delay_min"
        ],
        title="Actual Departure Delay by Flight"
    )

    fig.update_traces(
        texttemplate="%{text:.0f}",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="Flight Number",
        yaxis_title="Delay Minutes",
        legend_title_text="Service Status",
        height=500,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path)

    return fig


def create_crew_utilization_chart(
    crew_path="outputs/crew_summary.csv",
    output_path="outputs/crew_utilization_chart.html"
):
    """
    Create a bar chart showing crew utilization.
    A benchmark line is added to make interpretation easier.
    """

    crew_df = pd.read_csv(crew_path)

    fig = px.bar(
        crew_df,
        x="crew_id",
        y="utilization_percent",
        text="utilization_percent",
        hover_data=[
            "num_assigned_aircraft",
            "total_service_time_min",
            "active_span_min",
            "overtime_min",
            "overtime_cost"
        ],
        title="Crew Utilization"
    )

    fig.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside"
    )

    # Add benchmark line at 90%
    fig.add_hline(
        y=90,
        line_dash="dash",
        annotation_text="High utilization threshold: 90%",
        annotation_position="top left"
    )

    fig.update_layout(
        xaxis_title="Crew",
        yaxis_title="Utilization (%)",
        yaxis_range=[0, max(110, crew_df["utilization_percent"].max() + 10)],
        height=500,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path)

    return fig


def create_scenario_comparison_chart(
    scenario_path="outputs/scenario_comparison.csv",
    output_path="outputs/scenario_comparison_chart.html"
):
    """
    Create grouped scenario comparison chart for flight status counts.
    """

    scenario_df = pd.read_csv(scenario_path)

    metrics_df = scenario_df[
        [
            "scenario",
            "on_time_flights",
            "at_risk_flights",
            "delayed_flights"
        ]
    ].rename(
        columns={
            "on_time_flights": "On Time",
            "at_risk_flights": "At Risk",
            "delayed_flights": "Delayed"
        }
    ).melt(
        id_vars="scenario",
        var_name="Service Status",
        value_name="Number of Flights"
    )

    fig = px.bar(
        metrics_df,
        x="scenario",
        y="Number of Flights",
        color="Service Status",
        barmode="group",
        text="Number of Flights",
        title="Scenario Comparison: Flight Status Counts"
    )

    fig.update_traces(
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="Scenario",
        yaxis_title="Number of Flights",
        legend_title_text="Service Status",
        height=520,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path)

    return fig


def create_scenario_delay_buffer_chart(
    scenario_path="outputs/scenario_comparison.csv",
    output_path="outputs/scenario_delay_buffer_chart.html"
):
    """
    Create scenario comparison chart for delay and buffer violation only.
    This avoids mixing crew overtime with flight delay metrics.
    """

    scenario_df = pd.read_csv(scenario_path)

    metrics_df = scenario_df[
        [
            "scenario",
            "total_delay_min",
            "total_buffer_violation_min"
        ]
    ].rename(
        columns={
            "total_delay_min": "Total Delay Minutes",
            "total_buffer_violation_min": "Total Buffer Violation Minutes"
        }
    ).melt(
        id_vars="scenario",
        var_name="Metric",
        value_name="Minutes"
    )

    fig = px.bar(
        metrics_df,
        x="scenario",
        y="Minutes",
        color="Metric",
        barmode="group",
        text="Minutes",
        title="Scenario Comparison: Delay and Buffer Violation"
    )

    fig.update_traces(
        texttemplate="%{text:.0f}",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="Scenario",
        yaxis_title="Minutes",
        legend_title_text="Metric",
        height=520,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path)

    return fig


def create_scenario_overtime_chart(
    scenario_path="outputs/scenario_comparison.csv",
    output_path="outputs/scenario_overtime_chart.html"
):
    """
    Create scenario comparison chart for crew overtime.
    """

    scenario_df = pd.read_csv(scenario_path)

    fig = px.bar(
        scenario_df,
        x="scenario",
        y="total_overtime_min",
        text="total_overtime_min",
        hover_data=[
            "num_aircraft",
            "num_crews",
            "weather_severity",
            "average_crew_utilization_percent",
            "total_overtime_cost"
        ],
        title="Scenario Comparison: Crew Overtime"
    )

    fig.update_traces(
        texttemplate="%{text:.0f}",
        textposition="outside"
    )

    fig.update_layout(
        xaxis_title="Scenario",
        yaxis_title="Total Overtime Minutes",
        height=500,
        margin=dict(l=40, r=40, t=70, b=40)
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path)

    return fig


def create_all_visualizations():
    """
    Create all visual outputs for the project.
    """

    print("Creating visualizations...")

    create_gantt_chart()
    print("- outputs/crew_gantt_chart.html")

    create_flight_risk_ranking_chart()
    print("- outputs/flight_risk_ranking_chart.html")

    create_delay_summary_chart()
    print("- outputs/delay_summary_chart.html")

    create_crew_utilization_chart()
    print("- outputs/crew_utilization_chart.html")

    if os.path.exists("outputs/scenario_comparison.csv"):
        create_scenario_comparison_chart()
        print("- outputs/scenario_comparison_chart.html")

        create_scenario_delay_buffer_chart()
        print("- outputs/scenario_delay_buffer_chart.html")

        create_scenario_overtime_chart()
        print("- outputs/scenario_overtime_chart.html")
    else:
        print("Scenario comparison file not found. Skipping scenario charts.")

    print("\nVisualizations created successfully.")


if __name__ == "__main__":
    create_all_visualizations()