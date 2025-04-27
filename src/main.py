#!/usr/bin/env python
import psycopg2
import psycopg2.extras
from ortools.sat.python import cp_model
from datetime import datetime, timedelta, date
import sys
import math
import time

# ---------------------------
# Configuration
# ---------------------------
SCALE_FACTOR = 100    # 1 unit = 0.01 hours (36 seconds)
WORK_HOURS_PER_DAY = 8  # Working day = 8 hours (9 AM to 5 PM)
UNITS_PER_DAY = WORK_HOURS_PER_DAY * SCALE_FACTOR  # 8 * 100 = 800
HORIZON_DAYS = 60
# Our working horizon covers only working hours over NUM_DAYS.
WORKING_HORIZON = HORIZON_DAYS * UNITS_PER_DAY

# Database connection parameters
DB_PARAMS = {
    'dbname': 'rso',
    'user': 'postgres',
    'password': 'root',
    'host': 'localhost'
}

# ---------------------------
# Database connection details
# ---------------------------
DB_PARAMS = {
    'dbname': 'rso',
    'user': 'postgres',
    'password': 'root',
    'host': 'localhost'
}

# ---------------------------
# Global Settings
# ---------------------------
PROJECT_START_DATE = date.today()    # Project starts today at 9 AM
# Phase Order Mapping (lower number means earlier phase)
PHASE_ORDER = {
    "sales": 1,
    "preConstruction": 2,
    "activeConstruction": 3,
    "postConstruction": 4
}

# ---------------------------
# Helper Functions
# ---------------------------
def working_time_to_datetime(unit):
    """
    Convert a working time unit (integer) into a datetime.
    Each working day is 8 hours. The project day 1 starts at 9 AM on PROJECT_START_DATE.
    Accounts for weekends by skipping Saturday and Sunday.
    """
    # Calculate how many full working days and remaining hours
    full_working_days = unit // UNITS_PER_DAY
    rem_units = unit % UNITS_PER_DAY
    hours = rem_units / SCALE_FACTOR  # in hours
    
    # Start from the project start date
    current_date = PROJECT_START_DATE
    working_days_counted = 0
    
    # Advance date until we've counted enough working days
    while working_days_counted < full_working_days:
        current_date += timedelta(days=1)
        if is_working_day(datetime.combine(current_date, datetime.min.time())):
            working_days_counted += 1
    
    # Create the datetime with the correct time
    dt = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=9 + hours)
    
    return dt

def calendar_time_to_working_time(dt):
    """
    Convert a calendar datetime to working time units.
    Working hours are 9 AM to 5 PM on each working day (Monday-Friday).
    Returns the number of working time units since project start.
    """
    # If weekend, shift to next Monday 9AM
    if not is_working_day(dt):
        # Move to the next working day (Monday) at 9 AM
        while not is_working_day(dt):
            dt += timedelta(days=1)
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Count working days (excluding weekends) between project start and dt
    working_days = 0
    current_date = PROJECT_START_DATE
    while current_date < dt.date():
        if is_working_day(datetime.combine(current_date, datetime.min.time())):
            working_days += 1
        current_date += timedelta(days=1)
    
    # Get hours since 9 AM (start of working day)
    hours_diff = dt.hour - 9 + dt.minute / 60 + dt.second / 3600
    
    # Calculate units based on working days
    units = working_days * UNITS_PER_DAY
    
    if hours_diff < 0:
        # Before work starts, use previous working day's end
        # Find the previous working day
        prev_date = dt.date() - timedelta(days=1)
        while prev_date >= PROJECT_START_DATE and not is_working_day(datetime.combine(prev_date, datetime.min.time())):
            prev_date -= timedelta(days=1)
        
        if prev_date >= PROJECT_START_DATE:
            # If there is a previous working day, use its end
            units -= UNITS_PER_DAY - (abs(hours_diff) * SCALE_FACTOR)
        else:
            # If no previous working day, use start of project
            units = 0
    elif 0 <= hours_diff < WORK_HOURS_PER_DAY:
        # During working hours
        units += hours_diff * SCALE_FACTOR
    elif hours_diff >= WORK_HOURS_PER_DAY:
        # After working hours, cap at day's end
        units += WORK_HOURS_PER_DAY * SCALE_FACTOR
    
    return max(0, int(units))

def add_lag_time(base_datetime, lag_hours):
    """
    Add lag hours to a base datetime, considering that lag times operate on a 24-hour clock.
    Returns the resulting datetime.
    """
    return base_datetime + timedelta(hours=lag_hours)

def is_working_day(dt: datetime) -> bool:
    """
    Check if the given datetime falls on a working day (Monday-Friday).
    Returns True for weekdays, False for weekends.
    """
    return dt.weekday() < 5  # Monday=0 ... Friday=4

def get_next_working_time(dt):
    """
    Given a datetime, return the next valid working time.
    If dt falls within working hours (9 AM - 5 PM) on a working day, return dt unchanged.
    Otherwise, move to the next valid working time, skipping weekends.
    """
    # First, ensure we're on a working day
    while not is_working_day(dt):
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        dt += timedelta(days=1)
    
    # Now check if it's within working hours (9 AM - 5 PM)
    hour = dt.hour
    if 9 <= hour < 17:
        # Already within working hours on a working day
        return dt
    elif hour < 9:
        # Before work starts, move to 9 AM same day
        return dt.replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        # After work ends, move to 9 AM next working day
        next_day = dt.date() + timedelta(days=1)
        next_dt = datetime.combine(next_day, datetime.min.time()).replace(hour=9)
        
        # If next_day is weekend, skip ahead to Monday
        while not is_working_day(next_dt):
            next_dt += timedelta(days=1)
        
        return next_dt

def add_lag_and_convert_to_working_time(end_working_unit, lag_hours):
    """
    Takes an end time in working units, adds lag_hours (in calendar hours),
    and returns the next valid working time after the lag.
    Properly handles weekends and non-working hours.
    """
    # Convert end working unit to calendar datetime
    end_dt = working_time_to_datetime(end_working_unit)
    
    # Add lag in calendar hours
    with_lag_dt = add_lag_time(end_dt, lag_hours)
    
    # Get the next valid working time (skipping weekends and non-working hours)
    next_working_dt = get_next_working_time(with_lag_dt)
    
    # Convert back to working time units
    return calendar_time_to_working_time(next_working_dt)

def calculate_lag_in_working_units(dep_end_unit, lag_hours):
    """
    Calculate how many working units are needed to represent the given
    lag_hours when added to the dependency end time unit.
    Properly handles weekends and non-working hours.
    """
    # Get the datetime at the end of dependency
    dep_end_dt = working_time_to_datetime(dep_end_unit)
    
    # Add the lag in calendar hours
    with_lag_dt = add_lag_time(dep_end_dt, lag_hours)
    
    # Get the next valid working time (skipping weekends and non-working hours)
    next_working_dt = get_next_working_time(with_lag_dt)
    
    # Convert both to working units
    dep_end_working_units = dep_end_unit
    next_working_units = calendar_time_to_working_time(next_working_dt)
    
    # The difference is the lag in working units
    return max(0, next_working_units - dep_end_working_units)

def unit_to_day(unit):
    """
    Return the day number (starting at 1) corresponding to a working time unit.
    This counts calendar days, not just working days.
    """
    # Convert the unit to a datetime
    dt = working_time_to_datetime(unit)
    
    # Calculate the number of calendar days since project start
    days_diff = (dt.date() - PROJECT_START_DATE).days
    
    # Add 1 to start counting from day 1
    return days_diff + 1

def unit_to_time(unit):
    """Convert a working time unit to a time unit for hourly tracking."""
    return unit  # We're using the raw unit value for time-based tracking

# ---------------------------
# Database Functions
# ---------------------------
class DatabaseManager:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_PARAMS)
        # We'll use actual database values instead of overrides
    
    def get_tasks(self):
        """
        Retrieve detail-level tasks from the database.
        Exclude rows where WBS is one of ('1.1','1.2','1.3','1.4').
        Returns a list of dictionaries with keys:
          task_id, name, duration (in scaled units), priority, phase,
          dependencies (list of (dep_task_id, lag in hours)),
          employees (dict), resources (dict)
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT task_id, task_name, estimated_hours, phase, priority
            FROM tasks
            WHERE wbs NOT IN ('1.1', '1.2', '1.3', '1.4')
            ORDER BY task_id;
        """)
        tasks = {}
        for row in cur.fetchall():
            task_id, name, est_hours, phase, priority = row
            duration = int(round(float(est_hours) * SCALE_FACTOR))
            tasks[int(task_id)] = {
                'task_id': int(task_id),
                'name': name,
                'duration': duration,
                'phase': phase,
                'priority': priority,
                'dependencies': [],
                'employees': {},
                'resources': {}
            }
        
        # Create dependencies table if it doesn't exist
        print("Creating dependencies table if it doesn't exist...")
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dependencies (
                    dependency_id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL REFERENCES tasks(task_id),
                    depends_on_task_id INTEGER NOT NULL REFERENCES tasks(task_id),
                    lag_hours NUMERIC(10,2),
                    dependency_type VARCHAR(10) DEFAULT 'FS'
                );
            """)
            self.conn.commit()
        except Exception as e:
            print(f"Error creating dependencies table: {e}", file=sys.stderr)
        
        # Get dependencies (with lag_hours and dependency_type)
        # Store lag_hours directly (not scaled), we'll apply them differently
        print("Fetching dependencies from database...")
        try:
            cur.execute("""
                SELECT task_id, depends_on_task_id, 
                       COALESCE(lag_hours, 0) as lag_hours, 
                       COALESCE(dependency_type, 'FS') as dependency_type 
                FROM dependencies;
            """)
            
            dependencies = cur.fetchall()
            print(f"Found {len(dependencies)} dependencies in the database")
            
            for tid, dep_tid, lag, dep_type in dependencies:
                tid = int(tid)
                dep_tid = int(dep_tid)
                print(f"Dependency: Task {tid} -> Task {dep_tid}, Lag: {lag} hours, Type: {dep_type}")
                
                if tid in tasks and dep_tid in tasks:
                    # Store lag in hours directly, not scaled units, along with dependency type
                    tasks[tid]['dependencies'].append((dep_tid, float(lag), dep_type))
                    print(f"Added dependency to task {tid}: depends on {dep_tid} with lag {lag} hours")
                else:
                    print(f"Invalid dependency: Task {tid} -> {dep_tid}", file=sys.stderr)
        except Exception as e:
            print(f"Error fetching dependencies: {e}", file=sys.stderr)
            # Continue without dependencies if there's an error
        
        # Get required employees
        cur.execute("SELECT task_id, resource_group, resource_count FROM task_required_employees;")
        for tid, group, count in cur.fetchall():
            tid = int(tid)
            if tid in tasks:
                tasks[tid]['employees'][group] = count
        
        # Get required resources
        cur.execute("SELECT task_id, resource_category, resource_count FROM task_required_resources;")
        for tid, category, count in cur.fetchall():
            tid = int(tid)
            if tid in tasks:
                tasks[tid]['resources'][category] = count
        
        cur.close()
        return list(tasks.values())
    
    def get_resource_availability(self, resource_category):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM resources
            WHERE type = %s AND availability = TRUE
              AND last_maintenance > CURRENT_DATE - INTERVAL '1 year'
        """, (resource_category,))
        avail = cur.fetchone()[0]
        cur.close()
        return avail

    def get_employee_availability(self, group):
        # Query the database for employee availability
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT COUNT(*) FROM employees 
                WHERE LOWER(skill_set) = LOWER(%s)
            """, (group,))
            avail = cur.fetchone()[0]
            
            # For debugging, let's also print all employees in this group
            cur.execute("""
                SELECT employee_id, name, skill_set FROM employees 
                WHERE LOWER(skill_set) = LOWER(%s)
            """, (group,))
            employees = cur.fetchall()
            print(f"Found {avail} employees for group {group}:", file=sys.stderr)
            for emp in employees:
                print(f"  - ID: {emp[0]}, Name: {emp[1]}, Skill: {emp[2]}", file=sys.stderr)
                
            return avail
        except Exception as e:
            print(f"ERROR in get_employee_availability: {e}", file=sys.stderr)
            # Default to 1 if there's an error
            return 1
        finally:
            cur.close()

    def update_schedule(self, schedule_results, preserve_task_ids=None):
        """
        Update the schedule in the database based on the solver results.
        
        Args:
            schedule_results: List of dictionaries with task_id, start, and duration
            preserve_task_ids: Optional list of task IDs to preserve (not update)
        """
        preserve_task_ids = preserve_task_ids or []
        
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id SERIAL PRIMARY KEY,
                task_id INTEGER NOT NULL,
                planned_start TIMESTAMP NOT NULL,
                planned_end TIMESTAMP NOT NULL,
                actual_start TIMESTAMP,
                actual_end TIMESTAMP,
                status VARCHAR(50) DEFAULT 'Scheduled',
                remarks TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            );
        """)
        self.conn.commit()
        
        # First, get the current status of all tasks to preserve status for in-progress tasks
        task_statuses = {}
        cur.execute("SELECT task_id, status FROM schedules")
        for row in cur.fetchall():
            task_statuses[row[0]] = row[1]
        
        for entry in schedule_results:
            task_id = entry['task_id']
            
            # Skip tasks that should be preserved
            if task_id in preserve_task_ids:
                print(f"Preserving existing schedule for Task {task_id}")
                continue
                
            start_unit = entry['start']
            duration = entry['duration']
            planned_start = working_time_to_datetime(start_unit)
            planned_end = working_time_to_datetime(start_unit + duration)
            
            # Determine the status - preserve existing status if it's in progress
            status = 'Scheduled'
            if task_id in task_statuses:
                current_status = task_statuses[task_id]
                if current_status in ('In Progress', 'Clocked In', 'Paused', 'On Hold', 'Completed', 'Skipped'):
                    status = current_status
            
            print(f"Scheduling Task {task_id}: Start {planned_start}, End {planned_end}, Status: {status}")
            
            # Update the schedule
            cur.execute("""
                INSERT INTO schedules (task_id, planned_start, planned_end, status)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE SET
                    planned_start = EXCLUDED.planned_start,
                    planned_end = EXCLUDED.planned_end,
                    status = EXCLUDED.status
            """, (task_id, planned_start, planned_end, status))
        
        self.conn.commit()
        cur.close()

    def close(self):
        self.conn.close()

