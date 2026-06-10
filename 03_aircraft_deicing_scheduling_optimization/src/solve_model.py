import os
import pandas as pd
import pulp


def minutes_to_time(minutes):
    """
    Convert minutes from midnight to HH:MM format.
    Example: 480 -> 08:00
    """
    if minutes is None:
        return None

    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours:02d}:{mins:02d}"


def solve_deicing_schedule(
    aircraft_path="data/aircraft_schedule.csv",
    crews_path="data/crews.csv",
    travel_path="data/travel_times.csv",
    output_folder="outputs",
    departure_buffer_min=10,
    buffer_violation_cost_factor=0.25,
    solver_time_limit=60,
    solver_gap=0.01
):
    """
    Solve an aircraft de-icing/snow-removal scheduling model.

    Model features:
    - assigns each aircraft to one crew
    - determines service start and completion times
    - prevents crew schedule overlap
    - includes gate-to-gate travel/setup time
    - calculates departure delay
    - calculates crew overtime
    - adds a soft departure buffer requirement

    Departure buffer logic:
    Ideally, each aircraft should complete service at least
    departure_buffer_min minutes before scheduled departure.

    If this is not possible, the model allows a buffer violation
    but penalizes it in the objective.
    """

    aircraft_df = pd.read_csv(aircraft_path)
    crews_df = pd.read_csv(crews_path)
    travel_df = pd.read_csv(travel_path)

    aircraft_ids = aircraft_df["aircraft_id"].tolist()
    crew_ids = crews_df["crew_id"].tolist()

    # Dictionaries for quick lookup
    scheduled_departure = dict(
        zip(aircraft_df["aircraft_id"], aircraft_df["scheduled_departure_min"])
    )

    ready_time = dict(
        zip(aircraft_df["aircraft_id"], aircraft_df["ready_time_min"])
    )

    service_time = dict(
        zip(aircraft_df["aircraft_id"], aircraft_df["service_time_min"])
    )

    delay_penalty = dict(
        zip(aircraft_df["aircraft_id"], aircraft_df["delay_penalty_per_min"])
    )

    gate = dict(
        zip(aircraft_df["aircraft_id"], aircraft_df["gate"])
    )

    shift_start = dict(
        zip(crews_df["crew_id"], crews_df["shift_start_min"])
    )

    shift_end = dict(
        zip(crews_df["crew_id"], crews_df["shift_end_min"])
    )

    overtime_cost = dict(
        zip(crews_df["crew_id"], crews_df["overtime_cost_per_min"])
    )

    # Travel/setup time lookup between gates
    travel_time = {}

    for _, row in travel_df.iterrows():
        travel_time[(row["from_location"], row["to_location"])] = row["travel_time_min"]

    def get_travel_time(i, j):
        """
        Return travel/setup time from aircraft i gate to aircraft j gate.
        """
        return travel_time.get((gate[i], gate[j]), 0)

    # Big-M value for conditional constraints
    big_m = 10_000

    # Create optimization model
    model = pulp.LpProblem(
        "Aircraft_Deicing_Scheduling_With_Buffer",
        pulp.LpMinimize
    )

    # Assignment variable:
    # x[i, k] = 1 if aircraft i is assigned to crew k
    x = pulp.LpVariable.dicts(
        "assign",
        [(i, k) for i in aircraft_ids for k in crew_ids],
        cat="Binary"
    )

    # Start time variable
    start_time = pulp.LpVariable.dicts(
        "start_time",
        aircraft_ids,
        lowBound=0,
        cat="Continuous"
    )

    # Completion time variable
    completion_time = pulp.LpVariable.dicts(
        "completion_time",
        aircraft_ids,
        lowBound=0,
        cat="Continuous"
    )

    # Delay variable
    delay = pulp.LpVariable.dicts(
        "delay",
        aircraft_ids,
        lowBound=0,
        cat="Continuous"
    )

    # Buffer violation variable
    # This is positive when service finishes less than departure_buffer_min
    # minutes before departure.
    buffer_violation = pulp.LpVariable.dicts(
        "buffer_violation",
        aircraft_ids,
        lowBound=0,
        cat="Continuous"
    )

    # Crew overtime variable
    overtime = pulp.LpVariable.dicts(
        "overtime",
        crew_ids,
        lowBound=0,
        cat="Continuous"
    )

    # Sequencing variable:
    # y[i, j, k] = 1 if crew k serves aircraft i before aircraft j
    y = pulp.LpVariable.dicts(
        "sequence",
        [
            (i, j, k)
            for i in aircraft_ids
            for j in aircraft_ids
            for k in crew_ids
            if i != j
        ],
        cat="Binary"
    )

    # Objective function
    model += (
        # Actual departure delay cost
        pulp.lpSum(delay_penalty[i] * delay[i] for i in aircraft_ids)

        # Softer penalty for missing the preferred departure buffer
        + pulp.lpSum(
            buffer_violation_cost_factor * delay_penalty[i] * buffer_violation[i]
            for i in aircraft_ids
        )

        # Crew overtime cost
        + pulp.lpSum(overtime_cost[k] * overtime[k] for k in crew_ids)
    )

    # Constraint 1: each aircraft must be assigned to exactly one crew
    for i in aircraft_ids:
        model += (
            pulp.lpSum(x[(i, k)] for k in crew_ids) == 1,
            f"assign_once_{i}"
        )

    # Constraint 2: service cannot start before aircraft is ready
    for i in aircraft_ids:
        model += (
            start_time[i] >= ready_time[i],
            f"ready_time_{i}"
        )

    # Constraint 3: completion time definition
    for i in aircraft_ids:
        model += (
            completion_time[i] == start_time[i] + service_time[i],
            f"completion_time_{i}"
        )

    # Constraint 4: delay calculation
    for i in aircraft_ids:
        model += (
            delay[i] >= completion_time[i] - scheduled_departure[i],
            f"delay_calc_{i}"
        )

    # Constraint 5: departure buffer violation calculation
    # Preferred target:
    # completion_time <= scheduled_departure - departure_buffer_min
    for i in aircraft_ids:
        model += (
            buffer_violation[i] >= completion_time[i] - (
                scheduled_departure[i] - departure_buffer_min
            ),
            f"buffer_violation_calc_{i}"
        )

    # Constraint 6: assigned aircraft must respect crew shift start
    for i in aircraft_ids:
        for k in crew_ids:
            model += (
                start_time[i] >= shift_start[k] - big_m * (1 - x[(i, k)]),
                f"crew_shift_start_{i}_{k}"
            )

    # Constraint 7: overtime if completion exceeds crew shift end
    for i in aircraft_ids:
        for k in crew_ids:
            model += (
                overtime[k] >= completion_time[i] - shift_end[k] - big_m * (1 - x[(i, k)]),
                f"overtime_{i}_{k}"
            )

    # Constraint 8: sequencing/no-overlap constraints
    # If aircraft i and j are assigned to the same crew k,
    # then either i must finish before j starts, or j must finish before i starts.
    for k in crew_ids:
        for idx_i in range(len(aircraft_ids)):
            for idx_j in range(idx_i + 1, len(aircraft_ids)):
                i = aircraft_ids[idx_i]
                j = aircraft_ids[idx_j]

                travel_ij = get_travel_time(i, j)
                travel_ji = get_travel_time(j, i)

                # If y[i,j,k] = 1, then i is before j
                model += (
                    start_time[j] >= completion_time[i] + travel_ij
                    - big_m * (1 - y[(i, j, k)])
                    - big_m * (2 - x[(i, k)] - x[(j, k)]),
                    f"sequence_{i}_before_{j}_{k}"
                )

                # If y[i,j,k] = 0, then j is before i
                model += (
                    start_time[i] >= completion_time[j] + travel_ji
                    - big_m * y[(i, j, k)]
                    - big_m * (2 - x[(i, k)] - x[(j, k)]),
                    f"sequence_{j}_before_{i}_{k}"
                )

    # Solve model
    solver = pulp.PULP_CBC_CMD(
        msg=True,
        timeLimit=solver_time_limit,
        gapRel=solver_gap
    )

    model.solve(solver)

    status = pulp.LpStatus[model.status]
    objective_value = pulp.value(model.objective)

    print(f"Solver status: {status}")
    print(f"Objective value: {objective_value:.2f}")

    if status not in ["Optimal", "Not Solved"]:
        print("Warning: Model did not solve to optimality.")
        return None, None, None, status, objective_value

    # Build optimized schedule table
    results = []

    for i in aircraft_ids:
        assigned_crew = None

        for k in crew_ids:
            if pulp.value(x[(i, k)]) > 0.5:
                assigned_crew = k
                break

        start = pulp.value(start_time[i])
        completion = pulp.value(completion_time[i])
        delay_value = pulp.value(delay[i])
        buffer_violation_value = pulp.value(buffer_violation[i])

        aircraft_row = aircraft_df[aircraft_df["aircraft_id"] == i].iloc[0]

        buffer_target = scheduled_departure[i] - departure_buffer_min

        if delay_value > 0:
            service_status = "Delayed"
        elif buffer_violation_value > 0:
            service_status = "At Risk"
        else:
            service_status = "On Time"

        results.append({
            "aircraft_id": i,
            "flight_number": aircraft_row["flight_number"],
            "assigned_crew": assigned_crew,
            "gate": aircraft_row["gate"],
            "aircraft_type": aircraft_row["aircraft_type"],
            "ready_time_min": ready_time[i],
            "ready_time": minutes_to_time(ready_time[i]),
            "scheduled_departure_min": scheduled_departure[i],
            "scheduled_departure": minutes_to_time(scheduled_departure[i]),
            "departure_buffer_min": departure_buffer_min,
            "buffer_target_completion_min": buffer_target,
            "buffer_target_completion": minutes_to_time(buffer_target),
            "service_time_min": service_time[i],
            "start_time_min": round(start, 2),
            "start_time": minutes_to_time(start),
            "completion_time_min": round(completion, 2),
            "completion_time": minutes_to_time(completion),
            "delay_min": round(delay_value, 2),
            "buffer_violation_min": round(buffer_violation_value, 2),
            "service_status": service_status,
            "delay_penalty_per_min": delay_penalty[i],
            "weighted_delay_cost": round(delay_penalty[i] * delay_value, 2),
            "weighted_buffer_violation_cost": round(
                buffer_violation_cost_factor * delay_penalty[i] * buffer_violation_value,
                2
            )
        })

    schedule_df = pd.DataFrame(results)

    schedule_df = schedule_df.sort_values(
        by=["assigned_crew", "start_time_min"]
    ).reset_index(drop=True)

    # Add sequence order within each crew
    schedule_df["crew_sequence_order"] = (
        schedule_df
        .groupby("assigned_crew")
        .cumcount() + 1
    )

    # Build crew summary table
    crew_summary = []

    for k in crew_ids:
        assigned_jobs = schedule_df[schedule_df["assigned_crew"] == k]

        if len(assigned_jobs) > 0:
            first_start = assigned_jobs["start_time_min"].min()
            last_completion = assigned_jobs["completion_time_min"].max()
            total_service_time = assigned_jobs["service_time_min"].sum()
            span_time = last_completion - first_start
            utilization_percent = (
                total_service_time / span_time * 100
                if span_time > 0 else 0
            )
        else:
            first_start = None
            last_completion = None
            total_service_time = 0
            span_time = 0
            utilization_percent = 0

        overtime_value = pulp.value(overtime[k])

        crew_summary.append({
            "crew_id": k,
            "num_assigned_aircraft": len(assigned_jobs),
            "shift_start_min": shift_start[k],
            "shift_start": minutes_to_time(shift_start[k]),
            "shift_end_min": shift_end[k],
            "shift_end": minutes_to_time(shift_end[k]),
            "first_start_min": first_start,
            "first_start": minutes_to_time(first_start) if first_start is not None else None,
            "last_completion_min": last_completion,
            "last_completion": minutes_to_time(last_completion) if last_completion is not None else None,
            "total_service_time_min": total_service_time,
            "active_span_min": round(span_time, 2),
            "utilization_percent": round(utilization_percent, 2),
            "overtime_min": round(overtime_value, 2),
            "overtime_cost": round(overtime_cost[k] * overtime_value, 2)
        })

    crew_summary_df = pd.DataFrame(crew_summary)

    # Build flight risk/delay summary
    flight_risk_summary_df = schedule_df[
        [
            "aircraft_id",
            "flight_number",
            "assigned_crew",
            "scheduled_departure",
            "buffer_target_completion",
            "completion_time",
            "delay_min",
            "buffer_violation_min",
            "service_status",
            "delay_penalty_per_min",
            "weighted_delay_cost",
            "weighted_buffer_violation_cost"
        ]
    ].copy()

    flight_risk_summary_df = flight_risk_summary_df.sort_values(
        by=["delay_min", "buffer_violation_min"],
        ascending=False
    ).reset_index(drop=True)

    # Save outputs
    os.makedirs(output_folder, exist_ok=True)

    schedule_output_path = os.path.join(output_folder, "optimized_schedule.csv")
    crew_output_path = os.path.join(output_folder, "crew_summary.csv")
    risk_output_path = os.path.join(output_folder, "flight_delay_summary.csv")

    schedule_df.to_csv(schedule_output_path, index=False)
    crew_summary_df.to_csv(crew_output_path, index=False)
    flight_risk_summary_df.to_csv(risk_output_path, index=False)

    # Summary metrics
    total_delay = schedule_df["delay_min"].sum()
    total_buffer_violation = schedule_df["buffer_violation_min"].sum()
    delayed_flights = (schedule_df["service_status"] == "Delayed").sum()
    at_risk_flights = (schedule_df["service_status"] == "At Risk").sum()
    on_time_flights = (schedule_df["service_status"] == "On Time").sum()

    print("\nFiles saved:")
    print(f"- {schedule_output_path}")
    print(f"- {crew_output_path}")
    print(f"- {risk_output_path}")

    print("\nModel summary:")
    print(f"Total aircraft: {len(schedule_df)}")
    print(f"On-time flights: {on_time_flights}")
    print(f"At-risk flights: {at_risk_flights}")
    print(f"Delayed flights: {delayed_flights}")
    print(f"Total delay minutes: {total_delay:.2f}")
    print(f"Total buffer violation minutes: {total_buffer_violation:.2f}")

    print("\nOptimized schedule preview:")
    print(schedule_df.head(12))

    print("\nCrew summary:")
    print(crew_summary_df)

    print("\nTop delayed / at-risk flights:")
    print(flight_risk_summary_df.head(12))

    return schedule_df, crew_summary_df, flight_risk_summary_df, status, objective_value


if __name__ == "__main__":
    solve_deicing_schedule()