from ortools.sat.python import cp_model
from typing import List, Dict, Set
from datetime import date
from .models import Employee, Shift, EmployeeType
import pandas as pd

class RosterSolver:
    def __init__(self, employees: List[Employee], date_range: List[date], public_holidays: Set[date]):
        self.employees = employees
        self.date_range = date_range
        self.public_holidays = public_holidays
        self.model = cp_model.CpModel()
        self.variables = {} 
        self.errors = []

    def _get_shifts_for_day(self, d: date) -> List[Shift]:
        """Returns the specific shifts available for a given date type."""
        if d in self.public_holidays:
            return [Shift.PH_FULL]
        if d.weekday() >= 5: # Saturday / Sunday
            return [Shift.WEEKEND_FULL]
        else:
            return [Shift.WEEKDAY_PM]

    def _create_variables(self):
        """Generates boolean variables for valid Employee-Day-Shift combinations."""
        for d in self.date_range:
            available_shifts = self._get_shifts_for_day(d)
            is_ph = d in self.public_holidays

            for s in available_shifts:
                for emp in self.employees:
                    if emp.can_work(d, s, is_public_holiday=is_ph):
                        var_name = f"{emp.name}_{d}_{s.name}"
                        self.variables[(emp.name, d, s)] = self.model.NewBoolVar(var_name)

    def _add_coverage_constraints(self):
        """Ensures every shift on every day is filled by exactly one person."""
        for d in self.date_range:
            for s in self._get_shifts_for_day(d):
                relevant_vars = [
                    self.variables[(emp.name, d, s)]
                    for emp in self.employees
                    if (emp.name, d, s) in self.variables
                ]
                
                if relevant_vars:
                    self.model.Add(sum(relevant_vars) == 1)
                else:
                    err_msg = f"❌ Impossible to fill: {d.strftime('%Y-%m-%d')} ({s.name}). Reason: No eligible employees available."
                    self.errors.append(err_msg)

    def _add_rest_constraints(self):
        """Mandatory 1-day rest: If an employee works today, they cannot work tomorrow."""
        for emp in self.employees:
            for i in range(len(self.date_range) - 1):
                today = self.date_range[i]
                tomorrow = self.date_range[i + 1]
                
                today_vars = [self.variables[emp.name, today, s] 
                             for s in self._get_shifts_for_day(today)
                             if (emp.name, today, s) in self.variables]
                
                tomorrow_vars = [self.variables[emp.name, tomorrow, s]
                                for s in self._get_shifts_for_day(tomorrow)
                                if (emp.name, tomorrow, s) in self.variables]
                
                if today_vars and tomorrow_vars:
                    # Logic: Sum of (Worked Today + Worked Tomorrow) <= 1
                    self.model.Add(sum(today_vars) + sum(tomorrow_vars) <= 1)

    def _add_ph_bidding_constraints(self):
        """Prioritizes employees who bid for specific Public Holidays."""
        for d in self.date_range:
            if d in self.public_holidays:
                for s in self._get_shifts_for_day(d):
                    bidders = [emp for emp in self.employees if d in emp.ph_bids]
                    bidder_vars = [self.variables[(emp.name, d, s)] 
                                  for emp in bidders if (emp.name, d, s) in self.variables]

                    if bidder_vars:
                        # If there are bidders, one of them MUST get the shift
                        self.model.Add(sum(bidder_vars) == 1)

    def _set_fairness_objective(self):
        """Minimizes the spread between the highest and lowest total point scores."""
        weights = {
            Shift.WEEKDAY_PM: 10,
            Shift.WEEKEND_FULL: 15,
            Shift.PH_FULL: 15
        }
        
        employee_totals = []
        for emp in self.employees:
            total_points = emp.ytd_points * 10
            for (emp_name, d, s), var in self.variables.items():
                if emp_name == emp.name:
                    total_points += var * weights.get(s, 10)
            employee_totals.append(total_points)

        max_pts = self.model.NewIntVar(0, 100000, "max_pts")
        min_pts = self.model.NewIntVar(0, 100000, "min_pts")
        
        for total in employee_totals:
            self.model.Add(max_pts >= total)
            self.model.Add(min_pts <= total)

        self.model.Minimize(max_pts - min_pts)

    def solve(self):
        self._create_variables()
        self._add_coverage_constraints()
        if self.errors:
            return None, None, self.errors

        self._add_rest_constraints()  
        self._add_ph_bidding_constraints()
        self._set_fairness_objective()
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        status = solver.Solve(self.model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            roster_results = []
            for (emp_name, d, s), var in self.variables.items():
                if solver.Value(var) == 1:
                    roster_results.append({
                        "Date": d,
                        "Day": d.strftime('%A'),
                        "Employee": emp_name,
                        "Shift": s.name
                    })
            
            summary_results = []
            weights = {Shift.WEEKDAY_PM: 10, Shift.WEEKEND_FULL: 15, Shift.PH_FULL: 15}
            for emp in self.employees:
                new_points = 0
                for (emp_name, d, s), var in self.variables.items():
                    if emp_name == emp.name and solver.Value(var) == 1:
                        new_points += weights.get(s, 10)
                
                summary_results.append({
                    "Employee": emp.name,
                    "Starting Points": emp.ytd_points,
                    "Points Earned": new_points / 10,
                    "Total Points": emp.ytd_points + (new_points / 10)
                })
                
            return pd.DataFrame(roster_results), pd.DataFrame(summary_results), []
        
        return None, None, ["⚠️ Logic Conflict: Constraints are too tight to find a fair balance."]