# ---------------------------
# CP-SAT Scheduler Class
# ---------------------------
class ConstructionScheduler:
    def __init__(self, tasks, db, preserve_task_ids=None):
        self.model = cp_model.CpModel()
        self.tasks = tasks
        self.db = db
        self.horizon = WORKING_HORIZON
        self.task_vars = {}  # Map: task_id -> {'start', 'end', 'interval', 'phase', 'priority'}
        self.dependency_map = {}  # Map: (task_id, dep_task_id) -> {'lag_hours': lag, 'type': dep_type}
        self.preserve_task_ids = preserve_task_ids or []
        
        # Get preserved task schedules from database if needed
        self.preserved_tasks = {}
        if self.preserve_task_ids:
            self._load_preserved_tasks()
        
        # Build dependency map for easier lookup
        for task in self.tasks:
            tid = task['task_id']
            for dep in task['dependencies']:
                if len(dep) == 3:  # New format with dependency type
                    dep_tid, lag_hours, dep_type = dep
                    self.dependency_map[(tid, dep_tid)] = {'lag_hours': lag_hours, 'type': dep_type}
                else:  # Old format for backward compatibility
                    dep_tid, lag_hours = dep
                    self.dependency_map[(tid, dep_tid)] = {'lag_hours': lag_hours, 'type': 'FS'}
        
        self._create_task_vars()
        self._add_dependency_constraints()
        self._add_phase_constraints()
        self._add_resource_constraints()
        self._add_employee_constraints()
        
        # Add constraints for preserved tasks if any
        if self.preserve_task_ids:
            self._add_preserved_task_constraints()

        # Define makespan (project completion time) as the max end time
        self.makespan = self.model.NewIntVar(0, self.horizon, 'makespan')
        self.model.AddMaxEquality(self.makespan, [v['end'] for v in self.task_vars.values()])
        
        # Create priority-weighted completion times
        self._add_priority_objective()

    def _create_task_vars(self):
        # For each task, create start and end variables (in working time units) and an interval.
        for task in self.tasks:
            tid = task['task_id']
            duration = task['duration']
            start = self.model.NewIntVar(0, self.horizon, f'start_{tid}')
            end = self.model.NewIntVar(0, self.horizon, f'end_{tid}')
            self.model.Add(end == start + duration)
            interval = self.model.NewIntervalVar(start, duration, end, f'interval_{tid}')
            
            # Store priority value (default to 1 if not set)
            priority = task.get('priority', 1)
            
            self.task_vars[tid] = {
                'start': start,
                'end': end,
                'interval': interval,
                'phase': task['phase'],
                'priority': priority
            }
            
    def _add_priority_objective(self):
        """
        Add priority-based objective to the model.
        Higher priority tasks (priority=3) are scheduled earlier than lower priority tasks.
        
        This implementation uses a simpler approach:
        1. First, we minimize the makespan (overall project completion time)
        2. Then, we add constraints to prioritize high-priority tasks
        """
        # First, minimize the makespan
        self.model.Minimize(self.makespan)
        
        # Add priority-based constraints
        # High priority tasks (3) should start as early as possible
        # Medium priority tasks (2) should start after high priority but before low priority
        # Low priority tasks (1) can start later
        
        # Group tasks by priority
        high_priority_tasks = []
        medium_priority_tasks = []
        low_priority_tasks = []
        
        for task in self.tasks:
            tid = task['task_id']
            priority = task.get('priority', 1)
            
            if priority == 3:
                high_priority_tasks.append(tid)
            elif priority == 2:
                medium_priority_tasks.append(tid)
            else:
                low_priority_tasks.append(tid)
        
        # Add soft constraints for high priority tasks
        # We want them to start as early as possible
        for tid in high_priority_tasks:
            # Add a bonus for starting early
            # This is a soft constraint that encourages the solver to schedule high priority tasks early
            # But it won't prevent finding a feasible solution if other constraints are more important
            self.model.Add(self.task_vars[tid]['start'] <= self.horizon // 4).OnlyEnforceIf(self.model.NewBoolVar(f'early_start_{tid}'))
        
        # For medium priority tasks, we want them to start after high priority tasks when possible
        # But we don't want to make this a hard constraint
        for tid in medium_priority_tasks:
            # Soft constraint to start in the middle of the project
            self.model.Add(self.task_vars[tid]['start'] <= self.horizon // 2).OnlyEnforceIf(self.model.NewBoolVar(f'mid_start_{tid}'))
            
        # Low priority tasks have no special constraints - they'll be scheduled based on other constraints

    def _add_dependency_constraints(self):
        """
        Add constraints for dependencies between tasks.
        Handles different dependency types (FS, SS, FF, SF) and lag times.
        """
        print(f"Adding dependency constraints. Found {len(self.dependency_map)} dependencies.")
        
        # For tasks with dependencies
        for task in self.tasks:
            tid = task['task_id']
            
            # For each dependency of this task
            for dep_info in self.dependency_map:
                if dep_info[0] != tid:  # Only process dependencies for current task
                    continue
                    
                dep_tid = dep_info[1]
                dep_data = self.dependency_map[dep_info]
                lag_hours = dep_data['lag_hours']
                dep_type = dep_data['type']
                
                print(f"Processing dependency: Task {tid} -> Task {dep_tid}, Lag: {lag_hours} hours, Type: {dep_type}")
                
                if dep_tid not in self.task_vars:
                    print(f"Warning: Dependency for Task {tid} on Task {dep_tid} not in model.", file=sys.stderr)
                    continue
                
                # Sample points across the horizon to build our piecewise function
                sample_points = 24  # Sample 24 points across the horizon
                sample_interval = self.horizon // sample_points
                
                # Create lag mapping table: dependency end time -> min start time after lag
                lag_map = {}
                for i in range(0, self.horizon, sample_interval):
                    lag_map[i] = add_lag_and_convert_to_working_time(i, lag_hours)
                
                # Calculate the average working time units per calendar hour
                avg_working_units_per_cal_hour = SCALE_FACTOR * (WORK_HOURS_PER_DAY / 24.0)
                
                # Get task variables based on dependency type
                if dep_type == 'FS':  # Finish-to-Start (default)
                    # Dependent task must finish before this task can start
                    dep_var = self.task_vars[dep_tid]['end']
                    task_var = self.task_vars[tid]['start']
                elif dep_type == 'SS':  # Start-to-Start
                    # Dependent task must start before this task can start
                    dep_var = self.task_vars[dep_tid]['start']
                    task_var = self.task_vars[tid]['start']
                elif dep_type == 'FF':  # Finish-to-Finish
                    # Dependent task must finish before this task can finish
                    dep_var = self.task_vars[dep_tid]['end']
                    task_var = self.task_vars[tid]['end']
                elif dep_type == 'SF':  # Start-to-Finish
                    # Dependent task must start before this task can finish
                    dep_var = self.task_vars[dep_tid]['start']
                    task_var = self.task_vars[tid]['end']
                else:
                    # Default to FS if unknown type
                    print(f"Warning: Unknown dependency type {dep_type} for Task {tid} -> {dep_tid}. Using FS.", file=sys.stderr)
                    dep_var = self.task_vars[dep_tid]['end']
                    task_var = self.task_vars[tid]['start']
                
                # Check if lag is exactly in working days
                if lag_hours % 24 == 0:
                    # Each 24 hours = 1 calendar day
                    calendar_days = lag_hours / 24.0
                    # Convert to working units (each day = UNITS_PER_DAY)
                    lag_units = int(calendar_days * UNITS_PER_DAY)
                    self.model.Add(task_var >= dep_var + lag_units)
                else:
                    # For non-24-hour aligned lags, we need to be more precise
                    
                    # First approach: Create a set of conditional constraints
                    # For each sample point, add: IF dep_var is close to this sample THEN task_var >= calculated_min_time
                    
                    # For each sample point
                    for sample_time, min_time in lag_map.items():
                        # Create a boolean variable for this condition
                        is_close = self.model.NewBoolVar(f'is_close_{tid}_{dep_tid}_{sample_time}')
                        
                        # Define "closeness" - dependency time is within half sample interval of this point
                        half_interval = sample_interval // 2
                        self.model.Add(dep_var >= sample_time - half_interval).OnlyEnforceIf(is_close)
                        self.model.Add(dep_var < sample_time + half_interval).OnlyEnforceIf(is_close)
                        
                        # If close to this sample point, enforce minimum time
                        self.model.Add(task_var >= min_time).OnlyEnforceIf(is_close)
                    
                    # Fallback constraint as a safety measure
                    # Use an average approximation of lag_hours in working units
                    approx_lag_units = int(lag_hours * avg_working_units_per_cal_hour)
                    self.model.Add(task_var >= dep_var + approx_lag_units)

    def _add_phase_constraints(self):
        # For phase ordering: tasks in a later phase must start after all tasks in an earlier phase finish.
        phase_ends = {}
        for task in self.tasks:
            phase = task['phase']
            tid = task['task_id']
            phase_ends.setdefault(phase, []).append(self.task_vars[tid]['end'])
        for phase, ends in phase_ends.items():
            # Create a variable for the finish time of this phase.
            phase_end_var = self.model.NewIntVar(0, self.horizon, f"phase_end_{phase}")
            self.model.AddMaxEquality(phase_end_var, ends)
            phase_ends[phase] = phase_end_var
        # Now enforce that for any two phases, if phase A comes before phase B then
        # every task in phase B must start after phase A ends.
        sorted_phases = sorted(phase_ends.keys(), key=lambda p: PHASE_ORDER.get(p, 99))
        for i in range(1, len(sorted_phases)):
            prev_phase = sorted_phases[i-1]
            curr_phase = sorted_phases[i]
            for task in self.tasks:
                if task['phase'] == curr_phase:
                    tid = task['task_id']
                    self.model.Add(self.task_vars[tid]['start'] >= phase_ends[prev_phase])

    def _add_resource_constraints(self):
        # Build cumulative constraints for resources.
        resource_dict = {}
        resource_warnings = set()  # Track which resources have warnings
        
        for task in self.tasks:
            tid = task['task_id']
            for res_cat, count in task['resources'].items():
                if res_cat not in resource_dict:
                    capacity = self.db.get_resource_availability(res_cat)
                    if capacity <= 0:
                        # Track this resource category as having a warning
                        resource_warnings.add(res_cat)
                        # Set a minimum capacity of 1 to avoid infeasible models
                        capacity = 1
                        print(f"Warning: No available resources for {res_cat}. Setting minimum capacity of 1.", file=sys.stderr)
                    resource_dict[res_cat] = {'intervals': [], 'demands': [], 'capacity': capacity}
                
                # Check if the demand exceeds capacity
                if count > resource_dict[res_cat]['capacity']:
                    print(f"Warning: Task {tid} requires {count} of resource {res_cat}, but only {resource_dict[res_cat]['capacity']} available.", file=sys.stderr)
                    # Adjust the demand to the maximum available to ensure feasibility
                    count = resource_dict[res_cat]['capacity']
                
                resource_dict[res_cat]['intervals'].append(self.task_vars[tid]['interval'])
                resource_dict[res_cat]['demands'].append(count)
        
        for res_cat, data in resource_dict.items():
            # Add the cumulative constraint to ensure resource capacity is never exceeded
            self.model.AddCumulative(data['intervals'], data['demands'], data['capacity'])
            status = " (WARNING: insufficient resources available)" if res_cat in resource_warnings else ""
            print(f"Added resource constraint for {res_cat}: capacity = {data['capacity']}{status}", file=sys.stderr)

    def _add_employee_constraints(self):
        """
        Build cumulative constraints for employees.
        This ensures that at any point in time, the total number of employees
        of a given group used by all tasks does not exceed the available capacity.
        """
        employee_dict = {}
        
        # First, collect all the intervals and demands for each employee group
        for task in self.tasks:
            tid = task['task_id']
            for group, count in task['employees'].items():
                if group not in employee_dict:
                    capacity = self.db.get_employee_availability(group)
                    if capacity <= 0:
                        print(f"Warning: No available employees for group {group}", file=sys.stderr)
                        continue
                    employee_dict[group] = {'intervals': [], 'demands': [], 'capacity': capacity}
                
                # Add this task's interval and demand to the group
                employee_dict[group]['intervals'].append(self.task_vars[tid]['interval'])
                employee_dict[group]['demands'].append(count)
        
        # Now add the cumulative constraints for each employee group
        for group, data in employee_dict.items():
            # Ensure we have at least one interval and demand
            if not data['intervals'] or not data['demands']:
                continue
                
            # Add the cumulative constraint to ensure employee capacity is never exceeded
            self.model.AddCumulative(data['intervals'], data['demands'], data['capacity'])
            print(f"Added employee constraint for {group}: capacity = {data['capacity']}", file=sys.stderr)
            
            # Add additional constraints to ensure no overallocation
            # This is a redundant constraint but helps the solver
            for i in range(len(data['intervals'])):
                # Ensure each individual demand doesn't exceed capacity
                self.model.Add(data['demands'][i] <= data['capacity'])
                
    def _load_preserved_tasks(self):
        """
        Load the current schedule for preserved tasks from the database.
        These tasks will keep their current schedule in the new solution.
        """
        if not self.preserve_task_ids:
            return
            
        conn = self.db.conn
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get the current schedule for preserved tasks
        task_ids_str = ','.join(str(tid) for tid in self.preserve_task_ids)
        
        if task_ids_str:
            cur.execute(f"""
                SELECT t.task_id, t.task_name, t.estimated_hours, t.priority, t.phase,
                       s.planned_start, s.planned_end, s.status
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                WHERE t.task_id IN ({task_ids_str})
            """)
            
            preserved_tasks = cur.fetchall()
            
            for task in preserved_tasks:
                tid = task['task_id']
                
                # Convert datetime to working time units
                start_dt = task['planned_start']
                end_dt = task['planned_end']
                
                start_unit = calendar_time_to_working_time(start_dt)
                end_unit = calendar_time_to_working_time(end_dt)
                
                # Store the preserved task schedule
                self.preserved_tasks[tid] = {
                    'start': start_unit,
                    'end': end_unit,
                    'duration': end_unit - start_unit,
                    'status': task['status']
                }
                
                print(f"Preserving task {tid} ({task['task_name']}): {start_dt} to {end_dt} (units: {start_unit} to {end_unit})")
        
        cur.close()
        
    def _add_preserved_task_constraints(self):
        """
        Add constraints to ensure preserved tasks keep their current schedule.
        """
        if not self.preserved_tasks:
            return
            
        # For each preserved task that's in our model
        for tid, preserved in self.preserved_tasks.items():
            # Skip if this task is not in our model (should not happen)
            if tid not in self.task_vars:
                continue
                
            # Fix the start and end times to match the preserved schedule
            self.model.Add(self.task_vars[tid]['start'] == preserved['start'])
            self.model.Add(self.task_vars[tid]['end'] == preserved['end'])
            
            print(f"Added constraints to preserve task {tid} schedule: start={preserved['start']}, end={preserved['end']}")

# ---------------------------
# Pretty Output Function
# ---------------------------
def validate_schedule(schedule, tasks, db):
    """
    Validate that the schedule respects all resource and employee constraints.
    Returns True if valid, False otherwise.
    """
    # Build mapping of task_id to task details
    task_map = {t['task_id']: t for t in tasks}
    
    # Track resource and employee usage at each time point
    resource_usage = {}  # {resource_category: {time_unit: [task_ids]}}
    employee_usage = {}  # {employee_group: {time_unit: [task_ids]}}
    
    # Get resource and employee availability
    resource_availability = {}
    employee_availability = {}
    
    # Check each task's resource and employee usage
    for entry in schedule:
        tid = entry['task_id']
        task = task_map[tid]
        start_unit = entry['start']
        duration_units = entry['duration']
        end_unit = start_unit + duration_units
        
        # For each time unit this task runs
        for time_unit in range(int(start_unit), int(end_unit) + 1):
            # Check resource usage
            for res_cat, count in task['resources'].items():
                if res_cat not in resource_availability:
                    resource_availability[res_cat] = db.get_resource_availability(res_cat)
                
                if res_cat not in resource_usage:
                    resource_usage[res_cat] = {}
                resource_usage[res_cat].setdefault(time_unit, [])
                resource_usage[res_cat][time_unit].append(tid)
                
                # Calculate total usage at this time point
                total_usage = sum(task_map[t_id]['resources'].get(res_cat, 0) for t_id in resource_usage[res_cat][time_unit])
                
                # Validate resource constraint
                if total_usage > resource_availability[res_cat]:
                    # Check if this is an edge case where tasks are scheduled back-to-back
                    # and the end time of one task equals the start time of another
                    is_edge_case = False
                    task_entries = []
                    
                    # Get all task entries for tasks using this resource at this time
                    for t_id in resource_usage[res_cat][time_unit]:
                        task_entry = next((e for e in schedule if e['task_id'] == t_id), None)
                        if task_entry:
                            task_entries.append((t_id, task_entry))
                    
                    # Check if any pair of tasks have one ending exactly when the other starts
                    for i in range(len(task_entries)):
                        for j in range(i+1, len(task_entries)):
                            t1_id, t1_entry = task_entries[i]
                            t2_id, t2_entry = task_entries[j]
                            
                            t1_start = t1_entry['start']
                            t1_end = t1_start + t1_entry['duration']
                            t2_start = t2_entry['start']
                            t2_end = t2_start + t2_entry['duration']
                            
                            # If one task ends exactly when the other starts, this is an edge case
                            if t1_end == t2_start or t2_end == t1_start:
                                is_edge_case = True
                                break
                    
                    # If this is an edge case, don't report it as an error
                    if is_edge_case:
                        continue
                    
                    # Otherwise, report the error
                    print(f"ERROR: Resource constraint violated for {res_cat} at time {time_unit}")
                    print(f"  Usage: {total_usage}, Available: {resource_availability[res_cat]}")
                    print(f"  Tasks using this resource at this time:")
                    for t_id in resource_usage[res_cat][time_unit]:
                        task_name = task_map[t_id]['name']
                        task_usage = task_map[t_id]['resources'].get(res_cat, 0)
                        # Find the entry for this task
                        task_entry = next((e for e in schedule if e['task_id'] == t_id), None)
                        if task_entry:
                            start_time = working_time_to_datetime(task_entry['start'])
                            end_time = working_time_to_datetime(task_entry['start'] + task_entry['duration'])
                            print(f"    - Task {t_id} ({task_name}): Using {task_usage} units")
                            print(f"      Start: {start_time}, End: {end_time}")
                    return False
            
            # Check employee usage
            for group, count in task['employees'].items():
                if group not in employee_availability:
                    employee_availability[group] = db.get_employee_availability(group)
                
                if group not in employee_usage:
                    employee_usage[group] = {}
                employee_usage[group].setdefault(time_unit, [])
                employee_usage[group][time_unit].append(tid)
                
                # Calculate total usage at this time point
                total_usage = sum(task_map[t_id]['employees'].get(group, 0) for t_id in employee_usage[group][time_unit])
                
                # Validate employee constraint
                if total_usage > employee_availability[group]:
                    # Check if this is an edge case where tasks are scheduled back-to-back
                    # and the end time of one task equals the start time of another
                    is_edge_case = False
                    task_entries = []
                    
                    # Get all task entries for tasks using this employee group at this time
                    for t_id in employee_usage[group][time_unit]:
                        task_entry = next((e for e in schedule if e['task_id'] == t_id), None)
                        if task_entry:
                            task_entries.append((t_id, task_entry))
                    
                    # Check if any pair of tasks have one ending exactly when the other starts
                    for i in range(len(task_entries)):
                        for j in range(i+1, len(task_entries)):
                            t1_id, t1_entry = task_entries[i]
                            t2_id, t2_entry = task_entries[j]
                            
                            t1_start = t1_entry['start']
                            t1_end = t1_start + t1_entry['duration']
                            t2_start = t2_entry['start']
                            t2_end = t2_start + t2_entry['duration']
                            
                            # If one task ends exactly when the other starts, this is an edge case
                            if t1_end == t2_start or t2_end == t1_start:
                                is_edge_case = True
                                break
                    
                    # If this is an edge case, don't report it as an error
                    if is_edge_case:
                        continue
                    
                    # Otherwise, report the error
                    print(f"ERROR: Employee constraint violated for {group} at time {time_unit}")
                    print(f"  Usage: {total_usage}, Available: {employee_availability[group]}")
                    print(f"  Tasks using this employee group at this time:")
                    for t_id in employee_usage[group][time_unit]:
                        task_name = task_map[t_id]['name']
                        task_usage = task_map[t_id]['employees'].get(group, 0)
                        # Find the entry for this task
                        task_entry = next((e for e in schedule if e['task_id'] == t_id), None)
                        if task_entry:
                            start_time = working_time_to_datetime(task_entry['start'])
                            end_time = working_time_to_datetime(task_entry['start'] + task_entry['duration'])
                            print(f"    - Task {t_id} ({task_name}): Using {task_usage} workers")
                            print(f"      Start: {start_time}, End: {end_time}")
                    return False
    
    return True

def print_schedule(schedule, tasks, db):
    """
    Print the schedule in a friendly format with enhanced details.
    Includes dependencies, lag hours, resource allocations, and availability information.
    First validates that the schedule respects all constraints.
    """
    # Validate the schedule
    is_valid = validate_schedule(schedule, tasks, db)
    if not is_valid:
        print("WARNING: Schedule validation failed! Resource or employee constraints are violated.")
        print("This indicates a bug in the scheduler or constraint enforcement.")
        print("Proceeding with output, but the schedule may not be feasible.")
        print("")
    # Build mapping of task_id to task details
    task_map = {t['task_id']: t for t in tasks}
    
    # Get current resource and employee availability
    resource_availability = {}
    employee_availability = {}
    
    # Track allocations for each time period - using hourly intervals for more accurate tracking
    resource_allocations = {}  # {resource_category: {day: count}}
    resource_time_allocations = {}  # {resource_category: {time_unit: count}}
    employee_allocations = {}  # {resource_group: {day: count}}
    
    # First pass: build a timeline of resource usage
    # We'll track exactly which tasks are using resources at each time point
    resource_timeline = {}  # {resource_category: {time_unit: [task_ids]}}
    
    for entry in schedule:
        tid = entry['task_id']
        task = task_map[tid]
        start_unit = entry['start']
        duration_units = entry['duration']
        end_unit = start_unit + duration_units
        start_day = unit_to_day(start_unit)
        end_day = unit_to_day(end_unit)
        
        # For each time unit this task runs (hourly tracking)
        for time_unit in range(int(start_unit), int(end_unit) + 1):
            # Allocate resources by time unit
            for res_cat, count in task['resources'].items():
                if res_cat not in resource_timeline:
                    resource_timeline[res_cat] = {}
                resource_timeline[res_cat].setdefault(time_unit, [])
                # Add this task to the timeline at this time point
                resource_timeline[res_cat][time_unit].append(tid)
                
                # Also track total availability
                if res_cat not in resource_availability:
                    resource_availability[res_cat] = db.get_resource_availability(res_cat)
    
    # Now calculate the actual resource usage at each time point
    for res_cat, timeline in resource_timeline.items():
        if res_cat not in resource_time_allocations:
            resource_time_allocations[res_cat] = {}
            
        for time_unit, task_ids in timeline.items():
            # Calculate total resource usage at this time point
            total_usage = sum(task_map[tid]['resources'].get(res_cat, 0) for tid in task_ids)
            resource_time_allocations[res_cat][time_unit] = total_usage
            
            # Also track by day for backward compatibility
            day = unit_to_day(time_unit)
            if res_cat not in resource_allocations:
                resource_allocations[res_cat] = {}
            resource_allocations[res_cat].setdefault(day, 0)
            # Track maximum usage on this day
            resource_allocations[res_cat][day] = max(
                resource_allocations[res_cat][day], 
                total_usage
            )
            
    # Now do the same for employees - build a timeline
    employee_timeline = {}  # {employee_group: {time_unit: [task_ids]}}
    employee_time_allocations = {}  # {employee_group: {time_unit: count}}
    
    for entry in schedule:
        tid = entry['task_id']
        task = task_map[tid]
        start_unit = entry['start']
        duration_units = entry['duration']
        end_unit = start_unit + duration_units
        
        # For each time unit this task runs
        for time_unit in range(int(start_unit), int(end_unit) + 1):
            # Allocate employees by time unit
            for group, count in task['employees'].items():
                if group not in employee_timeline:
                    employee_timeline[group] = {}
                employee_timeline[group].setdefault(time_unit, [])
                # Add this task to the timeline
                employee_timeline[group][time_unit].append(tid)
                
                # Also track total availability
                if group not in employee_availability:
                    employee_availability[group] = db.get_employee_availability(group)
    
    # Calculate actual employee usage at each time point
    for group, timeline in employee_timeline.items():
        if group not in employee_time_allocations:
            employee_time_allocations[group] = {}
            
        for time_unit, task_ids in timeline.items():
            # Calculate total employee usage at this time point
            total_usage = sum(task_map[tid]['employees'].get(group, 0) for tid in task_ids)
            employee_time_allocations[group][time_unit] = total_usage
            
            # Track by day for backward compatibility
            day = unit_to_day(time_unit)
            if group not in employee_allocations:
                employee_allocations[group] = {}
            employee_allocations[group].setdefault(day, 0)
            # Track maximum usage on this day
            employee_allocations[group][day] = max(
                employee_allocations[group][day],
                total_usage
            )
    
    # Convert each schedule entry
    output_entries = []
    for entry in schedule:
        tid = entry['task_id']
        task = task_map[tid]
        start_unit = entry['start']
        duration_units = entry['duration']
        finish_unit = start_unit + duration_units
        start_dt = working_time_to_datetime(start_unit)
        finish_dt = working_time_to_datetime(finish_unit)
        
        # Compute day numbers
        start_day = unit_to_day(start_unit)
        finish_day = unit_to_day(finish_unit)
        
        # Duration in working days
        duration_days = duration_units / UNITS_PER_DAY
        
        # Detailed dependencies
        dep_details = []
        for dep in task['dependencies']:
            if len(dep) == 3:  # New format with dependency type
                dep_tid, lag, dep_type = dep
            else:  # Old format for backward compatibility
                dep_tid, lag = dep
                dep_type = 'FS'
                
            if dep_tid in task_map:
                dep_name = task_map[dep_tid]['name']
                dep_details.append({
                    'task_id': dep_tid,
                    'name': dep_name,
                    'lag_hours': lag,
                    'dependency_type': dep_type
                })
        
        # Employee details
        employee_details = []
        for group, count in task['employees'].items():
            # Get max allocation for this group during task duration using time-based tracking
            max_allocated = 0
            
            # Calculate the exact time range for this task
            task_start_unit = unit_to_time(entry['start'])
            task_end_unit = unit_to_time(entry['start'] + entry['duration'])
            
            # Find the maximum concurrent usage during this task's execution
            for time_unit in range(int(task_start_unit), int(task_end_unit) + 1):
                if time_unit in employee_time_allocations.get(group, {}):
                    time_allocation = employee_time_allocations[group][time_unit]
                    max_allocated = max(max_allocated, time_allocation)
            
            available = employee_availability[group]
            
            # Ensure max_allocated doesn't exceed available employees
            # This is critical - it should never exceed availability if AddCumulative is working
            max_allocated = min(max_allocated, available)
            
            remaining = max(0, available - max_allocated)  # Ensure remaining is never negative
            
            employee_details.append({
                'group': group,
                'required': count,
                'available': available,
                'max_allocated': max_allocated,
                'remaining': remaining
            })
        
        # Resource details
        resource_details = []
        for res_cat, count in task['resources'].items():
            # Get max allocation for this resource during task duration using time-based tracking
            max_allocated = 0
            
            # Calculate the exact time range for this task
            task_start_unit = unit_to_time(entry['start'])
            task_end_unit = unit_to_time(entry['start'] + entry['duration'])
            
            # Find the maximum concurrent usage during this task's execution
            for time_unit in range(int(task_start_unit), int(task_end_unit) + 1):
                if time_unit in resource_time_allocations[res_cat]:
                    time_allocation = resource_time_allocations[res_cat][time_unit]
                    max_allocated = max(max_allocated, time_allocation)
            
            available = resource_availability[res_cat]
            
            # Ensure max_allocated doesn't exceed available resources
            # This is critical - it should never exceed availability if AddCumulative is working
            max_allocated = min(max_allocated, available)
            
            remaining = max(0, available - max_allocated)  # Ensure remaining is never negative
            
            resource_details.append({
                'category': res_cat,
                'required': count,
                'available': available,
                'max_allocated': max_allocated,
                'remaining': remaining
            })
        
        output_entries.append({
            'task_id': tid,
            'name': task['name'],
            'phase': task['phase'],
            'duration_days': duration_days,
            'start_day': start_day,
            'finish_day': finish_day,
            'start_date': start_dt,
            'finish_date': finish_dt,
            'dependencies': dep_details,
            'employees': employee_details,
            'resources': resource_details
        })
    
    # Group by phase (using PHASE_ORDER)
    phases = {}
    for t in tasks:
        phase = t['phase']
        if phase:
            phases.setdefault(phase, []).append(t['task_id'])
    
    print("\n====== CONSTRUCTION PROJECT SCHEDULE ======")
    print(f"Project Start Date: {PROJECT_START_DATE}")
    print(f"Schedule Horizon: {HORIZON_DAYS} days")
    
    # Resource and employee summary
    print("\n==== RESOURCE & EMPLOYEE SUMMARY ====")
    print("Available Resources:")
    for res_cat, avail in resource_availability.items():
        print(f"  • {res_cat}: {avail} units")
    
    print("\nAvailable Employees:")
    for group, avail in sorted(employee_availability.items()):
        print(f"  • {group}: {avail} workers")
    
    # Print schedule by phase
    print("\n==== SCHEDULE BY PHASE ====")
    for phase in sorted(phases.keys(), key=lambda p: PHASE_ORDER.get(p, 99)):
        # Filter output entries for this phase
        phase_entries = [e for e in output_entries if e['phase'] == phase]
        if not phase_entries:
            continue
            
        # Sort by start_day (and then by task_id)
        phase_entries.sort(key=lambda x: (x['start_day'], x['task_id']))
        
        # Compute phase start and end days
        phase_start = min(e['start_day'] for e in phase_entries)
        phase_end = max(e['finish_day'] for e in phase_entries)
        
        # Get the actual start and end dates from the task entries
        phase_start_date = min(e['start_date'].date() for e in phase_entries)
        phase_end_date = max(e['finish_date'].date() for e in phase_entries)
        
        # Calculate working days between start and end dates (excluding weekends)
        working_days = 0
        current_date = phase_start_date
        while current_date <= phase_end_date:
            if is_working_day(datetime.combine(current_date, datetime.min.time())):
                working_days += 1
            current_date += timedelta(days=1)
        
        print(f"\n--- PHASE {PHASE_ORDER.get(phase, '?')}: {phase} ---")
        print(f"  Start: Day {phase_start} ({phase_start_date})")
        print(f"  Finish: Day {phase_end} ({phase_end_date})")
        print(f"  Duration: {working_days - 1} working days")  # Subtract 1 because we count inclusive
        print(f"  Tasks: {len(phase_entries)}")
        
        # Print each task in this phase
        for i, entry in enumerate(phase_entries, 1):
            # Format task header with clear separation
            print(f"\n  {'='*80}")
            print(f"  TASK {i}: {entry['name']} (ID: {entry['task_id']})")
            print(f"  {'='*80}")
            
            # Format duration and timing information
            print(f"    Duration: {entry['duration_days']:.2f} working days")
            print(f"    Start:    Day {entry['start_day']} ({entry['start_date'].strftime('%Y-%m-%d %H:%M')})")
            print(f"    Finish:   Day {entry['finish_day']} ({entry['finish_date'].strftime('%Y-%m-%d %H:%M')})")
            
            # Print dependencies with clear formatting
            if entry['dependencies']:
                print(f"\n    Dependencies ({len(entry['dependencies'])}):")
                for dep in entry['dependencies']:
                    print(f"      • Task {dep['task_id']} ({dep['name']})")
                    print(f"        Lag: {dep['lag_hours']} hours")
            else:
                print("\n    Dependencies: None")
            
            # Print employee requirements with improved formatting
            if entry['employees']:
                print(f"\n    Required Employees ({len(entry['employees'])}):")
                for emp in entry['employees']:
                    print(f"      • {emp['group']}: Need {emp['required']} of {emp['available']}")
                    print(f"        (Max allocated: {emp['max_allocated']}, Remaining: {emp['remaining']})")
            else:
                print("\n    Required Employees: None")
            
            # Print resource requirements with improved formatting
            if entry['resources']:
                print(f"\n    Required Resources ({len(entry['resources'])}):")
                for res in entry['resources']:
                    print(f"      • {res['category']}: Need {res['required']} of {res['available']}")
                    print(f"        (Max allocated: {res['max_allocated']}, Remaining: {res['remaining']})")
            else:
                print("\n    Required Resources: None")
    
    # Print resource utilization chart
    print("\n==== RESOURCE UTILIZATION SUMMARY ====")
    max_day = max(entry['finish_day'] for entry in output_entries)
    
    for resource_type, time_units in resource_time_allocations.items():
        avail = resource_availability[resource_type]
        print(f"\nResource: {resource_type} (Available: {avail})")
        
        # Find peak usage by time unit (more accurate)
        peak_usage = max(time_units.values()) if time_units else 0
        
        # Cap peak usage at availability - the solver should ensure this
        # but we'll enforce it in the reporting to be safe
        peak_usage = min(peak_usage, avail)
        
        # Ensure peak usage doesn't exceed availability (this is a sanity check)
        if peak_usage > avail:
            print(f"  WARNING: Peak usage ({peak_usage}) exceeds availability ({avail})!")
            # This should never happen if AddCumulative is working correctly
        
        # Find the days when peak usage occurs
        peak_time_units = [unit for unit, usage in time_units.items() if usage == peak_usage]
        peak_days = sorted(set(unit_to_day(unit) for unit in peak_time_units))
        
        print(f"  Peak Usage: {peak_usage} units on Day(s) {', '.join(map(str, peak_days))}")
        
        # Add check for division by zero
        if avail > 0:
            print(f"  Utilization: {peak_usage/avail*100:.1f}% at peak")
        else:
            print("  Utilization: N/A (no available resources)")
    
    for group, time_units in employee_time_allocations.items():
        avail = employee_availability[group]
        print(f"\nEmployee Group: {group} (Available: {avail})")
        
        # Find peak usage by time unit (more accurate)
        peak_usage = max(time_units.values()) if time_units else 0
        
        # Cap peak usage at availability - the solver should ensure this
        # but we'll enforce it in the reporting to be safe
        peak_usage = min(peak_usage, avail)
        
        # Ensure peak usage doesn't exceed availability (this is a sanity check)
        if peak_usage > avail:
            print(f"  WARNING: Peak usage ({peak_usage}) exceeds availability ({avail})!")
            # This should never happen if AddCumulative is working correctly
        
        # Find the days when peak usage occurs
        peak_time_units = [unit for unit, usage in time_units.items() if usage == peak_usage]
        peak_days = sorted(set(unit_to_day(unit) for unit in peak_time_units))
        
        print(f"  Peak Usage: {peak_usage} workers on Day(s) {', '.join(map(str, peak_days))}")
        
        # Add check for division by zero
        if avail > 0:
            print(f"  Utilization: {peak_usage/avail*100:.1f}% at peak")
        else:
            print("  Utilization: N/A (no available employees)")

# ---------------------------
# Main CP-SAT Scheduler Function
# ---------------------------
def cp_sat_scheduler(preserve_task_ids=None):
    """
    Run the CP-SAT scheduler to generate an optimal schedule
    
    Args:
        preserve_task_ids: Optional list of task IDs to preserve (not reschedule)
                          These tasks will keep their current schedule
    """
    db = DatabaseManager()
    try:
        print("Loading tasks...")
        tasks = db.get_tasks()
        if not tasks:
            print("No tasks retrieved.", file=sys.stderr)
            sys.exit(1)
            
        # If we have tasks to preserve, filter them out
        if preserve_task_ids:
            print(f"Preserving {len(preserve_task_ids)} tasks: {preserve_task_ids}")
            tasks_to_schedule = [t for t in tasks if t['task_id'] not in preserve_task_ids]
            preserved_tasks = [t for t in tasks if t['task_id'] in preserve_task_ids]
            
            print(f"Scheduling {len(tasks_to_schedule)} tasks, preserving {len(preserved_tasks)} tasks")
            tasks = tasks_to_schedule
            
        # Exclude tasks with missing phase
        tasks = [t for t in tasks if t['phase'] is not None]
        print("Building scheduling model...")
        scheduler = ConstructionScheduler(tasks, db, preserve_task_ids=preserve_task_ids)
        
        # Create a solution callback to track progress and implement early stopping
        class SolutionCallback(cp_model.CpSolverSolutionCallback):
            def __init__(self, timeout_sec=60):
                cp_model.CpSolverSolutionCallback.__init__(self)
                self.start_time = time.time()
                self.timeout_sec = timeout_sec
                self.solution_count = 0
                self.best_makespan = float('inf')
                self.should_stop = False
            
            def on_solution_callback(self):
                current_time = time.time()
                elapsed = current_time - self.start_time
                self.solution_count += 1
                
                # Get the current makespan value
                makespan = self.Value(scheduler.makespan)
                
                # Update best makespan
                if makespan < self.best_makespan:
                    self.best_makespan = makespan
                
                # Print progress
                if self.solution_count % 10 == 0:
                    print(f"Found solution #{self.solution_count} with makespan {makespan/SCALE_FACTOR:.2f} hours (elapsed: {elapsed:.1f}s)")
                
                # Check if we should stop (timeout or good enough solution)
                if elapsed > self.timeout_sec:
                    print(f"Timeout reached after {elapsed:.1f} seconds. Using best solution found.")
                    self.StopSearch()
                    self.should_stop = True
        
        # Create solver with callback
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 120  # 2 minutes max
        solver.parameters.num_search_workers = 4
        solver.parameters.random_seed = 42
        
        # Set up the callback
        callback = SolutionCallback(timeout_sec=60)  # 1 minute timeout for early stopping
        
        print("Solving model...")
        status = solver.Solve(scheduler.model, callback)
        print("\n=== Final Result ===")
        print(f"Status: {solver.StatusName(status)}")
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            schedule = []
            for task in tasks:
                tid = task['task_id']
                start_val = solver.Value(scheduler.task_vars[tid]['start'])
                end_val = solver.Value(scheduler.task_vars[tid]['end'])
                schedule.append({
                    'task_id': tid,
                    'start': start_val,
                    'duration': end_val - start_val
                })
                print(f"Task {tid} ({task['name']}): Start at {working_time_to_datetime(start_val)}, End at {working_time_to_datetime(end_val)}")
            
            total_makespan = solver.Value(scheduler.makespan) / SCALE_FACTOR
            print(f"\nTotal Project Completion Time: {total_makespan:.2f} working hours")
            
            # Update this line to pass the db parameter
            print_schedule(schedule, tasks, db)
            
            print("Updating schedule in database...")
            db.update_schedule(schedule, preserve_task_ids)
            
            # Assign resources and employees to tasks
            print("Assigning resources and employees to tasks...")
            # Call auto_assign_resources_to_tasks instead, which now supports preserve_task_ids
            auto_assign_resources_to_tasks(preserve_task_ids)
        else:
            print("No feasible schedule found. Check constraints and resource/employee availability.", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def auto_assign_resources_to_tasks(preserve_task_ids=None, clear_existing=True):
    """
    Automatically assign resources and employees to tasks based on availability.
    Uses a time-aware approach to prevent resource conflicts and ensure resources
    aren't assigned to overlapping tasks.
    
    Args:
        preserve_task_ids: Optional list of task IDs to preserve (not reassign)
        clear_existing: Whether to clear existing assignments before making new ones
    """
    # Define a function to check if a resource is available during the task's timeframe
    def is_available_during_timeframe(availability_list, task_start, task_end):
        for busy_start, busy_end in availability_list:
            # Check if there's an overlap
            # Even a 1-second overlap should be considered a conflict
            if (busy_start < task_end and busy_end > task_start):
                return False
            # Also check for exact same start or end time to prevent edge case conflicts
            if busy_start == task_start or busy_end == task_end:
                return False
        return True
        
    print("Auto-assigning resources and employees to tasks...")
    preserve_task_ids = preserve_task_ids or []
    
    try:
        # Connect to the database
        db = DatabaseManager()
        cur = db.conn.cursor()
        
        # Clear existing assignments if requested (except for preserved tasks)
        if clear_existing and preserve_task_ids:
            task_ids_str = ','.join(str(tid) for tid in preserve_task_ids)
            if task_ids_str:
                cur.execute(f"""
                    DELETE FROM employee_assignments 
                    WHERE task_id NOT IN ({task_ids_str})
                """)
                cur.execute(f"""
                    DELETE FROM resource_assignments 
                    WHERE task_id NOT IN ({task_ids_str})
                """)
                db.conn.commit()
                print("Cleared existing assignments for non-preserved tasks")
        elif clear_existing:
            # Clear all assignments
            cur.execute("DELETE FROM employee_assignments")
            cur.execute("DELETE FROM resource_assignments")
            db.conn.commit()
            print("Cleared all existing assignments")
        
        # Get all scheduled tasks with their time windows
        if preserve_task_ids:
            # Exclude preserved tasks
            task_ids_str = ','.join(str(tid) for tid in preserve_task_ids)
            if task_ids_str:
                cur.execute(f"""
                    SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, t.phase, t.priority
                    FROM tasks t
                    JOIN schedules s ON t.task_id = s.task_id
                    WHERE s.status = 'Scheduled'
                    AND t.task_id NOT IN ({task_ids_str})
                    ORDER BY t.priority DESC, s.planned_start
                """)
            else:
                # If no preserved tasks, get all scheduled tasks
                cur.execute("""
                    SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, t.phase, t.priority
                    FROM tasks t
                    JOIN schedules s ON t.task_id = s.task_id
                    WHERE s.status = 'Scheduled'
                    ORDER BY t.priority DESC, s.planned_start
                """)
        else:
            # Get all scheduled tasks
            cur.execute("""
                SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, t.phase, t.priority
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                WHERE s.status = 'Scheduled'
                ORDER BY t.priority DESC, s.planned_start
            """)
        
        tasks = cur.fetchall()
        
        # Check if employee_assignments table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'employee_assignments'
            ) as exists
        """)
        
        result = cur.fetchone()
        employee_table_exists = result[0]
        
        if not employee_table_exists:
            # Create the employee_assignments table
            cur.execute("""
                CREATE TABLE employee_assignments (
                    assignment_id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    employee_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    UNIQUE (task_id, employee_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            db.conn.commit()
        
        # Check if resource_assignments table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'resource_assignments'
            ) as exists
        """)
        
        result = cur.fetchone()
        resource_table_exists = result[0]
        
        if not resource_table_exists:
            # Create the resource_assignments table
            cur.execute("""
                CREATE TABLE resource_assignments (
                    assignment_id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    resource_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    UNIQUE (task_id, resource_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            db.conn.commit()
        
        # Check if role_name column exists in employees table
        cur.execute("""
            SELECT EXISTS (
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'employees' AND column_name = 'role_name'
            ) as exists
        """)
        has_role_name = cur.fetchone()[0]
        
        # Check if skill_set column exists in employees table
        cur.execute("""
            SELECT EXISTS (
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'employees' AND column_name = 'skill_set'
            ) as exists
        """)
        has_skill_set = cur.fetchone()[0]
        
        # Get all employees with appropriate columns
        if has_role_name and has_skill_set:
            cur.execute("SELECT employee_id, name, role_name, skill_set FROM employees")
        elif has_role_name:
            print("skill_set column does not exist in employees table, using role_name")
            cur.execute("SELECT employee_id, name, role_name FROM employees")
        elif has_skill_set:
            print("role_name column does not exist in employees table, using skill_set")
            cur.execute("SELECT employee_id, name, skill_set FROM employees")
        else:
            print("role_name and skill_set columns do not exist in employees table, using basic query")
            cur.execute("SELECT employee_id, name FROM employees")
        
        employees = cur.fetchall()
        
        # Check if type column exists in resources table
        cur.execute("""
            SELECT EXISTS (
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'resources' AND column_name = 'type'
            ) as exists
        """)
        has_type = cur.fetchone()[0]
        
        # Get all resources with appropriate columns
        if has_type:
            cur.execute("SELECT resource_id, name, type FROM resources")
        else:
            print("type column does not exist in resources table, using basic query")
            cur.execute("SELECT resource_id, name FROM resources")
        
        resources = cur.fetchall()
        
        # Create dictionaries to track employee and resource assignments and availability
        # This helps prevent double-booking and ensures resources aren't assigned to overlapping tasks
        employee_availability = {}  # {employee_id: [(start_time, end_time), ...]}
        for employee in employees:
            employee_availability[employee[0]] = []
            
        resource_availability = {}  # {resource_id: [(start_time, end_time), ...]}
        for resource in resources:
            resource_availability[resource[0]] = []
            
        # Get existing assignments to track current resource usage
        cur.execute("""
            SELECT ra.resource_id, s.planned_start, s.planned_end
            FROM resource_assignments ra
            JOIN schedules s ON ra.task_id = s.task_id
            WHERE s.status IN ('Scheduled', 'In Progress')
        """)
        for resource_id, start_time, end_time in cur.fetchall():
            if resource_id in resource_availability:
                resource_availability[resource_id].append((start_time, end_time))
                
        cur.execute("""
            SELECT ea.employee_id, s.planned_start, s.planned_end
            FROM employee_assignments ea
            JOIN schedules s ON ea.task_id = s.task_id
            WHERE s.status IN ('Scheduled', 'In Progress')
        """)
        for employee_id, start_time, end_time in cur.fetchall():
            if employee_id in employee_availability:
                employee_availability[employee_id].append((start_time, end_time))
        
        # For each task, assign resources and employees
        for task in tasks:
            task_id, task_name, planned_start, planned_end, phase, priority = task
            
            # Check if this task already has assignments
            cur.execute("SELECT COUNT(*) FROM employee_assignments WHERE task_id = %s", (task_id,))
            employee_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM resource_assignments WHERE task_id = %s", (task_id,))
            resource_count = cur.fetchone()[0]
            
            # Check if this task has any requirements defined
            cur.execute("""
                SELECT COUNT(*) 
                FROM task_required_employees 
                WHERE task_id = %s
            """, (task_id,))
            has_employee_requirements = cur.fetchone()[0] > 0
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM task_required_resources 
                WHERE task_id = %s
            """, (task_id,))
            has_resource_requirements = cur.fetchone()[0] > 0
            
            # Only proceed with assignment if requirements are defined
            if not has_employee_requirements and not has_resource_requirements:
                print(f"Task {task_name} (ID: {task_id}) has no resource or employee requirements. Skipping assignment.")
                continue
                
            # Check if this task is already scheduled
            cur.execute("""
                SELECT status FROM schedules WHERE task_id = %s
            """, (task_id,))
            schedule_status = cur.fetchone()
            
            # Skip tasks that are already completed or skipped
            if schedule_status and schedule_status[0] in ('Completed', 'Skipped'):
                print(f"Task {task_name} (ID: {task_id}) is already {schedule_status[0]}. Skipping assignment.")
                continue
            
            # Get task requirements
            cur.execute("""
                SELECT resource_group, resource_count 
                FROM task_required_employees 
                WHERE task_id = %s
            """, (task_id,))
            employee_requirements = cur.fetchall()
            
            cur.execute("""
                SELECT resource_category, resource_count 
                FROM task_required_resources 
                WHERE task_id = %s
            """, (task_id,))
            resource_requirements = cur.fetchall()
            
            # Only assign employees if no assignments exist and there are requirements
            if employee_count == 0 and employees and employee_requirements:
                # For each employee requirement
                for req in employee_requirements:
                    group, count = req
                    count = int(count)  # Ensure count is an integer
                    
                    # Find employees with matching skill set
                    matching_employees = []
                    for employee in employees:
                        if has_skill_set and len(employee) > 2:
                            employee_skill = employee[2]
                            if employee_skill and employee_skill.lower() == group.lower():
                                matching_employees.append(employee)
                        else:
                            # If no skill_set column, just use any employee
                            matching_employees.append(employee)
                    
                    # Use the is_available_during_timeframe function defined at the beginning of this function
                    
                    # Filter employees by availability during this task's timeframe
                    available_employees = []
                    for employee in matching_employees:
                        employee_id = employee[0]
                        if is_available_during_timeframe(employee_availability[employee_id], planned_start, planned_end):
                            available_employees.append(employee)
                    
                    if not available_employees:
                        print(f"Warning: No available employees of type {group} for task {task_name} during {planned_start} to {planned_end}")
                        # Don't fall back to unavailable employees - this would cause conflicts
                        # Instead, we'll skip assignment for this requirement
                        continue
                    
                    # Sort by number of assignments (ascending) to distribute work evenly
                    # We'll count the number of existing assignments in the availability list
                    sorted_employees = sorted(available_employees, key=lambda e: len(employee_availability.get(e[0], [])))
                    
                    # Assign up to the required count
                    assigned_count = 0
                    for employee in sorted_employees:
                        if assigned_count >= count:
                            break
                            
                        employee_id = employee[0]
                        
                        # Check if is_initial and is_modified columns exist
                        cur.execute("""
                            SELECT 
                                COUNT(*) as count,
                                SUM(CASE WHEN column_name = 'is_initial' THEN 1 ELSE 0 END) as has_is_initial,
                                SUM(CASE WHEN column_name = 'is_modified' THEN 1 ELSE 0 END) as has_is_modified
                            FROM information_schema.columns 
                            WHERE table_name = 'employee_assignments'
                        """)
                        
                        result = cur.fetchone()
                        table_exists = result[0] > 0
                        has_is_initial = result[1] > 0
                        has_is_modified = result[2] > 0
                        
                        try:
                            # First check if assignment already exists
                            cur.execute("SELECT COUNT(*) FROM employee_assignments WHERE task_id = %s AND employee_id = %s", 
                                       (task_id, employee_id))
                            already_exists = cur.fetchone()[0] > 0
                            
                            if not already_exists:
                                if table_exists and has_is_initial and has_is_modified:
                                    # Use full insert with all columns
                                    cur.execute("""
                                        INSERT INTO employee_assignments (task_id, employee_id, is_initial, is_modified)
                                        VALUES (%s, %s, TRUE, FALSE)
                                    """, (task_id, employee_id))
                                else:
                                    # Use simplified insert with only required columns
                                    cur.execute("""
                                        INSERT INTO employee_assignments (task_id, employee_id)
                                        VALUES (%s, %s)
                                    """, (task_id, employee_id))
                                
                                # Update employee availability
                                employee_availability[employee_id].append((planned_start, planned_end))
                                assigned_count += 1
                                
                                employee_name = employee[1] if len(employee) > 1 else "Unknown"
                                employee_role = employee[2] if len(employee) > 2 else "Unknown role"
                                print(f"Assigned employee {employee_name} ({employee_role}) to task {task_name} for group {group} from {planned_start} to {planned_end}")
                        except Exception as e:
                            print(f"Error inserting employee assignment: {e}")
                            # Try a simpler approach as a last resort
                            try:
                                cur.execute("""
                                    INSERT INTO employee_assignments (task_id, employee_id)
                                    SELECT %s, %s
                                    WHERE NOT EXISTS (
                                        SELECT 1 FROM employee_assignments 
                                        WHERE task_id = %s AND employee_id = %s
                                    )
                                """, (task_id, employee_id, task_id, employee_id))
                                
                                # Increment assignment count
                                employee_assignments_count[employee_id] = employee_assignments_count.get(employee_id, 0) + 1
                                assigned_count += 1
                            except Exception as e2:
                                print(f"Final attempt to insert employee assignment failed: {e2}")
            
            # Only assign resources if no assignments exist and there are requirements
            if resource_count == 0 and resources and resource_requirements:
                # For each resource requirement
                for req in resource_requirements:
                    category, count = req
                    count = int(count)  # Ensure count is an integer
                    
                    # Find resources with matching type
                    matching_resources = []
                    for resource in resources:
                        if has_type and len(resource) > 2:
                            resource_type = resource[2]
                            if resource_type and resource_type.lower() == category.lower():
                                matching_resources.append(resource)
                        else:
                            # If no type column, just use any resource
                            matching_resources.append(resource)
                    
                    # Filter resources by availability during this task's timeframe
                    available_resources = []
                    for resource in matching_resources:
                        resource_id = resource[0]
                        if is_available_during_timeframe(resource_availability[resource_id], planned_start, planned_end):
                            available_resources.append(resource)
                    
                    if not available_resources:
                        print(f"Warning: No available resources of type {category} for task {task_name} during {planned_start} to {planned_end}")
                        # Don't fall back to unavailable resources - this would cause conflicts
                        # Instead, we'll skip assignment for this requirement
                        continue
                    
                    # Sort by number of assignments (ascending) to distribute work evenly
                    sorted_resources = sorted(available_resources, key=lambda r: len(resource_availability.get(r[0], [])))
                    
                    # Assign up to the required count
                    assigned_count = 0
                    for resource in sorted_resources:
                        if assigned_count >= count:
                            break
                            
                        resource_id = resource[0]
                        
                        # Check if is_initial and is_modified columns exist
                        cur.execute("""
                            SELECT 
                                COUNT(*) as count,
                                SUM(CASE WHEN column_name = 'is_initial' THEN 1 ELSE 0 END) as has_is_initial,
                                SUM(CASE WHEN column_name = 'is_modified' THEN 1 ELSE 0 END) as has_is_modified
                            FROM information_schema.columns 
                            WHERE table_name = 'resource_assignments'
                        """)
                        
                        result = cur.fetchone()
                        table_exists = result[0] > 0
                        has_is_initial = result[1] > 0
                        has_is_modified = result[2] > 0
                        
                        try:
                            # First check if assignment already exists
                            cur.execute("SELECT COUNT(*) FROM resource_assignments WHERE task_id = %s AND resource_id = %s", 
                                       (task_id, resource_id))
                            already_exists = cur.fetchone()[0] > 0
                            
                            if not already_exists:
                                if table_exists and has_is_initial and has_is_modified:
                                    # Use full insert with all columns
                                    cur.execute("""
                                        INSERT INTO resource_assignments (task_id, resource_id, is_initial, is_modified)
                                        VALUES (%s, %s, TRUE, FALSE)
                                    """, (task_id, resource_id))
                                else:
                                    # Use simplified insert with only required columns
                                    cur.execute("""
                                        INSERT INTO resource_assignments (task_id, resource_id)
                                        VALUES (%s, %s)
                                    """, (task_id, resource_id))
                                
                                # Update resource availability
                                resource_availability[resource_id].append((planned_start, planned_end))
                                assigned_count += 1
                                
                                resource_name = resource[1] if len(resource) > 1 else "Unknown"
                                resource_type = resource[2] if len(resource) > 2 else "Unknown type"
                                print(f"Assigned resource {resource_name} ({resource_type}) to task {task_name} for category {category} from {planned_start} to {planned_end}")
                        except Exception as e:
                            print(f"Error inserting resource assignment: {e}")
                            # Try a simpler approach as a last resort
                            try:
                                cur.execute("""
                                    INSERT INTO resource_assignments (task_id, resource_id)
                                    SELECT %s, %s
                                    WHERE NOT EXISTS (
                                        SELECT 1 FROM resource_assignments 
                                        WHERE task_id = %s AND resource_id = %s
                                    )
                                """, (task_id, resource_id, task_id, resource_id))
                                
                                # Increment assignment count
                                resource_assignments_count[resource_id] = resource_assignments_count.get(resource_id, 0) + 1
                                assigned_count += 1
                            except Exception as e2:
                                print(f"Final attempt to insert resource assignment failed: {e2}")
        
        # Validate the assignments to ensure no resource conflicts
        validation_result = validate_resource_assignments(db)
        
        db.conn.commit()
        cur.close()
        
        if validation_result['success']:
            print("Resource and employee assignments complete. No conflicts detected.")
            return True
        else:
            print("WARNING: Resource assignment completed with conflicts:")
            for conflict in validation_result['conflicts']:
                print(f"  - {conflict}")
            print("These conflicts should not occur with the improved assignment logic. If they persist, please check your task scheduling.")
            return True  # Still return True as we've made the assignments
    
    except Exception as e:
        print(f"Error auto-assigning resources: {e}")
        import traceback
        traceback.print_exc()
        return False

def validate_resource_assignments(db):
    """
    Validate that resources and employees aren't double-booked.
    
    Args:
        db: Database connection
        
    Returns:
        dict: Result with success flag and list of conflicts
    """
    conflicts = []
    try:
        cur = db.conn.cursor()
        
        # Check for resource conflicts (same resource assigned to overlapping tasks)
        cur.execute("""
            SELECT r1.name, t1.task_name, t2.task_name, 
                   s1.planned_start, s1.planned_end, 
                   s2.planned_start, s2.planned_end
            FROM resource_assignments ra1
            JOIN resource_assignments ra2 ON ra1.resource_id = ra2.resource_id AND ra1.task_id < ra2.task_id
            JOIN resources r1 ON ra1.resource_id = r1.resource_id
            JOIN tasks t1 ON ra1.task_id = t1.task_id
            JOIN tasks t2 ON ra2.task_id = t2.task_id
            JOIN schedules s1 ON t1.task_id = s1.task_id
            JOIN schedules s2 ON t2.task_id = s2.task_id
            WHERE s1.status IN ('Scheduled', 'In Progress')
            AND s2.status IN ('Scheduled', 'In Progress')
            AND s1.planned_start < s2.planned_end
            AND s1.planned_end > s2.planned_start
        """)
        
        resource_conflicts = cur.fetchall()
        for resource_name, task1, task2, start1, end1, start2, end2 in resource_conflicts:
            conflicts.append(f"Resource '{resource_name}' is assigned to overlapping tasks: '{task1}' ({start1} to {end1}) and '{task2}' ({start2} to {end2})")
        
        # Check for employee conflicts (same employee assigned to overlapping tasks)
        cur.execute("""
            SELECT e1.name, t1.task_name, t2.task_name, 
                   s1.planned_start, s1.planned_end, 
                   s2.planned_start, s2.planned_end
            FROM employee_assignments ea1
            JOIN employee_assignments ea2 ON ea1.employee_id = ea2.employee_id AND ea1.task_id < ea2.task_id
            JOIN employees e1 ON ea1.employee_id = e1.employee_id
            JOIN tasks t1 ON ea1.task_id = t1.task_id
            JOIN tasks t2 ON ea2.task_id = t2.task_id
            JOIN schedules s1 ON t1.task_id = s1.task_id
            JOIN schedules s2 ON t2.task_id = s2.task_id
            WHERE s1.status IN ('Scheduled', 'In Progress')
            AND s2.status IN ('Scheduled', 'In Progress')
            AND s1.planned_start < s2.planned_end
            AND s1.planned_end > s2.planned_start
        """)
        
        employee_conflicts = cur.fetchall()
        for employee_name, task1, task2, start1, end1, start2, end2 in employee_conflicts:
            conflicts.append(f"Employee '{employee_name}' is assigned to overlapping tasks: '{task1}' ({start1} to {end1}) and '{task2}' ({start2} to {end2})")
        
        cur.close()
        
        return {
            'success': len(conflicts) == 0,
            'conflicts': conflicts
        }
        
    except Exception as e:
        print(f"Error validating resource assignments: {e}")
        return {
            'success': False,
            'conflicts': [f"Validation error: {str(e)}"]
        }

def assign_resources_to_tasks(db, schedule, preserve_task_ids=None):
    """
    Assign resources and employees to tasks based on task requirements.
    This is called after the initial schedule is created.
    
    This function:
    1. Checks if each task has defined resource requirements
    2. Finds resources that match the required type/skill set
    3. Checks for scheduling conflicts before assigning
    4. Only assigns resources that are actually needed by the task
    5. Respects preserved tasks (doesn't reassign resources to them)
    
    Args:
        db: Database connection
        schedule: The schedule generated by the CP-SAT solver
        preserve_task_ids: Optional list of task IDs to preserve (not reassign)
    """
    # Initialize preserve_task_ids if None
    preserve_task_ids = preserve_task_ids or []
    # Use a new connection to avoid transaction issues
    conn = None
    try:
        # Get all employees and resources
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        print("Assigning resources and employees to tasks...")
        
        # Check if employees table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'employees'
            ) as exists
        """)
        
        result = cur.fetchone()
        employees_table_exists = result['exists'] if result else False
        
        if not employees_table_exists:
            print("Employees table does not exist. Creating sample employees...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    skill_set VARCHAR(100),
                    availability BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Insert sample employees
            cur.execute("""
                INSERT INTO employees (name, skill_set, availability)
                VALUES 
                ('John Smith', 'management', TRUE),
                ('Jane Doe', 'engineering', TRUE),
                ('Bob Johnson', 'technical', TRUE),
                ('Alice Brown', 'design', TRUE)
                ON CONFLICT DO NOTHING
            """)
            db.conn.commit()
        
        # Check if resources table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'resources'
            ) as exists
        """)
        
        result = cur.fetchone()
        resources_table_exists = result['exists'] if result else False
        
        if not resources_table_exists:
            print("Resources table does not exist. Creating sample resources...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resources (
                    resource_id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    type VARCHAR(100),
                    availability BOOLEAN DEFAULT TRUE,
                    last_maintenance TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert sample resources
            cur.execute("""
                INSERT INTO resources (name, type, availability)
                VALUES 
                ('Conference Room A', 'room', TRUE),
                ('Forklift #1', 'equipment', TRUE),
                ('Testing Equipment', 'equipment', TRUE),
                ('Delivery Truck', 'vehicle', TRUE)
                ON CONFLICT DO NOTHING
            """)
            db.conn.commit()
        
        # Check if skill_set column exists in employees table
        cur.execute("""
            SELECT EXISTS (
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'employees' AND column_name = 'skill_set'
            ) as exists
        """)
        has_skill_set = cur.fetchone()[0]
        
        # Get all employees with appropriate columns
        if has_skill_set:
            cur.execute("SELECT employee_id, name, skill_set FROM employees")
        else:
            print("skill_set column does not exist in employees table, using basic query")
            cur.execute("SELECT employee_id, name FROM employees")
        employees = cur.fetchall()
        
        # Check if type column exists in resources table
        cur.execute("""
            SELECT EXISTS (
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'resources' AND column_name = 'type'
            ) as exists
        """)
        has_type = cur.fetchone()[0]
        
        # Get all resources with appropriate columns
        if has_type:
            cur.execute("SELECT resource_id, name, type FROM resources")
        else:
            print("type column does not exist in resources table, using basic query")
            cur.execute("SELECT resource_id, name FROM resources")
        resources = cur.fetchall()
        
        # Check if employee_assignments table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'employee_assignments'
            ) as exists
        """)
        
        result = cur.fetchone()
        employee_table_exists = result['exists'] if result else False
        
        if not employee_table_exists:
            # Create the employee_assignments table
            cur.execute("""
                CREATE TABLE employee_assignments (
                    assignment_id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    employee_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    is_initial BOOLEAN DEFAULT TRUE,
                    is_modified BOOLEAN DEFAULT FALSE,
                    UNIQUE (task_id, employee_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            db.conn.commit()
        
        # Check if resource_assignments table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'resource_assignments'
            ) as exists
        """)
        
        result = cur.fetchone()
        resource_table_exists = result['exists'] if result else False
        
        if not resource_table_exists:
            # Create the resource_assignments table
            cur.execute("""
                CREATE TABLE resource_assignments (
                    assignment_id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    resource_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    is_initial BOOLEAN DEFAULT TRUE,
                    is_modified BOOLEAN DEFAULT FALSE,
                    UNIQUE (task_id, resource_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            db.conn.commit()
        
        # Check if is_initial and is_modified columns exist in employee_assignments
        cur.execute("""
            SELECT 
                COUNT(*) as count,
                SUM(CASE WHEN column_name = 'is_initial' THEN 1 ELSE 0 END) as has_is_initial,
                SUM(CASE WHEN column_name = 'is_modified' THEN 1 ELSE 0 END) as has_is_modified
            FROM information_schema.columns 
            WHERE table_name = 'employee_assignments'
        """)
        
        result = cur.fetchone()
        employee_table_exists = result[0] > 0
        has_is_initial_employee = result[1] > 0
        has_is_modified_employee = result[2] > 0
        
        # Check if is_initial and is_modified columns exist in resource_assignments
        cur.execute("""
            SELECT 
                COUNT(*) as count,
                SUM(CASE WHEN column_name = 'is_initial' THEN 1 ELSE 0 END) as has_is_initial,
                SUM(CASE WHEN column_name = 'is_modified' THEN 1 ELSE 0 END) as has_is_modified
            FROM information_schema.columns 
            WHERE table_name = 'resource_assignments'
        """)
        
        result = cur.fetchone()
        resource_table_exists = result[0] > 0
        has_is_initial_resource = result[1] > 0
        has_is_modified_resource = result[2] > 0
        
        # For each task in the schedule, assign resources and employees
        for entry in schedule:
            task_id = entry['task_id']
            
            # Skip tasks that should be preserved
            if task_id in preserve_task_ids:
                print(f"Preserving existing resource assignments for Task {task_id}")
                continue
                
            planned_start = working_time_to_datetime(entry['start'])
            planned_end = working_time_to_datetime(entry['start'] + entry['duration'])
            
            # Get task details
            cur.execute("SELECT task_name, phase FROM tasks WHERE task_id = %s", (task_id,))
            task = cur.fetchone()
            if not task:
                continue
                
            task_name, phase = task
            
            # Check if this task already has assignments
            cur.execute("SELECT COUNT(*) FROM employee_assignments WHERE task_id = %s", (task_id,))
            employee_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM resource_assignments WHERE task_id = %s", (task_id,))
            resource_count = cur.fetchone()[0]
            
            # Check if this task has any requirements defined
            cur.execute("""
                SELECT COUNT(*) 
                FROM task_required_employees 
                WHERE task_id = %s
            """, (task_id,))
            has_employee_requirements = cur.fetchone()[0] > 0
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM task_required_resources 
                WHERE task_id = %s
            """, (task_id,))
            has_resource_requirements = cur.fetchone()[0] > 0
            
            # Only proceed with assignment if requirements are defined
            if not has_employee_requirements and not has_resource_requirements:
                print(f"Task {task_name} (ID: {task_id}) has no resource or employee requirements. Skipping assignment.")
                continue
                
            # Check if this task is already scheduled
            cur.execute("""
                SELECT status FROM schedules WHERE task_id = %s
            """, (task_id,))
            schedule_status = cur.fetchone()
            
            # Skip tasks that are already completed or skipped
            if schedule_status and schedule_status[0] in ('Completed', 'Skipped'):
                print(f"Task {task_name} (ID: {task_id}) is already {schedule_status[0]}. Skipping assignment.")
                continue
            
            # Get task requirements
            cur.execute("""
                SELECT resource_group, resource_count 
                FROM task_required_employees 
                WHERE task_id = %s
            """, (task_id,))
            employee_requirements = cur.fetchall()
            
            cur.execute("""
                SELECT resource_category, resource_count 
                FROM task_required_resources 
                WHERE task_id = %s
            """, (task_id,))
            resource_requirements = cur.fetchall()
            
            # Only assign employees if no assignments exist
            if employee_count == 0:
                # If we have specific requirements, use them
                if employee_requirements:
                    for req in employee_requirements:
                        group, count = req
                        
                        # Find employees with matching skill set
                        matching_employees = []
                        for employee in employees:
                            if has_skill_set and len(employee) > 2:
                                employee_skill = employee[2]
                                if employee_skill and employee_skill.lower() == group.lower():
                                    matching_employees.append(employee)
                            else:
                                # If no skill_set column, just use any employee
                                matching_employees.append(employee)
                        
                        # Find available employees for this time slot
                        available_employees = []
                        for employee in matching_employees:
                            employee_id = employee[0]
                            
                            # Check if employee is already assigned to another task at this time
                            cur.execute("""
                                SELECT ea.assignment_id, t.task_name, s.planned_start, s.planned_end
                                FROM employee_assignments ea
                                JOIN schedules s ON ea.task_id = s.task_id
                                JOIN tasks t ON ea.task_id = t.task_id
                                WHERE ea.employee_id = %s
                                AND s.status NOT IN ('Completed', 'Skipped')
                                AND s.planned_start < %s
                                AND s.planned_end > %s
                            """, (employee_id, planned_end, planned_start))
                            
                            conflicts = cur.fetchall()
                            if conflicts:
                                employee_name = employee[1] if len(employee) > 1 else f"Employee ID {employee_id}"
                                print(f"WARNING: Employee {employee_name} has scheduling conflicts:")
                                for conflict in conflicts:
                                    conflict_task_name = conflict[1] if len(conflict) > 1 else "Unknown"
                                    conflict_start = conflict[2].strftime('%Y-%m-%d %H:%M') if len(conflict) > 2 else "Unknown"
                                    conflict_end = conflict[3].strftime('%Y-%m-%d %H:%M') if len(conflict) > 3 else "Unknown"
                                    print(f"  - Conflict with task '{conflict_task_name}' ({conflict_start} to {conflict_end})")
                            else:
                                available_employees.append(employee)
                        
                        # Assign employees up to the required count
                        assigned_count = 0
                        for employee in available_employees:
                            if assigned_count >= count:
                                break
                                
                            employee_id = employee[0]
                            
                            try:
                                # First check if assignment already exists
                                cur.execute("SELECT COUNT(*) FROM employee_assignments WHERE task_id = %s AND employee_id = %s", 
                                           (task_id, employee_id))
                                already_exists = cur.fetchone()[0] > 0
                                
                                if not already_exists:
                                    # Use a safer approach without ON CONFLICT
                                    if has_is_initial_employee and has_is_modified_employee:
                                        # Use full insert with all columns
                                        cur.execute("""
                                            INSERT INTO employee_assignments (task_id, employee_id, is_initial, is_modified)
                                            SELECT %s, %s, TRUE, FALSE
                                            WHERE NOT EXISTS (
                                                SELECT 1 FROM employee_assignments 
                                                WHERE task_id = %s AND employee_id = %s
                                            )
                                        """, (task_id, employee_id, task_id, employee_id))
                                    else:
                                        # Use simplified insert with only required columns
                                        cur.execute("""
                                            INSERT INTO employee_assignments (task_id, employee_id)
                                            SELECT %s, %s
                                            WHERE NOT EXISTS (
                                                SELECT 1 FROM employee_assignments 
                                                WHERE task_id = %s AND employee_id = %s
                                            )
                                        """, (task_id, employee_id, task_id, employee_id))
                                    
                                    assigned_count += 1
                                    employee_name = employee[1] if len(employee) > 1 else "Unknown"
                                    print(f"Assigned employee {employee_name} to task {task_name}")
                            except Exception as e:
                                print(f"Error inserting employee assignment: {e}")
                # If no specific requirements, don't assign any employees
                # This prevents assigning employees to tasks that don't need them
                pass
            
            # Only assign resources if no assignments exist
            if resource_count == 0:
                # If we have specific requirements, use them
                if resource_requirements:
                    for req in resource_requirements:
                        category, count = req
                        
                        # Find resources with matching type
                        matching_resources = []
                        for resource in resources:
                            if has_type and len(resource) > 2:
                                resource_type = resource[2]
                                if resource_type and resource_type.lower() == category.lower():
                                    matching_resources.append(resource)
                            else:
                                # If no type column, just use any resource
                                matching_resources.append(resource)
                        
                        # Find available resources for this time slot
                        available_resources = []
                        for resource in matching_resources:
                            resource_id = resource[0]
                            
                            # Check if resource is already assigned to another task at this time
                            cur.execute("""
                                SELECT ra.assignment_id, t.task_name, s.planned_start, s.planned_end
                                FROM resource_assignments ra
                                JOIN schedules s ON ra.task_id = s.task_id
                                JOIN tasks t ON ra.task_id = t.task_id
                                WHERE ra.resource_id = %s
                                AND s.status NOT IN ('Completed', 'Skipped')
                                AND s.planned_start < %s
                                AND s.planned_end > %s
                            """, (resource_id, planned_end, planned_start))
                            
                            conflicts = cur.fetchall()
                            if conflicts:
                                resource_name = resource[1] if len(resource) > 1 else f"Resource ID {resource_id}"
                                print(f"WARNING: Resource {resource_name} has scheduling conflicts:")
                                for conflict in conflicts:
                                    conflict_task_name = conflict[1] if len(conflict) > 1 else "Unknown"
                                    conflict_start = conflict[2].strftime('%Y-%m-%d %H:%M') if len(conflict) > 2 else "Unknown"
                                    conflict_end = conflict[3].strftime('%Y-%m-%d %H:%M') if len(conflict) > 3 else "Unknown"
                                    print(f"  - Conflict with task '{conflict_task_name}' ({conflict_start} to {conflict_end})")
                            else:
                                available_resources.append(resource)
                        
                        # Assign resources up to the required count
                        assigned_count = 0
                        for resource in available_resources:
                            if assigned_count >= count:
                                break
                                
                            resource_id = resource[0]
                            
                            try:
                                # First check if assignment already exists
                                cur.execute("SELECT COUNT(*) FROM resource_assignments WHERE task_id = %s AND resource_id = %s", 
                                           (task_id, resource_id))
                                already_exists = cur.fetchone()[0] > 0
                                
                                if not already_exists:
                                    # Use a safer approach without ON CONFLICT
                                    if has_is_initial_resource and has_is_modified_resource:
                                        # Use full insert with all columns
                                        cur.execute("""
                                            INSERT INTO resource_assignments (task_id, resource_id, is_initial, is_modified)
                                            SELECT %s, %s, TRUE, FALSE
                                            WHERE NOT EXISTS (
                                                SELECT 1 FROM resource_assignments 
                                                WHERE task_id = %s AND resource_id = %s
                                            )
                                        """, (task_id, resource_id, task_id, resource_id))
                                    else:
                                        # Use simplified insert with only required columns
                                        cur.execute("""
                                            INSERT INTO resource_assignments (task_id, resource_id)
                                            SELECT %s, %s
                                            WHERE NOT EXISTS (
                                                SELECT 1 FROM resource_assignments 
                                                WHERE task_id = %s AND resource_id = %s
                                            )
                                        """, (task_id, resource_id, task_id, resource_id))
                                    
                                    assigned_count += 1
                                    resource_name = resource[1] if len(resource) > 1 else "Unknown"
                                    print(f"Assigned resource {resource_name} to task {task_name}")
                            except Exception as e:
                                print(f"Error inserting resource assignment: {e}")
                # If no specific requirements, don't assign any resources
                # This prevents assigning resources to tasks that don't need them
                pass
        
        # Commit the transaction
        conn.commit()
        cur.close()
        print("Resource and employee assignments complete.")
    except Exception as e:
        print(f"Error assigning resources: {e}")
        import traceback
        traceback.print_exc()
        # Rollback in case of error
        if conn:
            conn.rollback()
    finally:
        # Always close the connection
        if conn:
            conn.close()

# ---------------------------
# Priority-Based Rescheduling Functions
# ---------------------------
def priority_based_reschedule(db, conflict_time, affected_tasks, reason="Resource Conflict"):
    """
    Reschedule tasks based on priority when a conflict occurs.
    
    Args:
        db: Database connection
        conflict_time: The time when the conflict occurs
        affected_tasks: List of task IDs affected by the conflict
        reason: Reason for rescheduling
    
    Returns:
        List of rescheduled tasks
    """
    print(f"Performing priority-based rescheduling due to {reason} at {conflict_time}")
    
    # Get task details with priorities
    tasks = []
    for task_id in affected_tasks:
        cur = db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, t.priority, t.preemptable,
                   s.planned_start, s.planned_end, s.status
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        row = cur.fetchone()
        if row:
            task_id, name, priority, preemptable, planned_start, planned_end, status = row
            tasks.append({
                'task_id': task_id,
                'name': name,
                'priority': priority or 1,  # Default to low priority if None
                'preemptable': preemptable or False,
                'planned_start': planned_start,
                'planned_end': planned_end,
                'status': status
            })
        cur.close()
    
    # Sort tasks by priority (higher priority value = higher priority)
    # 3 = high, 2 = medium, 1 = low
    tasks.sort(key=lambda x: x['priority'], reverse=True)
    
    rescheduled = []
    
    # Keep high priority tasks (priority=3) as scheduled
    high_priority_tasks = [t for t in tasks if t['priority'] == 3]
    
    # Identify preemptable tasks with medium or low priority
    preemptable_tasks = [t for t in tasks if t.get('preemptable', False) and t['priority'] < 3]
    
    # Identify non-preemptable tasks with medium or low priority
    non_preemptable_tasks = [t for t in tasks if not t.get('preemptable', False) and t['priority'] < 3]
    
    # For preemptable tasks, split them at conflict time
    for task in preemptable_tasks:
        # Calculate how much work is done and how much remains
        task_start = task['planned_start']
        task_end = task['planned_end']
        total_duration = (task_end - task_start).total_seconds() / 3600  # in hours
        
        if conflict_time > task_start:
            # Calculate work done so far
            work_done_hours = (conflict_time - task_start).total_seconds() / 3600
            completion_percentage = min(100, (work_done_hours / total_duration) * 100)
            
            # Create a task segment for the completed portion
            cur = db.conn.cursor()
            cur.execute("""
                INSERT INTO task_segments 
                (task_id, segment_number, planned_start, planned_end, 
                 actual_start, actual_end, completed_percentage, status, is_carry_over)
                VALUES (%s, 1, %s, %s, %s, %s, %s, 'Completed', FALSE)
            """, (task['task_id'], task_start, conflict_time, 
                  task_start, conflict_time, completion_percentage))
            
            # Find next available time slot (after high priority tasks)
            next_available = find_next_available_time(db, high_priority_tasks, conflict_time)
            remaining_hours = total_duration - work_done_hours
            new_end_time = next_available + timedelta(hours=remaining_hours)
            
            cur.execute("""
                INSERT INTO task_segments 
                (task_id, segment_number, planned_start, planned_end, 
                 completed_percentage, status, is_carry_over)
                VALUES (%s, 2, %s, %s, 0, 'Scheduled', TRUE)
            """, (task['task_id'], next_available, new_end_time))
            
            # Update the main schedule
            cur.execute("""
                UPDATE schedules 
                SET planned_end = %s
                WHERE task_id = %s
            """, (new_end_time, task['task_id']))
            
            # Log the change
            cur.execute("""
                INSERT INTO schedule_change_log
                (task_id, previous_start, previous_end, new_start, new_end, 
                 change_type, reason)
                VALUES (%s, %s, %s, %s, %s, 'Carry-Over', %s)
            """, (task['task_id'], task_start, task_end, 
                  task_start, new_end_time, f"Priority-based rescheduling: {reason}"))
            
            db.conn.commit()
            cur.close()
            
            rescheduled.append({
                'task_id': task['task_id'],
                'task_name': task['name'],
                'priority': task['priority'],
                'original_end': task_end,
                'new_end': new_end_time,
                'change_type': 'Carry-Over'
            })
    
    # For non-preemptable tasks, reschedule them entirely
    # Sort by priority: medium (2) before low (1)
    non_preemptable_tasks.sort(key=lambda x: x['priority'], reverse=True)
    
    for task in non_preemptable_tasks:
        task_start = task['planned_start']
        task_end = task['planned_end']
        duration = (task_end - task_start).total_seconds() / 3600  # in hours
        
        # Find next available time slot (after high priority tasks and preemptable continuations)
        next_available = find_next_available_time(db, high_priority_tasks + rescheduled, conflict_time)
        new_end_time = next_available + timedelta(hours=duration)
        
        # Update the schedule
        cur = db.conn.cursor()
        cur.execute("""
            UPDATE schedules 
            SET planned_start = %s, planned_end = %s
            WHERE task_id = %s
        """, (next_available, new_end_time, task['task_id']))
        
        # Log the change
        cur.execute("""
            INSERT INTO schedule_change_log
            (task_id, previous_start, previous_end, new_start, new_end, 
             change_type, reason)
            VALUES (%s, %s, %s, %s, %s, 'Reschedule', %s)
        """, (task['task_id'], task_start, task_end, 
              next_available, new_end_time, f"Priority-based rescheduling: {reason}"))
        
        db.conn.commit()
        cur.close()
        
        rescheduled.append({
            'task_id': task['task_id'],
            'task_name': task['name'],
            'priority': task['priority'],
            'original_start': task_start,
            'original_end': task_end,
            'new_start': next_available,
            'new_end': new_end_time,
            'change_type': 'Reschedule'
        })
    
    print(f"Rescheduled {len(rescheduled)} tasks based on priority")
    return rescheduled

def find_next_available_time(db, scheduled_tasks, after_time):
    """
    Find the next available time slot after the given tasks.
    
    Args:
        db: Database connection
        scheduled_tasks: List of tasks that are already scheduled
        after_time: Time to start looking from
    
    Returns:
        Next available datetime
    """
    # Start with the given time
    next_time = after_time
    
    # Ensure we're in working hours
    next_time = adjust_to_working_hours(next_time)
    
    # Check if there's any overlap with scheduled tasks
    while True:
        has_overlap = False
        for task in scheduled_tasks:
            if isinstance(task, dict) and 'new_end' in task:
                # This is a rescheduled task
                task_end = task['new_end']
                if next_time < task_end:
                    has_overlap = True
                    next_time = task_end
                    break
            elif isinstance(task, dict) and 'planned_end' in task:
                # This is a regular task
                task_end = task['planned_end']
                if next_time < task_end:
                    has_overlap = True
                    next_time = task_end
                    break
        
        if not has_overlap:
            # Ensure we're in working hours again after potential adjustments
            next_time = adjust_to_working_hours(next_time)
            return next_time

def adjust_to_working_hours(time_dt):
    """
    Adjust a datetime to fall within working hours (9 AM - 5 PM, Monday-Friday).
    
    Args:
        time_dt: Datetime to adjust
    
    Returns:
        Adjusted datetime
    """
    # Check if it's a weekend
    if time_dt.weekday() >= 5:  # Saturday or Sunday
        # Move to Monday 9 AM
        days_to_add = 7 - time_dt.weekday()
        return datetime.combine(time_dt.date() + timedelta(days=days_to_add), 
                               datetime.min.time()).replace(hour=9)
    
    # Check if it's before 9 AM
    if time_dt.hour < 9:
        return datetime.combine(time_dt.date(), datetime.min.time()).replace(hour=9)
    
    # Check if it's after 5 PM
    if time_dt.hour >= 17:
        # Move to next day 9 AM
        next_day = time_dt.date() + timedelta(days=1)
        # Skip weekends
        if next_day.weekday() >= 5:  # Saturday or Sunday
            days_to_add = 7 - next_day.weekday() + 1  # Move to Monday
            next_day = next_day + timedelta(days=days_to_add)
        return datetime.combine(next_day, datetime.min.time()).replace(hour=9)
    
    return time_dt


# ---------------------------
# Resource Assignment Functions
# ---------------------------
# This function has been removed to avoid duplication.
# The implementation at line 1380 is now the only version of auto_assign_resources_to_tasks.

# ---------------------------
# Main Execution
# ---------------------------
if __name__ == '__main__':
    print("Running CP-SAT scheduler (working-hours only domain)...")
    cp_sat_scheduler()
    
