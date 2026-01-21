
from enum import Enum
from typing import List
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Iterable
from datetime import date, timedelta

class EmployeeType(Enum):
    STANDARD = "Standard"
    NO_PM = "No-PM"
    WEEKEND_ONLY = "Weekend-Only"

class Shift(Enum):
    WEEKDAY_AM = "Weekday AM"
    WEEKDAY_PM = "Weekday PM"
    WEEKEND_AM = "Weekend AM"
    WEEKEND_PM = "Weekend PM"
    PH_AM = "PH AM"
    PH_PM = "PH PM"


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
        if day in self.blackouts:
            return False
        
        if is_public_holiday and self.is_immune(day):
            return False

        is_weekend: bool = day.weekday() >= 5
        weekend_shifts = {Shift.WEEKEND_AM, Shift.WEEKEND_PM}
        ph_shifts = {Shift.PH_AM, Shift.PH_PM}

        if is_public_holiday:
            if shift not in ph_shifts:
                return False
        else:
            if is_weekend and shift not in weekend_shifts:
                return False
            if not is_weekend and shift in weekend_shifts:
                return False

        if self.role == EmployeeType.NO_PM:
            if shift in {Shift.WEEKDAY_PM, Shift.WEEKEND_PM, Shift.PH_PM}:
                return False
        
        if self.role == EmployeeType.WEEKEND_ONLY:
            if not is_weekend and not is_public_holiday:
                return False
            
        return True         


