
from enum import Enum
from typing import List
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Iterable
from datetime import date, timedelta

class EmployeeType(Enum):
    STANDARD = "Standard"
    WEEKEND_ONLY = "Weekend-Only"

class Shift(Enum):
    WEEKDAY_PM = "Weekday PM"
    WEEKEND_FULL = "Weekend Full"
    PH_FULL = "PH Full"

@dataclass
class Employee:
    name: str
    role: EmployeeType
    ytd_points: int = 0
    blackouts: Set[date] = field(default_factory=set)
    ph_bids: Set[date] = field(default_factory=set)
    last_ph_date: Optional[date] = None

    def is_immune(self, day: date, years_threshold: int = 2) -> bool:
        if not self.last_ph_date:
            return False
        try:
            immunity_end_date = self.last_ph_date.replace(year=self.last_ph_date.year + years_threshold)
        except ValueError:  
            immunity_end_date = self.last_ph_date.replace(year=self.last_ph_date.year + years_threshold, day=28)
        return day < immunity_end_date

    def can_work(self, day: date, shift: Shift, is_public_holiday: bool = False) -> bool:
        # 1. Availability/Blackout checks
        if day in self.blackouts:
            return False
        if is_public_holiday and self.is_immune(day):
            return False

        is_weekend = day.weekday() >= 5

        # 2. Role-Based Constraint: Weekend-Only staff 
        # (Returns False if a Weekend-Only person is checked against a Weekday shift)
        if self.role == EmployeeType.WEEKEND_ONLY and shift == Shift.WEEKDAY_PM:
            return False

        # 3. Day-to-Shift Validation (The == operator returns True or False)
        if is_public_holiday:
            return shift == Shift.PH_FULL
        
        if is_weekend:
            return shift == Shift.WEEKEND_FULL
            
        return shift == Shift.WEEKDAY_PM

