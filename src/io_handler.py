
import pandas as pd
from typing import List, Set
from .models import Employee, EmployeeType
from dateutil import parser
from datetime import date

def load_holidays(filepath: str) -> Set[date]:
    """Reads the Holidays sheet and returns a set of date objects."""
    try:
        # Specifying sheet_name='Holidays' is the key here
        df = pd.read_excel(filepath, sheet_name='Holidays')
        
        # We clean the dates to ensure they are Python date objects
        holiday_dates = pd.to_datetime(df['Date']).dt.date.tolist()
        
        return set(holiday_dates)
    except Exception as e:
        # If the sheet doesn't exist yet, we return an empty set 
        # so the solver just treats every day as a normal day.
        print(f"Note: No 'Holidays' sheet found or error reading it: {e}")
        return set()

def parse_dates(cell) -> Set[date]:
    # 1. Handle actual Nulls
    if pd.isna(cell):
        return set()

    # 2. Convert to string and clean it
    cell_str = str(cell).strip()
    if not cell_str or cell_str.lower() == "nan":
        return set()

    found_dates = set()
    
    # 3. Split by common separators (comma, semicolon, or even newline)
    # We replace everything with a comma first, then split
    raw_items = cell_str.replace(';', ',').replace('\n', ',').split(',')

    for item in raw_items:
        clean_item = item.strip()
        if not clean_item:
            continue
            
        try:
            # The 'fuzzy' logic handles weird spaces or formats automatically
            dt = parser.parse(clean_item, fuzzy=False)
            found_dates.add(dt.date())
        except (ValueError, OverflowError):
            print(f"⚠️ Skipping invalid date: '{clean_item}'")
            
    return found_dates

def load_employees(filepath: str) -> List[Employee]:
    # Load the excel
    df = pd.read_excel(filepath, sheet_name='Employees')
    employees = []

    for index, row in df.iterrows():
        # How do we check if the name is empty?
        # How do we turn the string 'Standard' into EmployeeType.STANDARD?
        name_raw = row.get("Name")

        if pd.isna(name_raw) or str(name_raw).strip() == "":
            print(f"Skipping row {index}: Name is missing.")
            continue
        name = str(name_raw).strip()

        team = str(row.get("Team", "")).strip()
        if not team:
            print(f"Warning: No team for {name}. Skipping row {index}.")
            continue

        role_str = str(row.get("Role", "Standard")).strip()
        try:
            role = EmployeeType(role_str)
        except ValueError:
            print(f"Warning: Invalid role '{role_str}' for {name}. Defaulting to Standard.")
            role = EmployeeType.STANDARD

        blackout_data = row.get("Blackouts(dates)") or row.get("Blackouts") or ""
        blackouts = parse_dates(blackout_data)

        ytd_raw = row.get("YTD", 0)
        ytd = int(ytd_raw) if not pd.isna(ytd_raw) else 0

        ph_bids_raw = row.get("PH Bids")
        ph_bids = parse_dates(ph_bids_raw)

        last_ph_raw = row.get("Last PH Date")
        last_ph_set = parse_dates(last_ph_raw)
        last_ph = max(last_ph_set) if last_ph_set else None

        employees.append(Employee(
            name=name,
            team=team,
            role=role,
            ytd_points=ytd,
            blackouts=blackouts,
            ph_bids=ph_bids,
            last_ph_date=last_ph
        ))

    return employees

def update_employee_points(filepath, summary_df):
    original_df = pd.read_excel(filepath)
    point_map = dict(zip(summary_df['Employee'], summary_df['Total Points']))
    original_df['YTD'] = original_df['Name'].map(point_map).fillna(original_df['YTD'])
    original_df.to_excel(filepath, index=False, sheet_name='Employees')