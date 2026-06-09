import pandas as pd
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2


def load_data():
    """
    Load depot, customer, vehicle, and distance matrix data.
    """

    depot = pd.read_csv("data/depot.csv")
    customers = pd.read_csv("data/customers.csv")
    vehicles = pd.read_csv("data/vehicles.csv")
    distance_matrix_df = pd.read_csv("data/distance_matrix.csv")

    return depot, customers, vehicles, distance_matrix_df


def create_distance_matrix(location_ids, distance_matrix_df):
    """
    Convert the long-format distance table into a square distance matrix
    required by OR-Tools.
    """

    distance_lookup = {
        (row["from_id"], row["to_id"]): row["distance_miles"]
        for _, row in distance_matrix_df.iterrows()
    }

    distance_matrix = []

    for from_id in location_ids:
        row = []

        for to_id in location_ids:
            distance = distance_lookup[(from_id, to_id)]

            # OR-Tools works with integer values.
            # We multiply miles by 100 to preserve two decimals.
            row.append(int(distance * 100))

        distance_matrix.append(row)

    return distance_matrix


def build_data_model(depot, customers, vehicles, distance_matrix_df):
    """
    Build the input dictionary for the fleet routing model.
    """

    location_ids = ["D0"] + customers["customer_id"].tolist()

    distance_matrix = create_distance_matrix(
        location_ids,
        distance_matrix_df
    )

    demands = [0] + customers["demand_units"].tolist()

    vehicle_capacities = vehicles["capacity_units"].tolist()

    max_route_distances = [
        int(distance * 100)
        for distance in vehicles["max_route_distance"].tolist()
    ]

    data = {
        "location_ids": location_ids,
        "distance_matrix": distance_matrix,
        "demands": demands,
        "vehicle_capacities": vehicle_capacities,
        "max_route_distances": max_route_distances,
        "num_vehicles": len(vehicles),
        "depot_index": 0,
        "vehicles": vehicles,
        "customers": customers,
    }

    return data


def print_feasibility_check(data):
    """
    Print basic feasibility checks before solving the model.
    """

    total_demand = sum(data["demands"])
    total_capacity = sum(data["vehicle_capacities"])

    print("\nFeasibility Check")
    print("------------------------")
    print(f"Total customer demand: {total_demand} units")
    print(f"Total vehicle capacity: {total_capacity} units")

    if total_demand > total_capacity:
        print("Warning: Total demand exceeds total vehicle capacity.")
        print("The model is likely infeasible.")
    else:
        print("Capacity check passed.")

    print("\nVehicle Route Distance Limits")
    print("------------------------")

    vehicles = data["vehicles"]

    for _, row in vehicles.iterrows():
        print(
            f"{row['vehicle_id']} ({row['vehicle_type']}): "
            f"max {row['max_route_distance']} miles"
        )


def solve_cvrp(data):
    """
    Solve the Capacitated Vehicle Routing Problem with:
    - vehicle capacity limits
    - vehicle-specific cost per mile
    - fixed vehicle usage cost
    - maximum route distance limits
    """

    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]),
        data["num_vehicles"],
        data["depot_index"]
    )

    routing = pywrapcp.RoutingModel(manager)

    # --------------------------------------------------
    # 1. Vehicle-specific travel cost objective
    # --------------------------------------------------

    def create_vehicle_cost_callback(vehicle_id):
        """
        Create a travel cost callback for each vehicle.

        Travel cost = distance * vehicle cost per mile
        """

        cost_per_mile = data["vehicles"].iloc[vehicle_id]["cost_per_mile"]

        def vehicle_cost_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)

            distance_miles = data["distance_matrix"][from_node][to_node] / 100

            travel_cost = distance_miles * cost_per_mile

            # Multiply by 100 to represent cents.
            return int(travel_cost * 100)

        return vehicle_cost_callback

    for vehicle_id in range(data["num_vehicles"]):
        vehicle_cost_callback = create_vehicle_cost_callback(vehicle_id)

        vehicle_cost_callback_index = routing.RegisterTransitCallback(
            vehicle_cost_callback
        )

        routing.SetArcCostEvaluatorOfVehicle(
            vehicle_cost_callback_index,
            vehicle_id
        )

    # --------------------------------------------------
    # 2. Fixed cost for using each vehicle
    # --------------------------------------------------

    for vehicle_id in range(data["num_vehicles"]):
        fixed_cost = data["vehicles"].iloc[vehicle_id]["fixed_cost"]

        # Multiply by 100 to represent cents.
        routing.SetFixedCostOfVehicle(
            int(fixed_cost * 100),
            vehicle_id
        )

    # --------------------------------------------------
    # 3. Vehicle capacity constraint
    # --------------------------------------------------

    def demand_callback(from_index):
        """
        Return demand at a customer node.
        """

        from_node = manager.IndexToNode(from_index)

        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(
        demand_callback
    )

    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        data["vehicle_capacities"],
        True,
        "Capacity"
    )

    # --------------------------------------------------
    # 4. Maximum route distance constraint
    # --------------------------------------------------

    def distance_callback(from_index, to_index):
        """
        Return physical travel distance between two nodes.
        This is used for maximum route distance limits.
        """

        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)

        return data["distance_matrix"][from_node][to_node]

    distance_callback_index = routing.RegisterTransitCallback(
        distance_callback
    )

    routing.AddDimensionWithVehicleCapacity(
        distance_callback_index,
        0,
        data["max_route_distances"],
        True,
        "Distance"
    )

    # --------------------------------------------------
    # 5. Search settings
    # --------------------------------------------------

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()

    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )

    search_parameters.time_limit.seconds = 15

    solution = routing.SolveWithParameters(search_parameters)

    return manager, routing, solution


