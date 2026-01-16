from ortools.sat.python import cp_model
from typing import List, Dict, Set
from datetime import date
from .models import Employee, Shift
from ortools.sat.python import cp_model
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

        if d in self.public_holidays:
            return [Shift.PH_AM, Shift.PH_PM]
        
        if d.weekday() >= 5: #Saturday / Sunday
            return [Shift.WEEKEND_AM, Shift.WEEKEND_PM]
        else:
            return [Shift.WEEKDAY_PM]

    def _create_variables(self):
        
        for d in self.date_range:
            available_shifts = self._get_shifts_for_day(d)
            is_ph = d in self.public_holidays

            for s in available_shifts:
                for emp in self.employees:

                    if emp.can_work(d, s, is_public_holiday=is_ph):
                        var_name = f"{emp.name}_{d}_{s.name}"
                        self.variables[(emp.name, d, s)] = self.model.NewBoolVar(var_name)

    def _add_ph_bidding_constraints(self):
        for d in self.date_range:
            if d in self.public_holidays:
                for s in self._get_shifts_for_day(d):
                    bidders = [emp for emp in self.employees if d in emp.ph_bids]
                    

                    valid_bidder_vars = [
                        self.variables[(emp.name, d, s)] 
                        for emp in bidders 
                        if (emp.name, d, s) in self.variables
                    ]

                    if valid_bidder_vars:
                        self.model.Add(sum(valid_bidder_vars) == 1)

    def _add_coverage_constraints(self):
        for d in self.date_range:
            available_shifts = self._get_shifts_for_day(d)
            for s in available_shifts:
                relevant_switches = []
                for emp in self.employees:
                    if (emp.name, d, s) in self.variables:
                        relevant_switches.append(self.variables[(emp.name, d, s)])
                
                if relevant_switches:
                    self.model.Add(sum(relevant_switches) == 1)
                else:
                    err_msg = f"❌ Impossible to fill: {d.strftime('%Y-%m-%d')} ({s.name}). Reason: Impossible to fill with current restrictions."
                    self.errors.append(err_msg)
                    
    def _add_one_shift_per_day_constraint(self):
        for emp in self.employees:
            for d in self.date_range:
                # Gather all possible shift variables for this specific employee on this day
                shifts_today = []
                for s in self._get_shifts_for_day(d):
                    if (emp.name, d, s) in self.variables:
                        shifts_today.append(self.variables[(emp.name, d, s)])
                
                # Constraint: The sum of shifts worked today must be 0 or 1
                if shifts_today:
                    self.model.Add(sum(shifts_today) <= 1)

    def _add_rest_constraints(self):
        for emp in self.employees:
            for i in range(len(self.date_range) - 1):
                today = self.date_range[i]
                tomorrow = self.date_range[i + 1]
                pm_shifts = {Shift.WEEKDAY_PM, Shift.WEEKEND_PM, Shift.PH_PM} 
                today_pm_var = None
                for s in pm_shifts: 
                    if (emp.name, today, s) in self.variables: 
                        today_pm_var = self.variables[(emp.name, today, s)] 
                        break
                if today_pm_var is None:
                    continue
                
                tomorrow_switches = []
                for s_tomorrow in self._get_shifts_for_day(tomorrow): #for every switch in the the day
                    var = self.variables.get((emp.name, tomorrow, s_tomorrow)) #get the value of the switch 
                    if var is not None:
                        tomorrow_switches.append(var) #store the value of the switch in to a list
                
                if tomorrow_switches:
                    self.model.Add(today_pm_var + sum(tomorrow_switches) <= 1) 

    def _set_fairness_objective(self):
        weights = {
            Shift.WEEKDAY_PM: 10,
            Shift.WEEKDAY_AM: 10,
            Shift.WEEKEND_AM: 15,
            Shift.WEEKEND_PM: 15,
            Shift.PH_AM: 15, 
            Shift.PH_PM: 15
        }
        employee_totals = []
        for emp in self.employees:
            total_points = emp.ytd_points * 10
            for (emp_name, d, s), var in self.variables.items():
                if emp_name == emp.name:
                    weight = 15 if d in self.public_holidays else weights.get(s, 10)
                    total_points += var * weight
            employee_totals.append(total_points)

        # 1. Define the Ceiling (Max) and the Floor (Min)
        max_pts = self.model.NewIntVar(0, 100000, "max_pts")
        min_pts = self.model.NewIntVar(0, 100000, "min_pts")
        
        for total in employee_totals:
            self.model.Add(max_pts >= total)
            self.model.Add(min_pts <= total)

        
        self.model.Minimize(max_pts - min_pts) 
        pass

    def solve(self):
        self._create_variables()
        self._add_coverage_constraints()
        if self.errors:
            return None, None, self.errors

        self._add_rest_constraints()  
        self._add_ph_bidding_constraints()
        self._add_one_shift_per_day_constraint()
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
            weights = {
                Shift.WEEKDAY_PM: 10, Shift.WEEKDAY_AM: 10,
                Shift.WEEKEND_AM: 15, Shift.WEEKEND_PM: 15,
                Shift.PH_AM: 15, Shift.PH_PM: 15
            }
            for emp in self.employees:
                new_points = 0
                for (emp_name, d, s), var in self.variables.items():
                    if emp_name == emp.name and solver.Value(var) == 1:
                        new_points += weights.get(s, 10)
                
                summary_results.append({
                    "Employee": emp.name,
                    "Starting Points": emp.ytd_points,
                    "Points Earned": new_points /10,
                    "Total Points": emp.ytd_points + new_points /10
                })
                
            return pd.DataFrame(roster_results), pd.DataFrame(summary_results), []
        return None, None, ["⚠️ Logic Conflict: Constraints (Rest Rules or PH Bidding) are too tight to find a fair balance."]
        
