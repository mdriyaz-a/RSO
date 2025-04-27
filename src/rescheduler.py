#!/usr/bin/env python
import psycopg2
from datetime import datetime, timedelta, date, time
import sys
import math
import time as time_module
from ortools.sat.python import cp_model

# Import common utilities from main.py
from main import (
    DatabaseManager, 
    ConstructionScheduler,
    working_time_to_datetime,
    calendar_time_to_working_time,
    is_working_day,
    get_next_working_time,
    SCALE_FACTOR,
    WORK_HOURS_PER_DAY,
    UNITS_PER_DAY,
    WORKING_HORIZON
)

# ---------------------------
# Rescheduling Constants
# ---------------------------
SHORT_BREAK_THRESHOLD = 30  # minutes
CUMULATIVE_BREAK_THRESHOLD = 30  # minutes
WORKING_DAY_START = time(9, 0)  # 9:00 AM
WORKING_DAY_END = time(17, 0)  # 5:00 PM

# ---------------------------
# Rescheduling Manager Class
# ---------------------------
class ReschedulingManager:
    def __init__(self, db=None):
        self.db = db if db else DatabaseManager()
        
    def close(self):
        if self.db:
            self.db.close()
            
    # ---------------------------
    # Clock In/Out Management
    # ---------------------------
    def handle_clock_in(self, task_id, timestamp, reason="Starting work"):
        """
        Handle a clock-in event for a task.
        
        Args:
            task_id: The ID of the task being started
            timestamp: When the clock-in occurred
            reason: Reason for starting work
            
        Returns:
            dict: Result of the operation
        """
        print(f"Handling clock-in for Task {task_id} at {timestamp}")
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, s.status,
                   s.actual_start, s.actual_end
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, planned_start, planned_end, status, actual_start, actual_end = task
        
        # Check if task is already completed or skipped
        if status in ['Completed', 'Skipped']:
            return {"success": False, "message": f"Cannot clock in: Task is {status}"}
        
        # Check if task is already in progress
        if status == 'In Progress' and actual_start and not actual_end:
            return {"success": False, "message": "Task is already clocked in"}
        
        # If this is a resume after a break, don't update the actual_start time
        is_resuming = status == 'Paused' and actual_start is not None
        
        if is_resuming:
            print(f"Resuming task {task_id} after a break. Keeping original start time: {actual_start}")
            # Just update the status to In Progress, but keep the original actual_start
            cur.execute("""
                UPDATE schedules
                SET status = 'In Progress', actual_end = NULL
                WHERE task_id = %s
            """, (task_id,))
        else:
            # This is a new start, update both status and actual_start
            cur.execute("""
                UPDATE schedules
                SET status = 'In Progress', actual_start = %s, actual_end = NULL
                WHERE task_id = %s
            """, (timestamp, task_id))
        
        # First, get the most recent completion percentage and accumulated minutes
        cur.execute("""
            SELECT completed_percentage, accumulated_minutes
            FROM task_progress
            WHERE task_id = %s
            ORDER BY progress_id DESC
            LIMIT 1
        """, (task_id,))
        
        current_percentage = 0
        accumulated_minutes = 0
        row = cur.fetchone()
        if row:
            current_percentage = row[0] or 0
            accumulated_minutes = row[1] or 0
            
        print(f"Resuming with accumulated minutes: {accumulated_minutes}")
        
        # Get the total accumulated minutes from all previous sessions
        cur.execute("""
            SELECT SUM(duration_minutes)
            FROM task_progress
            WHERE task_id = %s AND end_time IS NOT NULL
        """, (task_id,))
        
        total_accumulated = 0
        acc_row = cur.fetchone()
        if acc_row and acc_row[0]:
            total_accumulated = acc_row[0]
            
        print(f"Total accumulated minutes from previous sessions: {total_accumulated}")
        
        # Calculate completion percentage based on planned duration
        # Get the planned duration
        cur.execute("""
            SELECT planned_start, planned_end
            FROM schedules
            WHERE task_id = %s
        """, (task_id,))
        
        plan_row = cur.fetchone()
        if plan_row and plan_row[0] and plan_row[1]:
            planned_start, planned_end = plan_row
            
            # Convert to naive for calculation
            if hasattr(planned_start, 'tzinfo') and planned_start.tzinfo is not None:
                planned_start = planned_start.replace(tzinfo=None)
            if hasattr(planned_end, 'tzinfo') and planned_end.tzinfo is not None:
                planned_end = planned_end.replace(tzinfo=None)
            
            # Calculate planned duration in minutes
            planned_duration_minutes = max(1, (planned_end - planned_start).total_seconds() / 60)
            
            # Calculate completion percentage
            current_percentage = min(100, max(0, (total_accumulated / planned_duration_minutes) * 100))
            print(f"Planned duration: {planned_duration_minutes} minutes, Completion: {current_percentage:.2f}%")
            
        # Log the progress
        try:
            cur.execute("""
                INSERT INTO task_progress
                (task_id, start_time, status, notes, duration_minutes, created_at, updated_at, completed_percentage, accumulated_minutes)
                VALUES (%s, %s, 'In Progress', %s, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s)
            """, (task_id, timestamp, reason, current_percentage, total_accumulated))
            
            # Log the inserted row for debugging
            cur.execute("""
                SELECT * FROM task_progress
                WHERE task_id = %s
                ORDER BY progress_id DESC
                LIMIT 1
            """, (task_id,))
            
            progress_row = cur.fetchone()
            print(f"Inserted task_progress row: {progress_row}")
        except Exception as e:
            print(f"Error inserting task_progress: {e}")
            # Continue anyway - we don't want to fail the clock-in just because of the progress log
        
        self.db.conn.commit()
        
        return {
            "success": True,
            "message": f"Task {task_id} clocked in at {timestamp}",
            "task_id": task_id,
            "status": "In Progress",
            "clock_in_time": timestamp,
            "is_resuming": is_resuming,
            "original_start": actual_start,
            "accumulated_minutes": total_accumulated,
            "completed_percentage": current_percentage
        }
    
    def handle_clock_out(self, task_id, timestamp, details):
        """
        Handle a clock-out event for a task.
        
        Args:
            task_id: The ID of the task being stopped
            timestamp: When the clock-out occurred
            details: Additional details including:
                - reason: Reason for stopping work
                - completed_percentage: Percentage of task completed
                - remaining_hours: Directly specified remaining work hours
                - carry_over: Whether to create a carry-over task
            
        Returns:
            dict: Result of the operation
        """
        print(f"Handling clock-out for Task {task_id} at {timestamp}")
        
        reason = details.get('reason', 'Work completed for now')
        completed_percentage = details.get('completed_percentage', 0)
        carry_over = details.get('carry_over', False)
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, s.status,
                   s.actual_start, s.actual_end, t.estimated_hours
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, planned_start, planned_end, status, actual_start, actual_end, estimated_hours = task
        
        # Check if task is already completed or skipped
        if status in ['Completed', 'Skipped']:
            return {"success": False, "message": f"Cannot clock out: Task is {status}"}
        
        # Check if task is not in progress
        if status != 'In Progress' or not actual_start or actual_end:
            return {"success": False, "message": "Task is not currently clocked in"}
        
        # Calculate work duration
        try:
            # Make sure both timestamps are in the same format (either both naive or both aware)
            if actual_start.tzinfo is not None and timestamp.tzinfo is None:
                # Convert timestamp to aware
                timestamp = timestamp.replace(tzinfo=actual_start.tzinfo)
            elif actual_start.tzinfo is None and timestamp.tzinfo is not None:
                # Convert actual_start to aware
                actual_start = actual_start.replace(tzinfo=timestamp.tzinfo)
                
            work_duration = (timestamp - actual_start).total_seconds() / 3600  # in hours
            print(f"Work duration: {work_duration} hours")
        except Exception as e:
            print(f"Error calculating work duration: {e}")
            # Use a default duration if calculation fails
            work_duration = 0.5  # Default to 30 minutes
        
        # Calculate the duration in minutes
        duration_minutes = 0
        accumulated_minutes = 0
        try:
            # Get the start time and accumulated minutes of the current session
            cur.execute("""
                SELECT start_time, accumulated_minutes FROM task_progress
                WHERE task_id = %s AND end_time IS NULL
                ORDER BY progress_id DESC
                LIMIT 1
            """, (task_id,))
            
            session_row = cur.fetchone()
            if session_row and session_row[0]:
                start_time = session_row[0]
                
                # Convert both timestamps to naive for comparison
                if hasattr(start_time, 'tzinfo') and start_time.tzinfo is not None:
                    start_time_naive = start_time.replace(tzinfo=None)
                else:
                    start_time_naive = start_time
                    
                if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                    timestamp_naive = timestamp.replace(tzinfo=None)
                else:
                    timestamp_naive = timestamp
                
                # Calculate the duration of this session
                duration_minutes = max(0, (timestamp_naive - start_time_naive).total_seconds() / 60)
                print(f"Start time: {start_time_naive}, End time: {timestamp_naive}, Duration: {duration_minutes} minutes")
                
                # Get the total accumulated minutes from all previous sessions
                cur.execute("""
                    SELECT SUM(duration_minutes)
                    FROM task_progress
                    WHERE task_id = %s AND end_time IS NOT NULL
                """, (task_id,))
                
                prev_accumulated = 0
                prev_row = cur.fetchone()
                if prev_row and prev_row[0]:
                    prev_accumulated = prev_row[0]
                
                # Add current session duration to previously accumulated time
                accumulated_minutes = prev_accumulated + duration_minutes
                print(f"Session duration: {duration_minutes} minutes, Total accumulated: {accumulated_minutes} minutes")
                
                # Calculate completion percentage based on planned duration
                # Get the planned duration
                cur.execute("""
                    SELECT planned_start, planned_end
                    FROM schedules
                    WHERE task_id = %s
                """, (task_id,))
                
                plan_row = cur.fetchone()
                if plan_row and plan_row[0] and plan_row[1]:
                    planned_start, planned_end = plan_row
                    
                    # Convert to naive for calculation
                    if hasattr(planned_start, 'tzinfo') and planned_start.tzinfo is not None:
                        planned_start = planned_start.replace(tzinfo=None)
                    if hasattr(planned_end, 'tzinfo') and planned_end.tzinfo is not None:
                        planned_end = planned_end.replace(tzinfo=None)
                    
                    # Calculate planned duration in minutes
                    planned_duration_minutes = max(1, (planned_end - planned_start).total_seconds() / 60)
                    
                    # Calculate completion percentage
                    completed_percentage = min(100, max(0, (accumulated_minutes / planned_duration_minutes) * 100))
                    print(f"Planned duration: {planned_duration_minutes} minutes, Completion: {completed_percentage:.2f}%")
                
        except Exception as e:
            print(f"Error calculating duration: {e}")
        
        # Update the task progress - mark the current session as paused
        cur.execute("""
            UPDATE task_progress
            SET end_time = %s, status = 'Paused', updated_at = CURRENT_TIMESTAMP, 
                completed_percentage = %s, duration_minutes = %s, accumulated_minutes = %s
            WHERE task_id = %s AND end_time IS NULL
        """, (timestamp, completed_percentage, duration_minutes, accumulated_minutes, task_id))
        
        # Log the updated row for debugging
        cur.execute("""
            SELECT * FROM task_progress
            WHERE task_id = %s
            ORDER BY progress_id DESC
            LIMIT 1
        """, (task_id,))
        
        progress_row = cur.fetchone()
        print(f"Updated task_progress row: {progress_row}")
        
        # Check if it's end of day or if carry-over is requested
        is_end_of_day = timestamp.time() >= WORKING_DAY_END
        
        if completed_percentage >= 100:
            # Task is complete
            cur.execute("""
                UPDATE schedules
                SET status = 'Completed', actual_end = %s
                WHERE task_id = %s
            """, (timestamp, task_id))
            
            result = {
                "success": True,
                "message": f"Task {task_id} completed at {timestamp}",
                "task_id": task_id,
                "status": "Completed",
                "clock_out_time": timestamp
            }
        elif is_end_of_day or carry_over:
            # Handle end-of-day carry-over
            # Get remaining work hours directly from user input if available
            # Otherwise fall back to percentage-based calculation
            remaining_hours = details.get('remaining_hours')
            
            if remaining_hours is None:
                # Fall back to percentage-based calculation if not provided
                total_duration = float(estimated_hours)  # Convert Decimal to float
                remaining_hours = total_duration * (1 - completed_percentage / 100)
                print(f"No remaining_hours provided, calculated {remaining_hours} hours based on {completed_percentage}% completion")
            
            if remaining_hours > 0:
                # Find next working day at 9 AM
                next_working_day = timestamp.date() + timedelta(days=1)
                while not is_working_day(datetime.combine(next_working_day, datetime.min.time())):
                    next_working_day += timedelta(days=1)
                
                next_day_start = datetime.combine(next_working_day, WORKING_DAY_START)
                new_end_time = next_day_start + timedelta(hours=remaining_hours)
                
                # Update the schedule
                cur.execute("""
                    UPDATE schedules
                    SET status = 'Paused', actual_end = %s, planned_end = %s
                    WHERE task_id = %s
                """, (timestamp, new_end_time, task_id))
                
                # Log the change
                cur.execute("""
                    INSERT INTO schedule_change_log
                    (task_id, previous_start, previous_end, new_start, new_end, 
                     change_type, reason)
                    VALUES (%s, %s, %s, %s, %s, 'Carry-Over', %s)
                """, (task_id, planned_start, planned_end, 
                      planned_start, new_end_time, reason))
                
                # Create or update task segment for work done today
                cur.execute("""
                    SELECT COUNT(*) FROM task_segments
                    WHERE task_id = %s AND segment_number = 1
                """, (task_id,))
                
                segment_exists = cur.fetchone()[0] > 0
                
                if segment_exists:
                    # Update existing segment
                    cur.execute("""
                        UPDATE task_segments
                        SET planned_end = %s,
                            actual_end = %s,
                            completed_percentage = %s,
                            status = 'Paused'
                        WHERE task_id = %s AND segment_number = 1
                    """, (timestamp, timestamp, completed_percentage, task_id))
                else:
                    # Create a new segment
                    cur.execute("""
                        INSERT INTO task_segments 
                        (task_id, segment_number, planned_start, planned_end, 
                         actual_start, actual_end, completed_percentage, status, is_carry_over)
                        VALUES (%s, 1, %s, %s, %s, %s, %s, 'Paused', FALSE)
                    """, (task_id, planned_start, timestamp, 
                          actual_start, timestamp, completed_percentage))
                
                # Create or update carry-over segment
                cur.execute("""
                    SELECT COUNT(*) FROM task_segments
                    WHERE task_id = %s AND segment_number = 2
                """, (task_id,))
                
                segment_exists = cur.fetchone()[0] > 0
                
                if segment_exists:
                    # Update existing segment
                    cur.execute("""
                        UPDATE task_segments
                        SET planned_start = %s,
                            planned_end = %s
                        WHERE task_id = %s AND segment_number = 2
                    """, (next_day_start, new_end_time, task_id))
                else:
                    # Create a new segment
                    cur.execute("""
                        INSERT INTO task_segments 
                        (task_id, segment_number, planned_start, planned_end, 
                         completed_percentage, status, is_carry_over)
                        VALUES (%s, 2, %s, %s, 0, 'Scheduled', TRUE)
                    """, (task_id, next_day_start, new_end_time))
                
                # Reschedule dependent tasks
                self._reschedule_dependent_tasks(task_id, planned_end, new_end_time)
                
                result = {
                    "success": True,
                    "message": f"Task {task_id} paused with carry-over to {next_day_start}",
                    "task_id": task_id,
                    "status": "Paused",
                    "clock_out_time": timestamp,
                    "carry_over_start": next_day_start,
                    "carry_over_end": new_end_time,
                    "completed_percentage": completed_percentage
                }
            else:
                # No remaining work, task is complete
                cur.execute("""
                    UPDATE schedules
                    SET status = 'Completed', actual_end = %s
                    WHERE task_id = %s
                """, (timestamp, task_id))
                
                result = {
                    "success": True,
                    "message": f"Task {task_id} completed at {timestamp}",
                    "task_id": task_id,
                    "status": "Completed",
                    "clock_out_time": timestamp
                }
        else:
            # Regular clock-out without carry-over
            cur.execute("""
                UPDATE schedules
                SET status = 'Paused', actual_end = %s
                WHERE task_id = %s
            """, (timestamp, task_id))
            
            result = {
                "success": True,
                "message": f"Task {task_id} paused at {timestamp}",
                "task_id": task_id,
                "status": "Paused",
                "clock_out_time": timestamp,
                "accumulated_minutes": accumulated_minutes,
                "completed_percentage": completed_percentage,
                "duration_minutes": duration_minutes
            }
        
        self.db.conn.commit()
        return result
    
    # ---------------------------
    # Task Completion
    # ---------------------------
    def handle_complete(self, task_id, timestamp, details=None):
        """
        Handle task completion.
        
        Args:
            task_id: The ID of the task being completed
            timestamp: When the completion occurred
            details: Additional details (optional)
            
        Returns:
            dict: Result of the operation
        """
        print(f"Handling completion for Task {task_id} at {timestamp}")
        
        if details is None:
            details = {}
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, s.status,
                   s.actual_start, s.actual_end, t.estimated_hours
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, planned_start, planned_end, status, actual_start, actual_end, estimated_hours = task
        
        # Check if task is already completed or skipped
        if status in ['Completed', 'Skipped']:
            return {"success": False, "message": f"Task is already {status}"}
        
        # If task is not in progress, check if we can complete it directly
        if status != 'In Progress' and not actual_start:
            # Set actual_start to planned_start if not set
            actual_start = planned_start
            
        # Update the schedule to mark as completed
        cur.execute("""
            UPDATE schedules
            SET status = 'Completed', actual_end = %s
            WHERE task_id = %s
        """, (timestamp, task_id))
        
        # If there's an open task_progress entry, close it
        cur.execute("""
            UPDATE task_progress
            SET end_time = %s, status = 'Completed', updated_at = CURRENT_TIMESTAMP
            WHERE task_id = %s AND end_time IS NULL
        """, (timestamp, task_id))
        
        # Log the completion
        cur.execute("""
            INSERT INTO schedule_change_log
            (task_id, previous_start, previous_end, new_start, new_end, 
             change_type, reason)
            VALUES (%s, %s, %s, %s, %s, 'Complete', 'Task completed')
        """, (task_id, planned_start, planned_end, 
              actual_start or planned_start, timestamp))
        
        # Trigger a full reschedule when a task is completed
        print(f"Task {task_id} completed. Triggering full reschedule...")
        
        try:
            # Normalize timestamps for comparison or after hours
            timestamp_naive = timestamp.replace(tzinfo=None) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo else timestamp
            planned_end_naive = planned_end.replace(tzinfo=None) if hasattr(planned_end, 'tzinfo') and planned_end.tzinfo else planned_end
            
            # Check if the task was completed after working hours
            completion_time = timestamp_naive.time()
            completion_date = timestamp_naive.date()
            is_after_hours = completion_time > WORKING_DAY_END
            
            print(f"After working hours: {is_after_hours}")
            
            # Always trigger a full reschedule when a task is completed
            print(f"Task {task_id} completed at {timestamp}")
            print(f"Triggering full reschedule...")
            
            # Perform a full reschedule of all incomplete tasks
            try:
                # Get the scheduler instance
                from scheduler import Scheduler
                scheduler = Scheduler(self.db)
                
                # Get all tasks that are already completed or in progress - these will be preserved
                cur.execute("""
                    SELECT task_id
                    FROM schedules
                    WHERE status IN ('Completed', 'Skipped')
                """)
                
                preserved_tasks = [row[0] for row in cur.fetchall()]
                print(f"Preserving {len(preserved_tasks)} tasks that are completed or skipped")
                
                # Add the current task to the preserved tasks
                if task_id not in preserved_tasks:
                    preserved_tasks.append(task_id)
                
                # Run the scheduler with the list of tasks to preserve
                # Clear existing schedules for tasks that need to be rescheduled
                cur.execute("""
                    DELETE FROM schedules
                    WHERE task_id NOT IN %s
                    AND status NOT IN ('Completed', 'Skipped')
                """, (tuple(preserved_tasks) if preserved_tasks else (0,),))
                
                # Run the scheduler
                result = scheduler.schedule(preserved_tasks=preserved_tasks)
                
                # Get the rescheduled tasks
                cur.execute("""
                    SELECT s.task_id, t.task_name, s.planned_start, s.planned_end
                    FROM schedules s
                    JOIN tasks t ON s.task_id = t.task_id
                    WHERE s.task_id NOT IN %s
                    ORDER BY s.planned_start
                """, (tuple(preserved_tasks) if preserved_tasks else (0,),))
                
                rescheduled_tasks = []
                for row in cur.fetchall():
                    rescheduled_task_id, rescheduled_task_name, new_start, new_end = row
                    rescheduled_tasks.append({
                        'task_id': rescheduled_task_id,
                        'name': rescheduled_task_name,
                        'original_start': None,  # We don't have the original start time
                        'original_end': None,    # We don't have the original end time
                        'new_start': new_start,
                        'new_end': new_end,
                        'reason': 'Full reschedule after task completion'
                    })
                
                print(f"Full reschedule completed. Rescheduled {len(rescheduled_tasks)} tasks.")
                
                # Skip the rest of the rescheduling logic since we've already done a full reschedule
                self.db.conn.commit()
                
                return {
                    "success": True,
                    "message": f"Task {task_id} marked as completed at {timestamp}. Full reschedule performed.",
                    "task_id": task_id,
                    "status": "Completed",
                    "completion_time": timestamp,
                    "rescheduled_tasks": rescheduled_tasks
                }
                
            except Exception as e:
                print(f"Error in full reschedule: {e}")
                import traceback
                traceback.print_exc()
                print("Continuing with normal rescheduling logic...")
            
            # If task was completed after working hours, also reschedule all incomplete tasks for the current day
                if is_after_hours:
                    print(f"Task completed after working hours. Rescheduling all incomplete tasks for today...")
                    
                    # Get all incomplete tasks scheduled for today with their resource assignments
                    cur.execute("""
                        SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, t.estimated_hours,
                               t.priority, t.project_id
                        FROM tasks t
                        JOIN schedules s ON t.task_id = s.task_id
                        WHERE s.status NOT IN ('Completed', 'Skipped')
                        AND DATE(s.planned_start) = %s
                        AND t.task_id != %s
                        ORDER BY t.priority DESC, s.planned_start
                    """, (completion_date, task_id))
                    
                    incomplete_tasks = cur.fetchall()
                    
                    if incomplete_tasks:
                        print(f"Found {len(incomplete_tasks)} incomplete tasks for today")
                        
                        # Get the next working day
                        next_working_day = completion_date + timedelta(days=1)
                        while not is_working_day(next_working_day):
                            next_working_day += timedelta(days=1)
                        
                        next_day_start = datetime.combine(next_working_day, WORKING_DAY_START)
                        
                        # Track resource and employee assignments to avoid conflicts
                        resource_assignments = {}  # resource_id -> [(start, end), ...]
                        employee_assignments = {}  # employee_id -> [(start, end), ...]
                        
                        # Reschedule each task
                        for task in incomplete_tasks:
                            incomplete_task_id, incomplete_task_name, task_start, task_end, task_hours, task_priority, project_id = task
                            
                            # Get resource and employee assignments for this task
                            cur.execute("""
                                SELECT 'resource' as type, resource_id as id
                                FROM resource_assignments
                                WHERE task_id = %s
                                UNION
                                SELECT 'employee' as type, employee_id as id
                                FROM employee_assignments
                                WHERE task_id = %s
                            """, (incomplete_task_id, incomplete_task_id))
                            
                            assignments = cur.fetchall()
                            
                            # Calculate duration in hours
                            if task_hours:
                                # Convert Decimal to float
                                duration = float(task_hours)
                            else:
                                duration = (task_end - task_start).total_seconds() / 3600
                            
                            # Find a suitable time slot for this task
                            found_slot = False
                            current_slot_start = next_day_start
                            
                            # Try to find a slot within the next 5 working days
                            for _ in range(5):  # Try up to 5 days
                                # Calculate new end time
                                new_task_start = current_slot_start
                                new_task_end = new_task_start + timedelta(hours=duration)
                                
                                # Check if this slot works for all resources and employees
                                slot_works = True
                                
                                for assignment_type, assignment_id in assignments:
                                    if assignment_type == 'resource':
                                        if assignment_id in resource_assignments:
                                            # Check for conflicts
                                            for start, end in resource_assignments[assignment_id]:
                                                if new_task_start < end and new_task_end > start:
                                                    # Conflict found
                                                    slot_works = False
                                                    break
                                    else:  # employee
                                        if assignment_id in employee_assignments:
                                            # Check for conflicts
                                            for start, end in employee_assignments[assignment_id]:
                                                if new_task_start < end and new_task_end > start:
                                                    # Conflict found
                                                    slot_works = False
                                                    break
                                
                                if slot_works:
                                    found_slot = True
                                    break
                                else:
                                    # Try the next slot, starting 15 minutes later
                                    current_slot_start += timedelta(minutes=15)
                                    
                                    # If we've reached the end of the day, move to the next working day
                                    if current_slot_start.time() >= WORKING_DAY_END:
                                        next_day = current_slot_start.date() + timedelta(days=1)
                                        while not is_working_day(next_day):
                                            next_day += timedelta(days=1)
                                        current_slot_start = datetime.combine(next_day, WORKING_DAY_START)
                            
                            if not found_slot:
                                # If we couldn't find a slot, just use the next available time
                                new_task_start = current_slot_start
                                new_task_end = new_task_start + timedelta(hours=duration)
                                print(f"Warning: Could not find conflict-free slot for task {incomplete_task_id}. Using {new_task_start}.")
                            
                            # Update resource and employee assignments
                            for assignment_type, assignment_id in assignments:
                                if assignment_type == 'resource':
                                    if assignment_id not in resource_assignments:
                                        resource_assignments[assignment_id] = []
                                    resource_assignments[assignment_id].append((new_task_start, new_task_end))
                                else:  # employee
                                    if assignment_id not in employee_assignments:
                                        employee_assignments[assignment_id] = []
                                    employee_assignments[assignment_id].append((new_task_start, new_task_end))
                            
                            # Update the schedule
                            cur.execute("""
                                UPDATE schedules
                                SET planned_start = %s, planned_end = %s
                                WHERE task_id = %s
                            """, (new_task_start, new_task_end, incomplete_task_id))
                            
                            # Log the change
                            cur.execute("""
                                INSERT INTO schedule_change_log
                                (task_id, previous_start, previous_end, new_start, new_end, 
                                 change_type, reason)
                                VALUES (%s, %s, %s, %s, %s, 'Reschedule', 'Rescheduled due to after-hours completion of Task %s')
                            """, (incomplete_task_id, task_start, task_end, 
                                  new_task_start, new_task_end, task_id))
                            
                            # Add to rescheduled tasks list
                            rescheduled_tasks.append({
                                'task_id': incomplete_task_id,
                                'name': incomplete_task_name,
                                'original_start': task_start,
                                'original_end': task_end,
                                'new_start': new_task_start,
                                'new_end': new_task_end,
                                'reason': 'After-hours completion'
                            })
                    else:
                        print("No incomplete tasks found for today")
                
                # Reschedule dependent tasks
                rescheduled_tasks = self._reschedule_dependent_tasks(task_id, planned_end, timestamp)
                
                if rescheduled_tasks:
                    print(f"Rescheduled {len(rescheduled_tasks)} tasks")
                    for task in rescheduled_tasks:
                        print(f"  - Task {task['task_id']} ({task['name']}): {task['original_start']} -> {task['new_start']}")
                else:
                    print("No tasks to reschedule")
            else:
                print(f"Task {task_id} completed close to planned end time. No rescheduling needed.")
        except Exception as e:
            print(f"Error in rescheduling: {e}")
            import traceback
            traceback.print_exc()
            # Continue with task completion even if rescheduling fails
        
        self.db.conn.commit()
        
        return {
            "success": True,
            "message": f"Task {task_id} marked as completed at {timestamp}",
            "task_id": task_id,
            "status": "Completed",
            "completion_time": timestamp,
            "rescheduled_tasks": rescheduled_tasks
        }
    
    # ---------------------------
    # 1. Short Breaks & Frequent Pauses
    # ---------------------------
    def handle_short_break(self, task_id, start_time, end_time, reason="Short Break"):
        """
        Handle a short break for a task.
        If cumulative breaks in a session are under the threshold, treat as part of the session.
        Otherwise, trigger a reschedule.
        
        Args:
            task_id: The ID of the task being paused
            start_time: When the break started
            end_time: When the break ended (or expected to end)
            reason: Reason for the break
            
        Returns:
            dict: Result of the operation
        """
        print(f"Handling short break for Task {task_id} from {start_time} to {end_time}")
        
        # Calculate break duration in minutes
        break_duration = (end_time - start_time).total_seconds() / 60
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, t.priority, s.planned_start, s.planned_end, s.status,
                   s.actual_start
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, priority, planned_start, planned_end, status, actual_start = task
        
        # Check if task is in progress
        if status != 'In Progress' or not actual_start:
            return {"success": False, "message": "Cannot pause: Task is not in progress"}
        
        # Get cumulative breaks for this task today
        today_start = datetime.combine(start_time.date(), datetime.min.time())
        today_end = datetime.combine(start_time.date(), datetime.max.time())
        
        cur.execute("""
            SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (end_time - start_time)) / 60), 0) as total_minutes
            FROM task_pause_log
            WHERE task_id = %s AND start_time BETWEEN %s AND %s
        """, (task_id, today_start, today_end))
        
        result = cur.fetchone()
        previous_breaks = float(result[0]) if result[0] is not None else 0
        cumulative_breaks = previous_breaks + break_duration
        
        # Log the break
        cur.execute("""
            INSERT INTO task_pause_log
            (task_id, start_time, end_time, reason, duration_minutes)
            VALUES (%s, %s, %s, %s, %s)
        """, (task_id, start_time, end_time, reason, break_duration))
        
        # Important: For a pause, we DO NOT update the task_progress table with an end_time
        # This keeps the task "clocked in" but just marks a break period
        
        # Check if we need to reschedule
        if break_duration > SHORT_BREAK_THRESHOLD or cumulative_breaks > CUMULATIVE_BREAK_THRESHOLD:
            print(f"Break duration ({break_duration} min) or cumulative breaks ({cumulative_breaks} min) exceed threshold. Rescheduling...")
            
            # Get the actual work done so far
            cur.execute("""
                SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (end_time - start_time)) / 3600), 0) as hours_worked
                FROM task_progress
                WHERE task_id = %s AND end_time IS NOT NULL
            """, (task_id,))
            
            hours_worked = cur.fetchone()[0]
            total_duration = (planned_end - planned_start).total_seconds() / 3600
            
            # Calculate remaining work
            remaining_hours = max(0, total_duration - hours_worked)
            
            if remaining_hours > 0:
                # Reschedule the remaining work
                new_start = get_next_working_time(end_time)
                new_end = new_start + timedelta(hours=remaining_hours)
                
                # Update the schedule
                cur.execute("""
                    UPDATE schedules
                    SET planned_end = %s
                    WHERE task_id = %s
                """, (new_end, task_id))
                
                # Log the change
                cur.execute("""
                    INSERT INTO schedule_change_log
                    (task_id, previous_start, previous_end, new_start, new_end, 
                     change_type, reason)
                    VALUES (%s, %s, %s, %s, %s, 'Reschedule', %s)
                """, (task_id, planned_start, planned_end, 
                      planned_start, new_end, f"Long break: {reason}"))
                
                # Reschedule dependent tasks
                self._reschedule_dependent_tasks(task_id, planned_end, new_end)
                
                self.db.conn.commit()
                
                return {
                    "success": True, 
                    "message": f"Task paused and rescheduled due to long break",
                    "task_id": task_id,
                    "status": "In Progress",
                    "new_end": new_end
                }
            else:
                # No remaining work, task is complete
                self.db.conn.commit()
                return {"success": True, "message": "Task already complete, no rescheduling needed"}
        else:
            # Short break, no rescheduling needed
            self.db.conn.commit()
            return {
                "success": True, 
                "message": f"Task paused for a short break until {end_time}",
                "task_id": task_id,
                "status": "In Progress",
                "break_end": end_time
            }
    
    # ---------------------------
    # 2. End-of-Day & Carry-Over
    # ---------------------------
    def handle_end_of_day(self, task_id):
        """
        Handle end-of-day scenario for a task.
        If a task has remaining work at the end of the day (5 PM),
        compute the remaining work and schedule a carry-over segment.
        
        Args:
            task_id: The ID of the task being carried over
            
        Returns:
            dict: Result of the operation
        """
        print(f"Handling end-of-day carry-over for Task {task_id}")
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, t.priority, s.planned_start, s.planned_end, s.status,
                   COALESCE(SUM(EXTRACT(EPOCH FROM (tp.end_time - tp.start_time)) / 3600), 0) as hours_worked
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            LEFT JOIN task_progress tp ON t.task_id = tp.task_id
            WHERE t.task_id = %s
            GROUP BY t.task_id, t.task_name, t.priority, s.planned_start, s.planned_end, s.status
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, priority, planned_start, planned_end, status, hours_worked = task
        
        # Calculate total duration and remaining work
        total_duration = (planned_end - planned_start).total_seconds() / 3600
        hours_worked = float(hours_worked) if hours_worked is not None else 0
        remaining_hours = max(0, total_duration - hours_worked)
        
        if remaining_hours <= 0:
            # Task is already complete
            return {"success": True, "message": "Task already complete, no carry-over needed"}
        
        # Current time is end of working day
        current_date = datetime.now().date()
        end_of_day = datetime.combine(current_date, WORKING_DAY_END)
        
        # Calculate completion percentage
        completion_percentage = min(100, (hours_worked / total_duration) * 100)
        
        # Check if a segment already exists
        cur.execute("""
            SELECT COUNT(*) FROM task_segments
            WHERE task_id = %s AND segment_number = 1
        """, (task_id,))
        
        segment_exists = cur.fetchone()[0] > 0
        
        if segment_exists:
            # Update existing segment
            cur.execute("""
                UPDATE task_segments
                SET planned_end = %s,
                    actual_end = %s,
                    completed_percentage = %s
                WHERE task_id = %s AND segment_number = 1
            """, (end_of_day, end_of_day, completion_percentage, task_id))
        else:
            # Create a new segment
            cur.execute("""
                INSERT INTO task_segments 
                (task_id, segment_number, planned_start, planned_end, 
                 actual_start, actual_end, completed_percentage, status, is_carry_over)
                VALUES (%s, 1, %s, %s, %s, %s, %s, 'Completed', FALSE)
            """, (task_id, planned_start, end_of_day, 
                  planned_start, end_of_day, completion_percentage))
        
        # Find next working day at 9 AM
        next_working_day = current_date + timedelta(days=1)
        while not is_working_day(datetime.combine(next_working_day, datetime.min.time())):
            next_working_day += timedelta(days=1)
        
        next_day_start = datetime.combine(next_working_day, WORKING_DAY_START)
        new_end_time = next_day_start + timedelta(hours=remaining_hours)
        
        # Check if a segment already exists for the carry-over
        cur.execute("""
            SELECT COUNT(*) FROM task_segments
            WHERE task_id = %s AND segment_number = 2
        """, (task_id,))
        
        segment_exists = cur.fetchone()[0] > 0
        
        if segment_exists:
            # Update existing segment
            cur.execute("""
                UPDATE task_segments
                SET planned_start = %s,
                    planned_end = %s
                WHERE task_id = %s AND segment_number = 2
            """, (next_day_start, new_end_time, task_id))
        else:
            # Create a new segment
            cur.execute("""
                INSERT INTO task_segments 
                (task_id, segment_number, planned_start, planned_end, 
                 completed_percentage, status, is_carry_over)
                VALUES (%s, 2, %s, %s, 0, 'Scheduled', TRUE)
            """, (task_id, next_day_start, new_end_time))
        
        # Update the main schedule
        cur.execute("""
            UPDATE schedules 
            SET planned_end = %s
            WHERE task_id = %s
        """, (new_end_time, task_id))
        
        # Log the change
        cur.execute("""
            INSERT INTO schedule_change_log
            (task_id, previous_start, previous_end, new_start, new_end, 
             change_type, reason)
            VALUES (%s, %s, %s, %s, %s, 'Carry-Over', 'End of day carry-over')
        """, (task_id, planned_start, planned_end, 
              planned_start, new_end_time))
        
        # Reschedule dependent tasks
        self._reschedule_dependent_tasks(task_id, planned_end, new_end_time)
        
        self.db.conn.commit()
        
        return {
            "success": True, 
            "message": f"Task carried over to next working day",
            "original_end": planned_end,
            "new_end": new_end_time,
            "completion_percentage": completion_percentage
        }
    
    # ---------------------------
    # 3. Overrun Situations
    # ---------------------------
    def handle_overrun(self, task_id, actual_end_time):
        """
        Handle a task overrun situation.
        If a task goes over its estimated duration, push dependent tasks forward.
        
        Args:
            task_id: The ID of the task that overran
            actual_end_time: The actual end time of the task
            
        Returns:
            dict: Result of the operation
        """
        print(f"Handling overrun for Task {task_id}, actual end time: {actual_end_time}")
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, t.priority, s.planned_start, s.planned_end, s.status
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, priority, planned_start, planned_end, status = task
        
        # Check if this is actually an overrun
        try:
            # Make sure both timestamps are in the same format (either both naive or both aware)
            if planned_end.tzinfo is not None and actual_end_time.tzinfo is None:
                # Convert actual_end_time to aware
                actual_end_time = actual_end_time.replace(tzinfo=planned_end.tzinfo)
            elif planned_end.tzinfo is None and actual_end_time.tzinfo is not None:
                # Convert planned_end to aware
                planned_end = planned_end.replace(tzinfo=actual_end_time.tzinfo)
                
            if actual_end_time <= planned_end:
                return {"success": True, "message": "Task completed on time or early, no overrun"}
        except Exception as e:
            print(f"Error comparing timestamps: {e}")
            # If we can't compare, assume it's an overrun
            pass
        
        # Update the schedule with actual end time
        cur.execute("""
            UPDATE schedules 
            SET planned_end = %s, actual_end = %s
            WHERE task_id = %s
        """, (actual_end_time, actual_end_time, task_id))
        
        # Log the change
        cur.execute("""
            INSERT INTO schedule_change_log
            (task_id, previous_start, previous_end, new_start, new_end, 
             change_type, reason)
            VALUES (%s, %s, %s, %s, %s, 'Overrun', 'Task took longer than estimated')
        """, (task_id, planned_start, planned_end, 
              planned_start, actual_end_time))
        
        # Reschedule dependent tasks
        rescheduled = self._reschedule_dependent_tasks(task_id, planned_end, actual_end_time)
        
        self.db.conn.commit()
        
        return {
            "success": True, 
            "message": f"Task overran and {len(rescheduled)} dependent tasks were rescheduled",
            "original_end": planned_end,
            "actual_end": actual_end_time,
            "rescheduled_tasks": rescheduled
        }
    
    # ---------------------------
    # 4. Long Delays & "On Hold" Events
    # ---------------------------
    def handle_on_hold(self, task_id, reason, expected_resume_time=None):
        """
        Handle a task being put on hold due to a long delay.
        Mark the task as "On Hold" and flag downstream tasks as "Blocked".
        
        Args:
            task_id: The ID of the task being put on hold
            reason: Reason for the hold
            expected_resume_time: When the task is expected to resume (optional)
            
        Returns:
            dict: Result of the operation
        """
        print(f"Putting Task {task_id} on hold due to: {reason}")
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, t.priority, s.planned_start, s.planned_end, s.status
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, priority, planned_start, planned_end, status = task
        
        # Update the task status to "On Hold"
        cur.execute("""
            UPDATE schedules 
            SET status = 'On Hold'
            WHERE task_id = %s
        """, (task_id,))
        
        # Log the hold
        current_time = datetime.now()
        cur.execute("""
            INSERT INTO task_pause_log
            (task_id, start_time, end_time, reason, is_on_hold, expected_resume_time)
            VALUES (%s, %s, NULL, %s, TRUE, %s)
        """, (task_id, current_time, reason, expected_resume_time))
        
        # Find all dependent tasks
        blocked_tasks = self._get_dependent_tasks(task_id)
        
        # Mark dependent tasks as "Blocked"
        for dep_task_id in blocked_tasks:
            cur.execute("""
                UPDATE schedules 
                SET status = 'Blocked'
                WHERE task_id = %s
            """, (dep_task_id,))
            
            # Log the change
            cur.execute("""
                INSERT INTO schedule_change_log
                (task_id, previous_start, previous_end, new_start, new_end, 
                 change_type, reason)
                VALUES (%s, %s, %s, NULL, NULL, 'Blocked', %s)
            """, (dep_task_id, planned_start, planned_end, 
                  f"Blocked due to dependency on Task {task_id} which is on hold: {reason}"))
        
        self.db.conn.commit()
        
        return {
            "success": True, 
            "message": f"Task put on hold and {len(blocked_tasks)} dependent tasks marked as blocked",
            "blocked_tasks": blocked_tasks
        }
    
    def resume_on_hold_task(self, task_id, resume_time=None):
        """
        Resume a task that was previously put on hold.
        Recalculate the schedule for the task and its dependencies.
        
        Args:
            task_id: The ID of the task to resume
            resume_time: When the task is resuming (defaults to now)
            
        Returns:
            dict: Result of the operation
        """
        if resume_time is None:
            resume_time = datetime.now()
            
        print(f"Resuming Task {task_id} at {resume_time}")
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, t.priority, s.planned_start, s.planned_end, s.status,
                   COALESCE(SUM(EXTRACT(EPOCH FROM (tp.end_time - tp.start_time)) / 3600), 0) as hours_worked
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            LEFT JOIN task_progress tp ON t.task_id = tp.task_id
            WHERE t.task_id = %s
            GROUP BY t.task_id, t.task_name, t.priority, s.planned_start, s.planned_end, s.status
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, priority, planned_start, planned_end, status, hours_worked = task
        
        if status != 'On Hold':
            return {"success": False, "message": f"Task {task_id} is not on hold"}
        
        # Close the on-hold record
        cur.execute("""
            UPDATE task_pause_log
            SET end_time = %s, duration_minutes = EXTRACT(EPOCH FROM (%s - start_time)) / 60
            WHERE task_id = %s AND end_time IS NULL AND is_on_hold = TRUE
        """, (resume_time, resume_time, task_id))
        
        # Calculate total duration and remaining work
        total_duration = (planned_end - planned_start).total_seconds() / 3600
        hours_worked = float(hours_worked) if hours_worked is not None else 0
        remaining_hours = max(0, total_duration - hours_worked)
        
        # Ensure resume time is during working hours
        resume_time = get_next_working_time(resume_time)
        new_end_time = resume_time + timedelta(hours=remaining_hours)
        
        # Update the schedule
        cur.execute("""
            UPDATE schedules 
            SET status = 'In Progress', planned_end = %s
            WHERE task_id = %s
        """, (new_end_time, task_id))
        
        # Log the change
        cur.execute("""
            INSERT INTO schedule_change_log
            (task_id, previous_start, previous_end, new_start, new_end, 
             change_type, reason)
            VALUES (%s, %s, %s, %s, %s, 'Resumed', 'Task resumed after being on hold')
        """, (task_id, planned_start, planned_end, 
              resume_time, new_end_time))
        
        # Get all blocked dependent tasks
        cur.execute("""
            SELECT d.task_id
            FROM dependencies d
            JOIN schedules s ON d.task_id = s.task_id
            WHERE d.depends_on_task_id = %s AND s.status = 'Blocked'
        """, (task_id,))
        
        blocked_tasks = [row[0] for row in cur.fetchall()]
        
        # Reschedule all blocked tasks
        rescheduled = self._reschedule_dependent_tasks(task_id, planned_end, new_end_time)
        
        # Update status of previously blocked tasks
        for dep_task_id in blocked_tasks:
            cur.execute("""
                UPDATE schedules 
                SET status = 'Scheduled'
                WHERE task_id = %s
            """, (dep_task_id,))
        
        self.db.conn.commit()
        
        return {
            "success": True, 
            "message": f"Task resumed and {len(rescheduled)} dependent tasks were rescheduled",
            "original_end": planned_end,
            "new_end": new_end_time,
            "rescheduled_tasks": rescheduled
        }
    
    # ---------------------------
    # 5. Cross-Project Resource Conflicts
    # ---------------------------
    def handle_resource_conflict(self, resource_id, conflict_time, is_employee=False):
        """
        Handle a resource conflict between projects.
        Apply priority-based logic to resolve the conflict.
        
        Args:
            resource_id: The ID of the resource or employee causing the conflict
            conflict_time: When the conflict occurs
            is_employee: Whether this is an employee (True) or psical resource (False)
            
        Returns:
            dict: Result of the operation
        """
        print(f"Handling {'employee' if is_employee else 'resource'} conflict for ID {resource_id} at {conflict_time}")
        
        # Find tasks using this resource at the conflict time
        cur = self.db.conn.cursor()
        
        if is_employee:
            # Find tasks assigned to this employee
            cur.execute("""
                SELECT t.task_id, t.task_name, t.priority, t.project_id, p.project_name,
                       s.planned_start, s.planned_end, s.status
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                JOIN projects p ON t.project_id = p.project_id
                JOIN employee_assignments ea ON t.task_id = ea.task_id
                WHERE ea.employee_id = %s 
                  AND s.planned_start <= %s AND s.planned_end >= %s
                  AND s.status IN ('Scheduled', 'In Progress')
            """, (resource_id, conflict_time, conflict_time))
        else:
            # Find tasks using this physical resource
            cur.execute("""
                SELECT t.task_id, t.task_name, t.priority, t.project_id, p.project_name,
                       s.planned_start, s.planned_end, s.status
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                JOIN projects p ON t.project_id = p.project_id
                JOIN resource_assignments ra ON t.task_id = ra.task_id
                WHERE ra.resource_id = %s 
                  AND s.planned_start <= %s AND s.planned_end >= %s
                  AND s.status IN ('Scheduled', 'In Progress')
            """, (resource_id, conflict_time, conflict_time))
        
        conflicting_tasks = cur.fetchall()
        
        if len(conflicting_tasks) <= 1:
            return {"success": True, "message": "No conflict detected"}
        
        # Sort tasks by priority (higher priority value = higher priority)
        conflicting_tasks.sort(key=lambda x: x[2] or 1, reverse=True)
        
        # The highest priority task keeps its schedule
        highest_priority_task = conflicting_tasks[0]
        hp_task_id, hp_name, hp_priority, hp_project_id, hp_project_name, hp_start, hp_end, hp_status = highest_priority_task
        
        # Lower priority tasks need to be rescheduled
        lower_priority_tasks = conflicting_tasks[1:]
        
        rescheduled = []
        for task in lower_priority_tasks:
            task_id, name, priority, project_id, project_name, start, end, status = task
            
            # Check if task is preemptable
            cur.execute("SELECT preemptable FROM tasks WHERE task_id = %s", (task_id,))
            preemptable = cur.fetchone()[0] or False
            
            if preemptable and status == 'In Progress':
                # For preemptable in-progress tasks, split at conflict time
                # Calculate how much work is done and how much remains
                total_duration = (end - start).total_seconds() / 3600  # in hours
                
                # Calculate work done so far
                cur.execute("""
                    SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (end_time - start_time)) / 3600), 0) as hours_worked
                    FROM task_progress
                    WHERE task_id = %s
                """, (task_id,))
                
                hours_worked = cur.fetchone()[0]
                completion_percentage = min(100, (hours_worked / total_duration) * 100)
                
                # Create a task segment for the completed portion
                cur.execute("""
                    INSERT INTO task_segments 
                    (task_id, segment_number, planned_start, planned_end, 
                     actual_start, actual_end, completed_percentage, status, is_carry_over)
                    VALUES (%s, 1, %s, %s, %s, %s, %s, 'Completed', FALSE)
                    ON CONFLICT (task_id, segment_number) DO UPDATE SET
                        planned_end = EXCLUDED.planned_end,
                        actual_end = EXCLUDED.actual_end,
                        completed_percentage = EXCLUDED.completed_percentage
                """, (task_id, start, conflict_time, 
                      start, conflict_time, completion_percentage))
                
                # Find next available time after the high priority task ends
                next_available = get_next_working_time(hp_end)
                remaining_hours = total_duration - hours_worked
                new_end_time = next_available + timedelta(hours=remaining_hours)
                
                # Create a task segment for the remaining portion
                cur.execute("""
                    INSERT INTO task_segments 
                    (task_id, segment_number, planned_start, planned_end, 
                     completed_percentage, status, is_carry_over)
                    VALUES (%s, 2, %s, %s, 0, 'Scheduled', TRUE)
                    ON CONFLICT (task_id, segment_number) DO UPDATE SET
                        planned_start = EXCLUDED.planned_start,
                        planned_end = EXCLUDED.planned_end
                """, (task_id, next_available, new_end_time))
                
                # Update the main schedule
                cur.execute("""
                    UPDATE schedules 
                    SET planned_end = %s
                    WHERE task_id = %s
                """, (new_end_time, task_id))
                
                # Log the change
                cur.execute("""
                    INSERT INTO schedule_change_log
                    (task_id, previous_start, previous_end, new_start, new_end, 
                     change_type, reason)
                    VALUES (%s, %s, %s, %s, %s, 'Preempted', %s)
                """, (task_id, start, end, 
                      start, new_end_time, 
                      f"Preempted due to resource conflict with higher priority Task {hp_task_id} ({hp_name}) from Project {hp_project_id} ({hp_project_name})"))
                
                rescheduled.append({
                    'task_id': task_id,
                    'name': name,
                    'project_id': project_id,
                    'project_name': project_name,
                    'priority': priority,
                    'original_end': end,
                    'new_end': new_end_time,
                    'change_type': 'Preempted'
                })
                
                # Reschedule dependent tasks
                self._reschedule_dependent_tasks(task_id, end, new_end_time)
            else:
                # For non-preemptable tasks or scheduled tasks, reschedule entirely
                # Find next available time after the high priority task ends
                next_available = get_next_working_time(hp_end)
                duration = (end - start).total_seconds() / 3600  # in hours
                new_end_time = next_available + timedelta(hours=duration)
                
                # Update the schedule
                cur.execute("""
                    UPDATE schedules 
                    SET planned_start = %s, planned_end = %s
                    WHERE task_id = %s
                """, (next_available, new_end_time, task_id))
                
                # Log the change
                cur.execute("""
                    INSERT INTO schedule_change_log
                    (task_id, previous_start, previous_end, new_start, new_end, 
                     change_type, reason)
                    VALUES (%s, %s, %s, %s, %s, 'Delayed', %s)
                """, (task_id, start, end, 
                      next_available, new_end_time, 
                      f"Delayed due to resource conflict with higher priority Task {hp_task_id} ({hp_name}) from Project {hp_project_id} ({hp_project_name})"))
                
                rescheduled.append({
                    'task_id': task_id,
                    'name': name,
                    'project_id': project_id,
                    'project_name': project_name,
                    'priority': priority,
                    'original_start': start,
                    'original_end': end,
                    'new_start': next_available,
                    'new_end': new_end_time,
                    'change_type': 'Delayed'
                })
                
                # Reschedule dependent tasks
                self._reschedule_dependent_tasks(task_id, end, new_end_time)
        
        self.db.conn.commit()
        
        return {
            "success": True, 
            "message": f"Resource conflict resolved by rescheduling {len(rescheduled)} lower priority tasks",
            "highest_priority_task": {
                'task_id': hp_task_id,
                'name': hp_name,
                'project_id': hp_project_id,
                'project_name': hp_project_name,
                'priority': hp_priority
            },
            "rescheduled_tasks": rescheduled
        }
    
    # ---------------------------
    # 6. Manual Overrides
    # ---------------------------
    def skip_task(self, task_id, reason):
        """
        Manually skip a task.
        
        Args:
            task_id: The ID of the task to skip
            reason: Reason for skipping
            
        Returns:
            dict: Result of the operation
        """
        print(f"Manually skipping Task {task_id} due to: {reason}")
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, s.status
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, planned_start, planned_end, status = task
        
        # Update the task status to "Skipped"
        cur.execute("""
            UPDATE schedules 
            SET status = 'Skipped'
            WHERE task_id = %s
        """, (task_id,))
        
        # Log the skip
        current_time = datetime.now()
        cur.execute("""
            INSERT INTO task_skip_log
            (task_id, skip_time, reason)
            VALUES (%s, %s, %s)
        """, (task_id, current_time, reason))
        
        # Trigger a full reschedule when a task is skipped
        print(f"Task {task_id} skipped. Triggering full reschedule...")
        
        try:
            # Get the scheduler instance
            from scheduler import Scheduler
            scheduler = Scheduler(self.db)
            
            # Get all tasks that are already completed or skipped - these will be preserved
            cur.execute("""
                SELECT task_id
                FROM schedules
                WHERE status IN ('Completed', 'Skipped')
            """)
            
            preserved_tasks = [row[0] for row in cur.fetchall()]
            print(f"Preserving {len(preserved_tasks)} tasks that are completed or skipped")
            
            # Add the current task to the preserved tasks if not already included
            if task_id not in preserved_tasks:
                preserved_tasks.append(task_id)
            
            # Run the scheduler with the list of tasks to preserve
            # Clear existing schedules for tasks that need to be rescheduled
            cur.execute("""
                DELETE FROM schedules
                WHERE task_id NOT IN %s
                AND status NOT IN ('Completed', 'Skipped')
            """, (tuple(preserved_tasks) if preserved_tasks else (0,),))
            
            # Run the scheduler
            result = scheduler.schedule(preserved_tasks=preserved_tasks)
            
            # Get the rescheduled tasks
            cur.execute("""
                SELECT s.task_id, t.task_name, s.planned_start, s.planned_end
                FROM schedules s
                JOIN tasks t ON s.task_id = t.task_id
                WHERE s.task_id NOT IN %s
                ORDER BY s.planned_start
            """, (tuple(preserved_tasks) if preserved_tasks else (0,),))
            
            rescheduled = []
            for row in cur.fetchall():
                rescheduled_task_id, rescheduled_task_name, new_start, new_end = row
                rescheduled.append({
                    'task_id': rescheduled_task_id,
                    'name': rescheduled_task_name,
                    'original_start': None,  # We don't have the original start time
                    'original_end': None,    # We don't have the original end time
                    'new_start': new_start,
                    'new_end': new_end,
                    'reason': 'Full reschedule after task skipped'
                })
            
            print(f"Full reschedule completed. Rescheduled {len(rescheduled)} tasks.")
        except Exception as e:
            print(f"Error in full reschedule: {e}")
            import traceback
            traceback.print_exc()
            
            # Fall back to just rescheduling dependent tasks
            print("Falling back to rescheduling only dependent tasks...")
            rescheduled = self._reschedule_dependent_tasks(task_id, planned_end, current_time)
        
        self.db.conn.commit()
        
        return {
            "success": True, 
            "message": f"Task skipped and {len(rescheduled)} dependent tasks were rescheduled",
            "rescheduled_tasks": rescheduled
        }
    
    def manually_reschedule_task(self, task_id, new_start_time, new_end_time, reason):
        """
        Manually reschedule a task.
        
        Args:
            task_id: The ID of the task to reschedule
            new_start_time: New start time
            new_end_time: New end time
            reason: Reason for rescheduling
            
        Returns:
            dict: Result of the operation
        """
        print(f"Manually rescheduling Task {task_id} to {new_start_time} - {new_end_time} due to: {reason}")
        
        # Get task details
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, t.task_name, s.planned_start, s.planned_end, s.status
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            print(f"Task {task_id} not found")
            return {"success": False, "message": f"Task {task_id} not found"}
        
        task_id, name, planned_start, planned_end, status = task
        
        # Store original times for logging
        original_start = new_start_time
        original_end = new_end_time
        
        # Calculate duration before adjusting times
        original_duration_hours = (new_end_time - new_start_time).total_seconds() / 3600
        if original_duration_hours <= 0:
            print(f"Warning: Invalid duration {original_duration_hours} hours. Using 0.25 hours instead.")
            original_duration_hours = 0.25  # Minimum 15 minutes
            
            # Only in case of invalid duration, adjust the end time
            new_end_time = new_start_time + timedelta(hours=original_duration_hours)
        
        # For manual rescheduling, we respect the user's chosen times
        # We don't enforce working hours for manual changes
        print(f"Using manually specified times: {new_start_time} - {new_end_time}")
        
        # Update the estimated hours in the tasks table to match the new duration
        # Round to 2 decimal places for better display
        new_estimated_hours = round(original_duration_hours, 2)
        print(f"Updating estimated hours to {new_estimated_hours} based on new duration")
        
        print(f"Adjusted schedule: {new_start_time} - {new_end_time} (duration: {original_duration_hours} hours)")
        
        # Ensure end time is after start time
        if new_end_time <= new_start_time:
            new_end_time = new_start_time + timedelta(minutes=15)  # Minimum 15 minutes
            print(f"Corrected invalid end time. New end time: {new_end_time}")
        
        # Update the estimated hours in the tasks table
        cur.execute("""
            UPDATE tasks 
            SET estimated_hours = %s
            WHERE task_id = %s
        """, (new_estimated_hours, task_id))
        
        # Update the schedule
        cur.execute("""
            UPDATE schedules 
            SET planned_start = %s, planned_end = %s
            WHERE task_id = %s
        """, (new_start_time, new_end_time, task_id))
        
        # Log the change
        cur.execute("""
            INSERT INTO schedule_change_log
            (task_id, previous_start, previous_end, new_start, new_end, 
             change_type, reason)
            VALUES (%s, %s, %s, %s, %s, 'Manual', %s)
        """, (task_id, planned_start, planned_end, 
              new_start_time, new_end_time, f"Manual reschedule: {reason}"))
        
        # Reschedule dependent tasks
        rescheduled = self._reschedule_dependent_tasks(task_id, planned_end, new_end_time)
        
        self.db.conn.commit()
        
        return {
            "success": True, 
            "message": f"Task manually rescheduled and {len(rescheduled)} dependent tasks were updated",
            "original_start": planned_start,
            "original_end": planned_end,
            "new_start": new_start_time,
            "new_end": new_end_time,
            "rescheduled_tasks": rescheduled
        }
    
    # ---------------------------
    # 7. Full Reoptimization
    # ---------------------------
    def full_reoptimization(self, project_id=None):
        """
        Perform a full reoptimization of the schedule.
        
        Args:
            project_id: Optional project ID to limit reoptimization scope
            
        Returns:
            dict: Result of the operation
        """
        print(f"Performing full reoptimization{' for Project ' + str(project_id) if project_id else ''}")
        
        # Get all tasks that need to be rescheduled
        cur = self.db.conn.cursor()
        
        if project_id:
            cur.execute("""
                SELECT task_id FROM tasks 
                WHERE project_id = %s AND wbs NOT IN ('1.1', '1.2', '1.3', '1.4')
            """, (project_id,))
        else:
            cur.execute("""
                SELECT task_id FROM tasks 
                WHERE wbs NOT IN ('1.1', '1.2', '1.3', '1.4')
            """)
        
        task_ids = [row[0] for row in cur.fetchall()]
        
        if not task_ids:
            return {"success": False, "message": "No tasks found for reoptimization"}
        
        # Get all tasks with their details
        tasks = self.db.get_tasks()
        
        # Create a new scheduler
        scheduler = ConstructionScheduler(tasks, self.db)
        
        # Solve the model
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300
        solver.parameters.num_search_workers = 4
        
        print("Solving model...")
        status = solver.Solve(scheduler.model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Extract the new schedule
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
            
            # Update the database
            self.db.update_schedule(schedule)
            
            # Log the reoptimization
            current_time = datetime.now()
            cur.execute("""
                INSERT INTO optimization_history
                (optimization_time, project_id, reason, num_tasks)
                VALUES (%s, %s, 'Full reoptimization', %s)
            """, (current_time, project_id, len(task_ids)))
            
            self.db.conn.commit()
            
            return {
                "success": True, 
                "message": f"Full reoptimization completed successfully for {len(task_ids)} tasks",
                "status": solver.StatusName(status)
            }
        else:
            return {
                "success": False, 
                "message": f"Reoptimization failed: {solver.StatusName(status)}",
                "status": solver.StatusName(status)
            }
    
    # ---------------------------
    # Helper Methods
    # ---------------------------
    def _get_dependent_tasks(self, task_id):
        """Get all tasks that depend on the given task."""
        dependent_tasks = []
        cur = self.db.conn.cursor()
        
        # Direct dependencies
        cur.execute("""
            SELECT task_id FROM dependencies
            WHERE depends_on_task_id = %s
        """, (task_id,))
        
        direct_deps = [row[0] for row in cur.fetchall()]
        dependent_tasks.extend(direct_deps)
        
        # Recursive dependencies (tasks that depend on the direct dependencies)
        for dep_id in direct_deps:
            dependent_tasks.extend(self._get_dependent_tasks(dep_id))
        
        return list(set(dependent_tasks))  # Remove duplicates
    
    def _reschedule_dependent_tasks(self, task_id, old_end_time, new_end_time):
        """
        Reschedule all tasks that depend on the given task.
        
        Args:
            task_id: The ID of the task that changed
            old_end_time: The original end time
            new_end_time: The new end time
            
        Returns:
            list: Rescheduled tasks
        """
        # Ensure both datetimes are timezone-aware or timezone-naive
        # Convert to timezone-naive for comparison if needed
        if hasattr(old_end_time, 'tzinfo') and old_end_time.tzinfo is not None:
            old_end_time = old_end_time.replace(tzinfo=None)
        
        if hasattr(new_end_time, 'tzinfo') and new_end_time.tzinfo is not None:
            new_end_time = new_end_time.replace(tzinfo=None)
            
        try:
            if old_end_time >= new_end_time:
                # No need to reschedule if the task finished earlier
                return []
        except TypeError as e:
            print(f"Error comparing timestamps: {e}")
            print(f"old_end_time: {old_end_time}, type: {type(old_end_time)}")
            print(f"new_end_time: {new_end_time}, type: {type(new_end_time)}")
            # If comparison fails, assume we need to reschedule
            pass
        
        rescheduled = []
        cur = self.db.conn.cursor()
        
        # Get direct dependencies
        cur.execute("""
            SELECT d.task_id, t.task_name, s.planned_start, s.planned_end, 
                   COALESCE(d.lag_hours, 0) as lag_hours
            FROM dependencies d
            JOIN tasks t ON d.task_id::INTEGER = t.task_id
            JOIN schedules s ON d.task_id::INTEGER = s.task_id
            WHERE d.depends_on_task_id::INTEGER = %s
        """, (task_id,))
        
        direct_deps = cur.fetchall()
        
        for dep_task_id, dep_name, dep_start, dep_end, lag_hours in direct_deps:
            # Calculate the time shift
            time_shift = (new_end_time - old_end_time).total_seconds() / 3600  # in hours
            
            # Apply lag (convert decimal.Decimal to float)
            lag_hours_float = float(lag_hours) if lag_hours is not None else 0
            with_lag_time = new_end_time + timedelta(hours=lag_hours_float)
            
            # Ensure it's during working hours
            next_working_time = get_next_working_time(with_lag_time)
            
            # Calculate new start and end times
            duration = (dep_end - dep_start).total_seconds() / 3600  # in hours
            new_dep_start = next_working_time
            new_dep_end = new_dep_start + timedelta(hours=duration)
            
            # Update the schedule
            cur.execute("""
                UPDATE schedules 
                SET planned_start = %s, planned_end = %s
                WHERE task_id = %s
            """, (new_dep_start, new_dep_end, dep_task_id))
            
            # Log the change
            cur.execute("""
                INSERT INTO schedule_change_log
                (task_id, previous_start, previous_end, new_start, new_end, 
                 change_type, reason)
                VALUES (%s, %s, %s, %s, %s, 'Dependency', %s)
            """, (dep_task_id, dep_start, dep_end, 
                  new_dep_start, new_dep_end, 
                  f"Rescheduled due to change in dependency Task {task_id}"))
            
            rescheduled.append({
                'task_id': dep_task_id,
                'name': dep_name,
                'original_start': dep_start,
                'original_end': dep_end,
                'new_start': new_dep_start,
                'new_end': new_dep_end
            })
            
            # Recursively reschedule tasks that depend on this one
            nested_rescheduled = self._reschedule_dependent_tasks(dep_task_id, dep_end, new_dep_end)
            rescheduled.extend(nested_rescheduled)
        
        return rescheduled

# ---------------------------
# Test Functions
# ---------------------------
def test_short_break():
    """Test handling a short break."""
    rm = ReschedulingManager()
    try:
        # Get a random task
        cur = rm.db.conn.cursor()
        cur.execute("""
            SELECT task_id FROM tasks 
            WHERE priority IS NOT NULL
            ORDER BY task_id
            LIMIT 1
        """)
        task_id = cur.fetchone()[0]
        cur.close()
        
        # Test a short break (15 minutes)
        now = datetime.now()
        break_end = now + timedelta(minutes=15)
        
        print(f"\n=== Testing Short Break for Task {task_id} ===")
        result = rm.handle_short_break(task_id, now, break_end, "Coffee break")
        print(f"Result: {result}")
        
        # Test a long break (45 minutes)
        now = datetime.now()
        break_end = now + timedelta(minutes=45)
        
        print(f"\n=== Testing Long Break for Task {task_id} ===")
        result = rm.handle_short_break(task_id, now, break_end, "Extended lunch")
        print(f"Result: {result}")
        
    finally:
        rm.close()

def test_end_of_day():
    """Test handling end-of-day carry-over."""
    rm = ReschedulingManager()
    try:
        # Get a random task
        cur = rm.db.conn.cursor()
        cur.execute("""
            SELECT task_id FROM tasks 
            WHERE priority IS NOT NULL
            ORDER BY task_id
            LIMIT 1
        """)
        task_id = cur.fetchone()[0]
        cur.close()
        
        print(f"\n=== Testing End-of-Day Carry-Over for Task {task_id} ===")
        result = rm.handle_end_of_day(task_id)
        print(f"Result: {result}")
        
    finally:
        rm.close()

def test_overrun():
    """Test handling a task overrun."""
    rm = ReschedulingManager()
    try:
        # Get a random task
        cur = rm.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, s.planned_end 
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.priority IS NOT NULL
            ORDER BY t.task_id
            LIMIT 1
        """)
        task_id, planned_end = cur.fetchone()
        cur.close()
        
        # Simulate an overrun (1 hour later)
        overrun_end = planned_end + timedelta(hours=1)
        
        print(f"\n=== Testing Overrun for Task {task_id} ===")
        result = rm.handle_overrun(task_id, overrun_end)
        print(f"Result: {result}")
        
    finally:
        rm.close()

def test_on_hold():
    """Test putting a task on hold and resuming it."""
    rm = ReschedulingManager()
    try:
        # Get a random task
        cur = rm.db.conn.cursor()
        cur.execute("""
            SELECT task_id FROM tasks 
            WHERE priority IS NOT NULL
            ORDER BY task_id
            LIMIT 1
        """)
        task_id = cur.fetchone()[0]
        cur.close()
        
        # Put the task on hold
        print(f"\n=== Testing On Hold for Task {task_id} ===")
        result = rm.handle_on_hold(task_id, "Machine breakdown")
        print(f"Result: {result}")
        
        # Resume the task
        print(f"\n=== Testing Resume for Task {task_id} ===")
        resume_time = datetime.now() + timedelta(hours=2)  # Resume in 2 hours
        result = rm.resume_on_hold_task(task_id, resume_time)
        print(f"Result: {result}")
        
    finally:
        rm.close()

def test_resource_conflict():
    """Test handling a resource conflict."""
    rm = ReschedulingManager()
    try:
        # Get a resource that's used by multiple tasks
        cur = rm.db.conn.cursor()
        cur.execute("""
            SELECT r.resource_id, r.name
            FROM resources r
            JOIN resource_assignments ra ON r.resource_id = ra.resource_id
            GROUP BY r.resource_id, r.name
            HAVING COUNT(DISTINCT ra.task_id) > 1
            LIMIT 1
        """)
        
        resource_row = cur.fetchone()
        
        if resource_row:
            resource_id, resource_name = resource_row
            
            # Find a time when this resource is used
            cur.execute("""
                SELECT s.planned_start
                FROM schedules s
                JOIN resource_assignments ra ON s.task_id = ra.task_id
                WHERE ra.resource_id = %s
                LIMIT 1
            """, (resource_id,))
            
            conflict_time = cur.fetchone()[0]
            
            print(f"\n=== Testing Resource Conflict for Resource {resource_id} ({resource_name}) ===")
            result = rm.handle_resource_conflict(resource_id, conflict_time, is_employee=False)
            print(f"Result: {result}")
        else:
            # Try with an employee
            cur.execute("""
                SELECT e.employee_id, e.name
                FROM employees e
                JOIN employee_assignments ea ON e.employee_id = ea.employee_id
                GROUP BY e.employee_id, e.name
                HAVING COUNT(DISTINCT ea.task_id) > 1
                LIMIT 1
            """)
            
            employee_row = cur.fetchone()
            
            if employee_row:
                employee_id, employee_name = employee_row
                
                # Find a time when this employee is assigned
                cur.execute("""
                    SELECT s.planned_start
                    FROM schedules s
                    JOIN employee_assignments ea ON s.task_id = ea.task_id
                    WHERE ea.employee_id = %s
                    LIMIT 1
                """, (employee_id,))
                
                conflict_time = cur.fetchone()[0]
                
                print(f"\n=== Testing Resource Conflict for Employee {employee_id} ({employee_name}) ===")
                result = rm.handle_resource_conflict(employee_id, conflict_time, is_employee=True)
                print(f"Result: {result}")
            else:
                print("No suitable resource or employee found for conflict testing")
        
        cur.close()
        
    finally:
        rm.close()

def test_skip_task():
    """Test skipping a task."""
    rm = ReschedulingManager()
    try:
        # Get a random task
        cur = rm.db.conn.cursor()
        cur.execute("""
            SELECT task_id FROM tasks 
            WHERE priority IS NOT NULL
            ORDER BY task_id
            LIMIT 1
        """)
        task_id = cur.fetchone()[0]
        cur.close()
        
        print(f"\n=== Testing Skip Task for Task {task_id} ===")
        result = rm.skip_task(task_id, "Not needed for this project")
        print(f"Result: {result}")
        
    finally:
        rm.close()

def test_manual_reschedule():
    """Test manually rescheduling a task."""
    rm = ReschedulingManager()
    try:
        # Get a random task
        cur = rm.db.conn.cursor()
        cur.execute("""
            SELECT t.task_id, s.planned_start, s.planned_end 
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.priority IS NOT NULL
            ORDER BY t.task_id
            LIMIT 1
        """)
        task_id, planned_start, planned_end = cur.fetchone()
        cur.close()
        
        # Reschedule to start tomorrow
        tomorrow = datetime.now().date() + timedelta(days=1)
        new_start = datetime.combine(tomorrow, time(10, 0))  # 10:00 AM tomorrow
        duration = (planned_end - planned_start).total_seconds() / 3600
        new_end = new_start + timedelta(hours=duration)
        
        print(f"\n=== Testing Manual Reschedule for Task {task_id} ===")
        result = rm.manually_reschedule_task(task_id, new_start, new_end, "Material delivery delay")
        print(f"Result: {result}")
        
    finally:
        rm.close()

def test_full_reoptimization():
    """Test full schedule reoptimization."""
    rm = ReschedulingManager()
    try:
        # Get a project ID
        cur = rm.db.conn.cursor()
        cur.execute("SELECT project_id FROM projects LIMIT 1")
        project_id = cur.fetchone()[0]
        cur.close()
        
        print(f"\n=== Testing Full Reoptimization for Project {project_id} ===")
        result = rm.full_reoptimization(project_id)
        print(f"Result: {result}")
        
    finally:
        rm.close()

# ---------------------------
# API Helper Functions
# ---------------------------
def get_task_details(task_id):
    """
    Get details for a specific task
    """
    db = DatabaseManager()
    cur = db.conn.cursor()
    
    cur.execute("""
        SELECT t.task_id, t.task_name, t.priority, t.preemptable,
               s.planned_start, s.planned_end, s.status
        FROM tasks t
        JOIN schedules s ON t.task_id = s.task_id
        WHERE t.task_id = %s
    """, (task_id,))
    
    row = cur.fetchone()
    if not row:
        cur.close()
        db.close()
        return None
    
    task_id, name, priority, preemptable, planned_start, planned_end, status = row
    
    task = {
        'task_id': task_id,
        'name': name,
        'priority': priority or 1,  # Default to low priority if None
        'preemptable': preemptable or False,
        'planned_start': planned_start,
        'planned_end': planned_end,
        'status': status
    }
    
    cur.close()
    db.close()
    
    return task

def handle_event(task_id, event_type, timestamp, details=None):
    """
    Handle a rescheduling event
    
    Args:
        task_id: ID of the task
        event_type: Type of event (clock_in, clock_out, pause, resume, complete, skip, manual_reschedule)
        timestamp: When the event occurred
        details: Additional details for the event
    
    Returns:
        Dictionary with result information
    """
    if details is None:
        details = {}
    
    rm = ReschedulingManager()
    result = {"success": False, "message": "Unknown event type"}
    
    try:
        if event_type == 'clock_in':
            reason = details.get('reason', 'Starting work')
            result = rm.handle_clock_in(task_id, timestamp, reason)
            
        elif event_type == 'clock_out':
            result = rm.handle_clock_out(task_id, timestamp, details)
            
        elif event_type == 'pause':
            reason = details.get('reason', 'Unspecified')
            duration_minutes = details.get('duration_minutes', 0)
            is_on_hold = details.get('is_on_hold', False)
            
            if is_on_hold:
                expected_resume_time = None
                if 'expected_resume_time' in details:
                    expected_resume_time = datetime.fromisoformat(details['expected_resume_time'])
                result = rm.handle_on_hold(task_id, reason, expected_resume_time)
            else:
                break_end = timestamp + timedelta(minutes=duration_minutes)
                result = rm.handle_short_break(task_id, timestamp, break_end, reason)
        
        elif event_type == 'resume':
            result = rm.resume_on_hold_task(task_id, timestamp)
        
        elif event_type == 'complete':
            result = rm.handle_complete(task_id, timestamp, details)
        
        elif event_type == 'skip':
            reason = details.get('reason', 'Unspecified')
            result = rm.skip_task(task_id, reason)
        
        elif event_type == 'manual_reschedule':
            new_start = datetime.fromisoformat(details.get('new_start'))
            new_end = datetime.fromisoformat(details.get('new_end'))
            reason = details.get('reason', 'Manual reschedule')
            result = rm.manually_reschedule_task(task_id, new_start, new_end, reason)
        
        else:
            result = {"success": False, "message": f"Unknown event type: {event_type}"}
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error handling event: {str(e)}")
        print(error_trace)
        
        result = {
            "success": False, 
            "message": f"Error handling event: {str(e)}",
            "traceback": error_trace
        }
    
    finally:
        rm.close()
    
    return result

# ---------------------------
# Main Execution
# ---------------------------
if __name__ == '__main__':
    print("Running rescheduling tests...")
    
    # Create required tables if they don't exist
    db = DatabaseManager()
    cur = db.conn.cursor()
    
    # Create task_progress table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_progress (
            progress_id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status VARCHAR(50) NOT NULL,
            notes TEXT,
            duration_minutes NUMERIC DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_percentage NUMERIC(5,2) DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        )
    """)
    
    # Create task_segments table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_segments (
            task_id INTEGER NOT NULL,
            segment_number INTEGER NOT NULL,
            planned_start TIMESTAMP NOT NULL,
            planned_end TIMESTAMP NOT NULL,
            actual_start TIMESTAMP,
            actual_end TIMESTAMP,
            completed_percentage NUMERIC(5,2) DEFAULT 0,
            status VARCHAR(50) DEFAULT 'Scheduled',
            is_carry_over BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (task_id, segment_number),
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        );
    """)
    
    # Create task_pause_log table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_pause_log (
            pause_id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            reason TEXT,
            duration_minutes NUMERIC(10,2),
            is_on_hold BOOLEAN DEFAULT FALSE,
            expected_resume_time TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        );
    """)
    
    # Create schedule_change_log table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schedule_change_log (
            change_id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            previous_start TIMESTAMP,
            previous_end TIMESTAMP,
            new_start TIMESTAMP,
            new_end TIMESTAMP,
            change_type VARCHAR(50) NOT NULL,
            reason TEXT,
            change_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        );
    """)
    
    # Create task_skip_log table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_skip_log (
            skip_id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            skip_time TIMESTAMP NOT NULL,
            reason TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        );
    """)
    
    # Create optimization_history table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS optimization_history (
            optimization_id SERIAL PRIMARY KEY,
            optimization_time TIMESTAMP NOT NULL,
            project_id INTEGER,
            reason TEXT,
            num_tasks INTEGER,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
    """)
    
    db.conn.commit()
    cur.close()
    db.close()
    
    # Run tests
    test_short_break()
    test_end_of_day()
    test_overrun()
    test_on_hold()
    test_resource_conflict()
    test_skip_task()
    test_manual_reschedule()
    test_full_reoptimization()
    
    print("\nAll tests completed!")