def extract_solution(data, manager, routing, solution):
    """
    Extract the optimized routes into:
    - stop-level route assignments
    - route-level summary table
    """

    route_records = []
    route_summary_records = []

    total_distance = 0
    total_load = 0
    total_operating_cost = 0

    if solution is None:
        print("\nNo feasible solution found.")
        print("Possible reasons:")
        print("- Total demand is higher than total fleet capacity.")
        print("- Maximum route distance is too restrictive.")
        print("- Customer locations are too spread out for the current fleet.")
        return None

    for vehicle_id in range(data["num_vehicles"]):

        index = routing.Start(vehicle_id)

        route_distance = 0
        route_load = 0
        stop_sequence = 0

        vehicle_name = data["vehicles"].iloc[vehicle_id]["vehicle_id"]
        vehicle_type = data["vehicles"].iloc[vehicle_id]["vehicle_type"]
        vehicle_capacity = data["vehicles"].iloc[vehicle_id]["capacity_units"]
        fixed_cost = data["vehicles"].iloc[vehicle_id]["fixed_cost"]
        cost_per_mile = data["vehicles"].iloc[vehicle_id]["cost_per_mile"]
        max_route_distance = data["vehicles"].iloc[vehicle_id]["max_route_distance"]

        print(f"\nRoute for {vehicle_name} ({vehicle_type}):")

        while not routing.IsEnd(index):

            node_index = manager.IndexToNode(index)
            location_id = data["location_ids"][node_index]
            demand = data["demands"][node_index]

            route_load += demand

            route_records.append({
                "vehicle_id": vehicle_name,
                "vehicle_type": vehicle_type,
                "stop_sequence": stop_sequence,
                "location_id": location_id,
                "demand_units": demand,
                "route_load_so_far": route_load,
                "vehicle_capacity": vehicle_capacity
            })

            print(f"  Stop {stop_sequence}: {location_id} | Load: {route_load}")

            previous_index = index
            index = solution.Value(routing.NextVar(index))

            from_node = manager.IndexToNode(previous_index)
            to_node = manager.IndexToNode(index)

            route_distance += data["distance_matrix"][from_node][to_node]

            stop_sequence += 1

        node_index = manager.IndexToNode(index)
        location_id = data["location_ids"][node_index]

        route_records.append({
            "vehicle_id": vehicle_name,
            "vehicle_type": vehicle_type,
            "stop_sequence": stop_sequence,
            "location_id": location_id,
            "demand_units": 0,
            "route_load_so_far": route_load,
            "vehicle_capacity": vehicle_capacity
        })

        route_distance_miles = route_distance / 100

        if route_load > 0:
            route_travel_cost = route_distance_miles * cost_per_mile
            route_total_cost = route_travel_cost + fixed_cost
            vehicle_used = True
        else:
            route_travel_cost = 0
            route_total_cost = 0
            vehicle_used = False

        number_of_customer_stops = sum(
            1 for record in route_records
            if record["vehicle_id"] == vehicle_name
            and record["location_id"] != "D0"
        )

        capacity_utilization = route_load / vehicle_capacity

        route_summary_records.append({
            "vehicle_id": vehicle_name,
            "vehicle_type": vehicle_type,
            "route_distance_miles": round(route_distance_miles, 2),
            "max_route_distance": max_route_distance,
            "route_load": route_load,
            "vehicle_capacity": vehicle_capacity,
            "capacity_utilization": round(capacity_utilization, 3),
            "number_of_customer_stops": number_of_customer_stops,
            "fixed_cost": fixed_cost,
            "cost_per_mile": cost_per_mile,
            "route_travel_cost": round(route_travel_cost, 2),
            "route_total_cost": round(route_total_cost, 2),
            "vehicle_used": vehicle_used
        })

        print(f"  Stop {stop_sequence}: {location_id}")
        print(f"  Route distance: {route_distance_miles:.2f} miles")
        print(f"  Route distance limit: {max_route_distance:.2f} miles")
        print(f"  Route load: {route_load} / {vehicle_capacity} units")
        print(f"  Route operating cost: ${route_total_cost:.2f}")

        total_distance += route_distance_miles
        total_load += route_load
        total_operating_cost += route_total_cost

    route_df = pd.DataFrame(route_records)
    route_summary_df = pd.DataFrame(route_summary_records)

    route_df.to_csv("data/optimized_routes.csv", index=False)
    route_summary_df.to_csv("data/route_summary.csv", index=False)

    print("\nModel Summary")
    print("------------------------")
    print(f"Total delivery distance: {total_distance:.2f} miles")
    print(f"Total delivered demand: {total_load} units")
    print(f"Total operating cost: ${total_operating_cost:.2f}")

    print("\nFiles Saved")
    print("------------------------")
    print("Stop-level route assignment saved to data/optimized_routes.csv")
    print("Route-level summary saved to data/route_summary.csv")

    return route_df, route_summary_df


def main():
    depot, customers, vehicles, distance_matrix_df = load_data()

    data = build_data_model(
        depot,
        customers,
        vehicles,
        distance_matrix_df
    )

    print_feasibility_check(data)

    manager, routing, solution = solve_cvrp(data)

    extract_solution(data, manager, routing, solution)


if __name__ == "__main__":
    main()