# Facility Location Optimization for Regional Distribution Planning

## Project Overview

This project solves a facility location optimization problem for a regional distribution network. The goal is to decide which candidate facilities should be opened and how customer demand zones should be assigned to those facilities while minimizing total cost.

The model considers:

* Facility opening costs
* Transportation costs
* Customer demand
* Facility capacity limits
* Service-radius restrictions
* Optional budget and facility-count constraints

This project is designed as an Operations Research portfolio project and demonstrates how mathematical optimization can support strategic network design decisions.

---

## Business Problem

A company wants to expand its regional distribution network. It has several candidate facility locations and multiple customer zones with known demand.

Opening more facilities may reduce transportation distance and improve service coverage, but it also increases fixed operating cost. Opening fewer facilities may reduce fixed cost, but it can increase transportation cost and create capacity risk.

The business question is:

> Which facilities should be opened, and how should customer zones be assigned, in order to minimize total cost while satisfying demand and operational constraints?

---

## Optimization Model

This project formulates the facility location problem as a Mixed-Integer Linear Programming model.

### Decision Variables

`y_j`

Binary variable equal to 1 if facility `j` is opened, and 0 otherwise.

`x_ij`

Continuous variable representing the amount of demand from customer zone `i` assigned to facility `j`.

---

## Objective Function

The objective is to minimize total cost:

```text
Total Cost = Facility Opening Cost + Transportation Cost
```

The model balances fixed facility costs against customer assignment and transportation costs.

---

## Constraints

The model includes the following constraints:

1. Each customer zone demand must be fully satisfied.
2. A customer can only be assigned to an open facility.
3. Facility capacity cannot be exceeded.
4. Customers can only be served by facilities within the maximum service radius.
5. Optional: the number of opened facilities can be limited.
6. Optional: the total facility opening budget can be limited.

---

## Synthetic Dataset

The project uses synthetic data generated in Python.

### Candidate Facilities

Each candidate facility includes:

* Facility ID
* Facility name
* X coordinate
* Y coordinate
* Opening cost
* Capacity

### Customer Zones

Each customer zone includes:

* Customer ID
* Customer name
* X coordinate
* Y coordinate
* Demand

### Transportation Costs

Transportation records include every customer-facility pair:

* Customer ID
* Facility ID
* Distance
* Cost per unit
* Service-radius eligibility

---

## Project Structure

```text
facility-location-optimization/
│
├── README.md
├── requirements.txt
│
├── data/
│   ├── candidate_facilities.csv
│   ├── customer_zones.csv
│   └── transportation_costs.csv
│
├── src/
│   ├── generate_data.py
│   ├── optimization_model.py
│   ├── visualization.py
│   ├── scenario_analysis.py
│   └── scenario_visualization.py
│
├── outputs/
│   ├── selected_facilities.csv
│   ├── customer_assignments.csv
│   ├── scenario_results.csv
│   ├── facility_assignment_map.png
│   ├── scenario_total_cost.png
│   └── scenario_capacity_utilization.png
│
└── app/
    └── streamlit_app.py
```

---

## Python Files

### `generate_data.py`

Generates synthetic facility, customer, and transportation cost datasets.

### `optimization_model.py`

Builds and solves the MILP facility location model.

### `visualization.py`

Creates a map-like visualization of selected facilities and customer assignments.

### `scenario_analysis.py`

Runs multiple optimization scenarios and compares total cost, selected facilities, demand, and capacity utilization.

### `scenario_visualization.py`

Creates scenario comparison charts for total cost and capacity utilization.

---

## Base Case Results

The base optimization model selected 4 facilities:

```text
F4, F5, F6, F8
```

### Base Case Summary

```text
Solver Status: Optimal
Total Cost: $1,250,893.04
Number of Selected Facilities: 4
Selected Facilities: F4, F5, F6, F8
```

The selected facilities serve different geographic customer clusters:

* F4 serves the upper-right and upper-middle customer zones.
* F5 serves the northwest cluster.
* F6 serves the southwest and lower-middle cluster.
* F8 serves the southeast cluster.

