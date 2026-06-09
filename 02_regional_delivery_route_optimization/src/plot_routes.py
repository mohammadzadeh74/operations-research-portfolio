import os
import pandas as pd
import plotly.graph_objects as go


def load_data():
    """
    Load the data needed for route visualization.
    """

    depot = pd.read_csv("data/depot.csv")
    customers = pd.read_csv("data/customers.csv")
    optimized_routes = pd.read_csv("data/optimized_routes.csv")
    route_summary = pd.read_csv("data/route_summary.csv")

    return depot, customers, optimized_routes, route_summary


def prepare_location_data(depot, customers):
    """
    Create one combined location table for depot + customers.
    """

    depot_locations = pd.DataFrame({
        "location_id": depot["depot_id"],
        "location_name": depot["depot_name"],
        "location_type": "Depot",
        "x_coord": depot["x_coord"],
        "y_coord": depot["y_coord"]
    })

    customer_locations = pd.DataFrame({
        "location_id": customers["customer_id"],
        "location_name": customers["customer_name"],
        "location_type": "Customer",
        "x_coord": customers["x_coord"],
        "y_coord": customers["y_coord"]
    })

    locations = pd.concat(
        [depot_locations, customer_locations],
        ignore_index=True
    )

    return locations


def build_route_plot_dataframe(optimized_routes, locations):
    """
    Merge route assignments with coordinates.
    """

    plot_df = optimized_routes.merge(
        locations,
        on="location_id",
        how="left"
    )

    return plot_df


def create_route_map(plot_df, route_summary):
    """
    Build an interactive Plotly route map.
    """

    fig = go.Figure()

    # -----------------------------
    # Add depot marker
    # -----------------------------
    depot_points = plot_df[plot_df["location_id"] == "D0"].drop_duplicates(
        subset=["location_id"]
    )

    fig.add_trace(
        go.Scatter(
            x=depot_points["x_coord"],
            y=depot_points["y_coord"],
            mode="markers+text",
            name="Depot",
            text=["Depot"],
            textposition="top center",
            marker=dict(
                size=14,
                symbol="diamond",
                color="black"
            ),
            hovertemplate=(
                "<b>Depot</b><br>"
                + "Location ID: %{text}<br>"
                + "X: %{x}<br>"
                + "Y: %{y}<extra></extra>"
            )
        )
    )

    # -----------------------------
    # Add each used vehicle route
    # -----------------------------
    color_list = [
        "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
    ]

    used_routes = route_summary[route_summary["vehicle_used"] == True].copy()

    for i, (_, route_info) in enumerate(used_routes.iterrows()):
        vehicle_id = route_info["vehicle_id"]
        vehicle_type = route_info["vehicle_type"]

        vehicle_route = plot_df[
            plot_df["vehicle_id"] == vehicle_id
        ].sort_values("stop_sequence")

        color = color_list[i % len(color_list)]

        hover_text = []

        for _, row in vehicle_route.iterrows():
            hover_text.append(
                f"Vehicle: {row['vehicle_id']}<br>"
                f"Stop Sequence: {row['stop_sequence']}<br>"
                f"Location: {row['location_id']}<br>"
                f"Demand: {row['demand_units']}<br>"
                f"Load So Far: {row['route_load_so_far']}<br>"
                f"Vehicle Capacity: {row['vehicle_capacity']}"
            )

        fig.add_trace(
            go.Scatter(
                x=vehicle_route["x_coord"],
                y=vehicle_route["y_coord"],
                mode="lines+markers+text",
                name=f"{vehicle_id} ({vehicle_type})",
                text=vehicle_route["stop_sequence"],
                textposition="top center",
                marker=dict(
                    size=10,
                    color=color
                ),
                line=dict(
                    width=3,
                    color=color
                ),
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_text
            )
        )

    # -----------------------------
    # Figure layout
    # -----------------------------
    fig.update_layout(
        title="Optimized Delivery Routes by Vehicle",
        xaxis_title="X Coordinate",
        yaxis_title="Y Coordinate",
        template="plotly_white",
        legend_title="Vehicle Routes",
        width=1000,
        height=700
    )

    return fig


def main():
    depot, customers, optimized_routes, route_summary = load_data()

    locations = prepare_location_data(depot, customers)

    plot_df = build_route_plot_dataframe(
        optimized_routes,
        locations
    )

    fig = create_route_map(plot_df, route_summary)

    os.makedirs("outputs", exist_ok=True)

    output_file = "outputs/route_map.html"
    fig.write_html(output_file)

    print("\nRoute visualization created successfully.")
    print(f"Interactive map saved to: {output_file}")

    fig.show()


if __name__ == "__main__":
    main()