This result is consistent with the expected behavior of a facility location model because customers are generally assigned to nearby selected facilities while respecting facility capacities.

---

## Scenario Analysis

Several scenarios were tested to evaluate how the network design changes under different business conditions.

| Scenario          | Solver Status |    Total Cost | Selected Facilities | Capacity Utilization |
| ----------------- | ------------: | ------------: | ------------------- | -------------------: |
| Base Case         |       Optimal | $1,250,893.04 | F4, F5, F6, F8      |                79.0% |
| Max 3 Facilities  |       Optimal | $1,274,987.92 | F1, F4, F8          |                98.5% |
| Max 5 Facilities  |       Optimal | $1,250,893.04 | F4, F5, F6, F8      |                79.0% |
| Low Budget        |       Optimal | $1,274,987.92 | F1, F4, F8          |                98.5% |
| High Budget       |       Optimal | $1,250,893.04 | F4, F5, F6, F8      |                79.0% |
| Demand Growth 20% |       Optimal | $1,425,945.32 | F4, F5, F6, F8      |                94.8% |

---

## Key Insights

The base case opens four facilities and achieves the lowest total cost among the tested scenarios.

The Max 3 Facilities scenario is feasible, but it increases total cost and pushes capacity utilization to 98.5%. This means the network can operate with three facilities, but it has very little spare capacity. From an operational perspective, this solution is riskier.

The Low Budget scenario produces the same result as the Max 3 Facilities scenario. This indicates that the budget restriction prevents the model from selecting the more flexible four-facility network.

The Max 5 Facilities and High Budget scenarios return the same result as the base case. This means that opening additional facilities does not reduce transportation cost enough to justify the extra fixed opening cost.

The Demand Growth 20% scenario keeps the same four selected facilities, but total cost increases and capacity utilization rises to 94.8%. This suggests the base network can handle moderate demand growth, but it becomes much closer to capacity limits.

Overall, the four-facility solution is not only cost-effective but also more robust than the three-facility alternative.

---

## Visual Outputs

The project produces the following visual outputs:

### Facility Assignment Map

```text
outputs/facility_assignment_map.png
```

This plot shows:

* All candidate facilities
* Selected facilities
* Customer demand zones
* Assignment lines from customers to selected facilities

### Scenario Total Cost Chart

```text
outputs/scenario_total_cost.png
```

This chart compares total cost across all tested scenarios.

### Scenario Capacity Utilization Chart

```text
outputs/scenario_capacity_utilization.png
```

This chart compares selected facility capacity utilization across scenarios.

---

## How to Run the Project

### 1. Install Required Packages

```bash
pip install pandas numpy matplotlib pulp
```

### 2. Generate Synthetic Data

```bash
python src/generate_data.py
```

### 3. Run the Optimization Model

```bash
python src/optimization_model.py
```

### 4. Generate Facility Assignment Visualization

```bash
python src/visualization.py
```

### 5. Run Scenario Analysis

```bash
python src/scenario_analysis.py
```

### 6. Generate Scenario Visualizations

```bash
python src/scenario_visualization.py
```

---

## Tools and Libraries

* Python
* Pandas
* NumPy
* PuLP
* Matplotlib

---

## Future Improvements

Planned extensions include:

* Build an interactive Streamlit dashboard.
* Allow stakeholders to adjust budget, demand growth, service radius, and maximum number of facilities.
* Add facility utilization charts.
* Add infeasibility detection and explanation.
* Compare MILP results with heuristic approaches for larger datasets.
* Add geographic map visualization using real coordinates.
* Add automated report generation for scenario comparison.

---

## Portfolio Value

This project demonstrates:

* Mixed-Integer Linear Programming formulation
* Facility location optimization
* Synthetic data generation
* Scenario analysis
* Capacity utilization analysis
* Python-based optimization modeling
* Decision-support visualization
* Stakeholder-oriented interpretation

---

## Author

Mo Moha
