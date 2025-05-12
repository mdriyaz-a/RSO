#!/usr/bin/env python
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
import json
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

# Import our existing modules
from initial_scheduler import DatabaseManager, cp_sat_scheduler, working_time_to_datetime, auto_assign_resources_to_tasks
from rescheduler import handle_event, get_task_details

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database connection helper
def get_db_connection():
    conn = psycopg2.connect(
        dbname='rso01',
        user='postgres',
        password='root',
        host='localhost'
    )
    conn.autocommit = True
    return conn

def assign_initial_resources():
    """Helper function to assign initial resources to tasks"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
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
        conn.commit()
    
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
        conn.commit()
    
    # Get tasks to assign resources to
    cur.execute("""
        SELECT t.task_id, t.task_name
        FROM tasks t
        JOIN schedules s ON t.task_id = s.task_id
        WHERE s.status = 'Scheduled'
    """)
    
    tasks = cur.fetchall()
    
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
        # Create the employees table
        cur.execute("""
            CREATE TABLE employees (
                employee_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                role_name VARCHAR(100),
                skill_set VARCHAR(100),
                availability BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Insert sample employees
        cur.execute("""
            INSERT INTO employees (name, role_name, skill_set, availability)
            VALUES 
            ('John Smith', 'Project Manager', 'management', TRUE),
            ('Jane Doe', 'Engineer', 'engineering', TRUE),
            ('Bob Johnson', 'Technician', 'technical', TRUE),
            ('Alice Brown', 'Designer', 'design', TRUE)
        """)
        conn.commit()
    
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
        # Create the resources table
        cur.execute("""
            CREATE TABLE resources (
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
        """)
        conn.commit()
    
    # Check if role_name column exists in employees table
    cur.execute("""
        SELECT EXISTS (
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'employees' AND column_name = 'role_name'
        ) as exists
    """)
    has_role_name = cur.fetchone()['exists']
    
    # Get all employees with appropriate columns
    if has_role_name:
        cur.execute("SELECT employee_id, name, role_name FROM employees")
    else:
        print("role_name column does not exist in employees table, using basic query")
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
    has_type = cur.fetchone()['exists']
    
    # Get all resources with appropriate columns
    if has_type:
        cur.execute("SELECT resource_id, name, type FROM resources")
    else:
        print("type column does not exist in resources table, using basic query")
        cur.execute("SELECT resource_id, name FROM resources")
    resources = cur.fetchall()
    
    # For each task, assign resources and employees
    assigned_tasks = []
    
    for task in tasks:
        task_id = task['task_id']
        task_name = task['task_name']
        
        # Check if this task already has assignments
        cur.execute("SELECT COUNT(*) FROM employee_assignments WHERE task_id = %s", (task_id,))
        employee_count = cur.fetchone()['count']
        
        # Check if this task requires employees
        cur.execute("""
            SELECT resource_group, resource_count 
            FROM task_required_employees 
            WHERE task_id = %s
        """, (task_id,))
        required_employees = cur.fetchall()
        
        # Only assign if no assignments exist and the task requires employees
        if employee_count == 0 and employees and required_employees:
            # Get the first required employee group
            required_group = required_employees[0]['resource_group'].lower() if required_employees else None
            
            # Find an employee with the matching skill set
            matching_employee = None
            for emp in employees:
                if emp.get('skill_set') and emp.get('skill_set').lower() == required_group:
                    matching_employee = emp
                    break
            
            # If no matching employee found, use the first employee as fallback
            employee = matching_employee or employees[0]
            employee_id = employee['employee_id']
            
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
            table_exists = result['count'] > 0
            has_is_initial = result['has_is_initial'] > 0
            has_is_modified = result['has_is_modified'] > 0
            
            # Check if there's a unique constraint on (task_id, employee_id)
            cur.execute("""
                SELECT COUNT(*) FROM pg_constraint
                WHERE conrelid = 'employee_assignments'::regclass
                AND contype = 'u'
                AND (
                    array_position(conkey, (SELECT attnum FROM pg_attribute WHERE attrelid = 'employee_assignments'::regclass AND attname = 'task_id')) IS NOT NULL
                    AND
                    array_position(conkey, (SELECT attnum FROM pg_attribute WHERE attrelid = 'employee_assignments'::regclass AND attname = 'employee_id')) IS NOT NULL
                )
            """)
            has_unique_constraint = cur.fetchone()['count'] > 0
            
            try:
                # First check if assignment already exists
                cur.execute("SELECT COUNT(*) FROM employee_assignments WHERE task_id = %s AND employee_id = %s", 
                           (task_id, employee_id))
                already_exists = cur.fetchone()['count'] > 0
                
                if not already_exists:
                    if table_exists and has_is_initial and has_is_modified:
                        # Use full insert with all columns
                        if has_unique_constraint:
                            cur.execute("""
                                INSERT INTO employee_assignments (task_id, employee_id, is_initial, is_modified)
                                VALUES (%s, %s, TRUE, FALSE)
                                ON CONFLICT (task_id, employee_id) DO NOTHING
                            """, (task_id, employee_id))
                        else:
                            cur.execute("""
                                INSERT INTO employee_assignments (task_id, employee_id, is_initial, is_modified)
                                VALUES (%s, %s, TRUE, FALSE)
                            """, (task_id, employee_id))
                    else:
                        # Use simplified insert with only required columns
                        if has_unique_constraint:
                            cur.execute("""
                                INSERT INTO employee_assignments (task_id, employee_id)
                                VALUES (%s, %s)
                                ON CONFLICT (task_id, employee_id) DO NOTHING
                            """, (task_id, employee_id))
                        else:
                            cur.execute("""
                                INSERT INTO employee_assignments (task_id, employee_id)
                                VALUES (%s, %s)
                            """, (task_id, employee_id))
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
                except Exception as e2:
                    print(f"Final attempt to insert employee assignment failed: {e2}")
            
            employee_name = employee['name'] if isinstance(employee, dict) else employee[1] if len(employee) > 1 else "Unknown"
            assigned_tasks.append({
                'task_id': task_id,
                'task_name': task_name,
                'employee_id': employee_id,
                'employee_name': employee_name
            })
        
        # Check if this task already has resource assignments
        cur.execute("SELECT COUNT(*) FROM resource_assignments WHERE task_id = %s", (task_id,))
        resource_count = cur.fetchone()['count']
        
        # Check if this task requires resources
        cur.execute("""
            SELECT resource_category, resource_count 
            FROM task_required_resources 
            WHERE task_id = %s
        """, (task_id,))
        required_resources = cur.fetchall()
        
        # Only assign if no assignments exist and the task requires resources
        if resource_count == 0 and resources and required_resources:
            # Get the first required resource category
            required_category = required_resources[0]['resource_category'].lower() if required_resources else None
            
            # Find a resource with the matching type
            matching_resource = None
            for res in resources:
                if res.get('type') and res.get('type').lower() == required_category:
                    matching_resource = res
                    break
            
            # If no matching resource found, use the first resource as fallback
            resource = matching_resource or resources[0]
            resource_id = resource['resource_id']
            
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
            table_exists = result['count'] > 0
            has_is_initial = result['has_is_initial'] > 0
            has_is_modified = result['has_is_modified'] > 0
            
            # Check if there's a unique constraint on (task_id, resource_id)
            cur.execute("""
                SELECT COUNT(*) FROM pg_constraint
                WHERE conrelid = 'resource_assignments'::regclass
                AND contype = 'u'
                AND (
                    array_position(conkey, (SELECT attnum FROM pg_attribute WHERE attrelid = 'resource_assignments'::regclass AND attname = 'task_id')) IS NOT NULL
                    AND
                    array_position(conkey, (SELECT attnum FROM pg_attribute WHERE attrelid = 'resource_assignments'::regclass AND attname = 'resource_id')) IS NOT NULL
                )
            """)
            has_unique_constraint = cur.fetchone()['count'] > 0
            
            try:
                # First check if assignment already exists
                cur.execute("SELECT COUNT(*) FROM resource_assignments WHERE task_id = %s AND resource_id = %s", 
                           (task_id, resource_id))
                already_exists = cur.fetchone()['count'] > 0
                
                if not already_exists:
                    if table_exists and has_is_initial and has_is_modified:
                        # Use full insert with all columns
                        if has_unique_constraint:
                            cur.execute("""
                                INSERT INTO resource_assignments (task_id, resource_id, is_initial, is_modified)
                                VALUES (%s, %s, TRUE, FALSE)
                                ON CONFLICT (task_id, resource_id) DO NOTHING
                            """, (task_id, resource_id))
                        else:
                            cur.execute("""
                                INSERT INTO resource_assignments (task_id, resource_id, is_initial, is_modified)
                                VALUES (%s, %s, TRUE, FALSE)
                            """, (task_id, resource_id))
                    else:
                        # Use simplified insert with only required columns
                        if has_unique_constraint:
                            cur.execute("""
                                INSERT INTO resource_assignments (task_id, resource_id)
                                VALUES (%s, %s)
                                ON CONFLICT (task_id, resource_id) DO NOTHING
                            """, (task_id, resource_id))
                        else:
                            cur.execute("""
                                INSERT INTO resource_assignments (task_id, resource_id)
                                VALUES (%s, %s)
                            """, (task_id, resource_id))
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
                except Exception as e2:
                    print(f"Final attempt to insert resource assignment failed: {e2}")
            
            resource_name = resource['name'] if isinstance(resource, dict) else resource[1] if len(resource) > 1 else "Unknown"
            assigned_tasks.append({
                'task_id': task_id,
                'task_name': task_name,
                'resource_id': resource_id,
                'resource_name': resource_name
            })
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"Assigned resources to {len(assigned_tasks)} tasks")
    return assigned_tasks

@app.route('/api/assignments/auto-assign', methods=['POST'])
def auto_assign_resources_endpoint():
    """
    Automatically assign resources and employees to tasks
    
    Optional JSON body:
    {
        "task_id": 123  // If provided, only assign to this task
    }
    """
    try:
        # Call the auto-assign function from initial_scheduler.py
        success = auto_assign_resources_to_tasks()
        
        if success:
            # Fetch the assignments to return to the client
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get employee assignments
            cur.execute("""
                SELECT ea.task_id, t.task_name, ea.employee_id, e.name as employee_name
                FROM employee_assignments ea
                JOIN tasks t ON ea.task_id = t.task_id
                JOIN employees e ON ea.employee_id = e.employee_id
            """)
            employee_assignments = cur.fetchall()
            
            # Get resource assignments
            cur.execute("""
                SELECT ra.task_id, t.task_name, ra.resource_id, r.name as resource_name
                FROM resource_assignments ra
                JOIN tasks t ON ra.task_id = t.task_id
                JOIN resources r ON ra.resource_id = r.resource_id
            """)
            resource_assignments = cur.fetchall()
            
            cur.close()
            conn.close()
            
            # Combine assignments
            all_assignments = []
            all_assignments.extend(employee_assignments)
            all_assignments.extend(resource_assignments)
            
            return jsonify({
                'success': True,
                'message': f'Assigned resources to tasks',
                'assigned_tasks': all_assignments
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to assign resources to tasks'
            }), 500
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/assignments', methods=['GET'])
def get_assignments():
    """
    Get all resource and employee assignments with their status (original or modified)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if employee_assignments table has is_initial and is_modified columns
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'employee_assignments' 
            AND column_name IN ('is_initial', 'is_modified')
        """)
        
        columns = [col['column_name'] for col in cur.fetchall()]
        has_initial_modified_employees = 'is_initial' in columns and 'is_modified' in columns
        
        # Get employee assignments with appropriate columns
        if has_initial_modified_employees:
            cur.execute("""
                SELECT ea.assignment_id, ea.task_id, t.task_name, 
                       ea.employee_id, e.name as employee_name,
                       s.planned_start, s.planned_end, 
                       s.actual_start, s.actual_end, 
                       s.status, t.priority, t.phase,
                       ea.is_initial, ea.is_modified
                FROM employee_assignments ea
                JOIN tasks t ON ea.task_id = t.task_id
                LEFT JOIN schedules s ON ea.task_id = s.task_id
                JOIN employees e ON ea.employee_id = e.employee_id
                ORDER BY ea.employee_id, s.planned_start
            """)
        else:
            cur.execute("""
                SELECT ea.assignment_id, ea.task_id, t.task_name, 
                       ea.employee_id, e.name as employee_name,
                       s.planned_start, s.planned_end, 
                       s.actual_start, s.actual_end, 
                       s.status, t.priority, t.phase
                FROM employee_assignments ea
                JOIN tasks t ON ea.task_id = t.task_id
                LEFT JOIN schedules s ON ea.task_id = s.task_id
                JOIN employees e ON ea.employee_id = e.employee_id
                ORDER BY ea.employee_id, s.planned_start
            """)
        
        employee_assignments = cur.fetchall()
        
        # Check if resource_assignments table has is_initial and is_modified columns
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'resource_assignments' 
            AND column_name IN ('is_initial', 'is_modified')
        """)
        
        columns = [col['column_name'] for col in cur.fetchall()]
        has_initial_modified_resources = 'is_initial' in columns and 'is_modified' in columns
        
        # Get resource assignments with appropriate columns
        if has_initial_modified_resources:
            cur.execute("""
                SELECT ra.assignment_id, ra.task_id, t.task_name, 
                       ra.resource_id, r.name as resource_name,
                       s.planned_start, s.planned_end, 
                       s.actual_start, s.actual_end, 
                       s.status, t.priority, t.phase,
                       ra.is_initial, ra.is_modified
                FROM resource_assignments ra
                JOIN tasks t ON ra.task_id = t.task_id
                LEFT JOIN schedules s ON ra.task_id = s.task_id
                JOIN resources r ON ra.resource_id = r.resource_id
                ORDER BY ra.resource_id, s.planned_start
            """)
        else:
            cur.execute("""
                SELECT ra.assignment_id, ra.task_id, t.task_name, 
                       ra.resource_id, r.name as resource_name,
                       s.planned_start, s.planned_end, 
                       s.actual_start, s.actual_end, 
                       s.status, t.priority, t.phase
                FROM resource_assignments ra
                JOIN tasks t ON ra.task_id = t.task_id
                LEFT JOIN schedules s ON ra.task_id = s.task_id
                JOIN resources r ON ra.resource_id = r.resource_id
                ORDER BY ra.resource_id, s.planned_start
            """)
        
        resource_assignments = cur.fetchall()
        
        # Find employee conflicts
        employee_conflicts = []
        employee_dict = {}
        
        for assignment in employee_assignments:
            employee_id = assignment['employee_id']
            task_id = assignment['task_id']
            
            if employee_id not in employee_dict:
                employee_dict[employee_id] = []
            
            employee_dict[employee_id].append(assignment)
        
        # Check for overlapping tasks for each employee
        for employee_id, tasks in employee_dict.items():
            # Skip if there's only one task for this employee
            if len(tasks) <= 1:
                continue
                
            for i in range(len(tasks)):
                # Skip completed or skipped tasks
                if tasks[i]['status'] in ['Completed', 'Skipped']:
                    continue
                    
                for j in range(i + 1, len(tasks)):
                    # Skip completed or skipped tasks
                    if tasks[j]['status'] in ['Completed', 'Skipped']:
                        continue
                        
                    task1 = tasks[i]
                    task2 = tasks[j]
                    
                    # Convert to datetime objects for comparison
                    task1_start = task1['planned_start']
                    task1_end = task1['planned_end']
                    task2_start = task2['planned_start']
                    task2_end = task2['planned_end']
                    
                    # Skip if either task has null dates
                    if not task1_start or not task1_end or not task2_start or not task2_end:
                        continue
                    
                    # Check if tasks overlap
                    if (task1_start < task2_end and task1_end > task2_start):
                        # Tasks overlap, create a conflict record
                        print(f"Found employee conflict: Employee {employee_id} ({task1['employee_name']}) has overlapping tasks: {task1['task_id']} and {task2['task_id']}")
                        print(f"  Task 1: {task1['task_name']} - {task1_start} to {task1_end}")
                        print(f"  Task 2: {task2['task_name']} - {task2_start} to {task2_end}")
                        conflict = {
                            'employee_id': employee_id,
                            'employee_name': task1['employee_name'],
                            'task1_id': task1['task_id'],
                            'task1_name': task1['task_name'],
                            'task1_start': task1_start,
                            'task1_end': task1_end,
                            'task1_start_iso': task1_start.isoformat(),
                            'task1_end_iso': task1_end.isoformat(),
                            'task1_priority': task1['priority'],
                            'task1_status': task1['status'],
                            'task2_id': task2['task_id'],
                            'task2_name': task2['task_name'],
                            'task2_start': task2_start,
                            'task2_end': task2_end,
                            'task2_start_iso': task2_start.isoformat(),
                            'task2_end_iso': task2_end.isoformat(),
                            'task2_priority': task2['priority'],
                            'task2_status': task2['status']
                        }
                        employee_conflicts.append(conflict)
        
        # Find resource conflicts
        resource_conflicts = []
        resource_dict = {}
        
        for assignment in resource_assignments:
            resource_id = assignment['resource_id']
            task_id = assignment['task_id']
            
            if resource_id not in resource_dict:
                resource_dict[resource_id] = []
            
            resource_dict[resource_id].append(assignment)
        
        # Check for overlapping tasks for each resource
        for resource_id, tasks in resource_dict.items():
            # Skip if there's only one task for this resource
            if len(tasks) <= 1:
                continue
                
            for i in range(len(tasks)):
                # Skip completed or skipped tasks
                if tasks[i]['status'] in ['Completed', 'Skipped']:
                    continue
                    
                for j in range(i + 1, len(tasks)):
                    # Skip completed or skipped tasks
                    if tasks[j]['status'] in ['Completed', 'Skipped']:
                        continue
                        
                    task1 = tasks[i]
                    task2 = tasks[j]
                    
                    # Convert to datetime objects for comparison
                    task1_start = task1['planned_start']
                    task1_end = task1['planned_end']
                    task2_start = task2['planned_start']
                    task2_end = task2['planned_end']
                    
                    # Skip if either task has null dates
                    if not task1_start or not task1_end or not task2_start or not task2_end:
                        continue
                    
                    # Check if tasks overlap
                    if (task1_start < task2_end and task1_end > task2_start):
                        # Tasks overlap, create a conflict record
                        print(f"Found resource conflict: Resource {resource_id} ({task1['resource_name']}) has overlapping tasks: {task1['task_id']} and {task2['task_id']}")
                        print(f"  Task 1: {task1['task_name']} - {task1_start} to {task1_end}")
                        print(f"  Task 2: {task2['task_name']} - {task2_start} to {task2_end}")
                        conflict = {
                            'resource_id': resource_id,
                            'resource_name': task1['resource_name'],
                            'task1_id': task1['task_id'],
                            'task1_name': task1['task_name'],
                            'task1_start': task1_start,
                            'task1_end': task1_end,
                            'task1_start_iso': task1_start.isoformat(),
                            'task1_end_iso': task1_end.isoformat(),
                            'task1_priority': task1['priority'],
                            'task1_status': task1['status'],
                            'task2_id': task2['task_id'],
                            'task2_name': task2['task_name'],
                            'task2_start': task2_start,
                            'task2_end': task2_end,
                            'task2_start_iso': task2_start.isoformat(),
                            'task2_end_iso': task2_end.isoformat(),
                            'task2_priority': task2['priority'],
                            'task2_status': task2['status']
                        }
                        resource_conflicts.append(conflict)
        
        # Add ISO format dates for all assignments
        for assignment in employee_assignments:
            if assignment['planned_start']:
                assignment['planned_start_iso'] = assignment['planned_start'].isoformat()
            else:
                assignment['planned_start_iso'] = None
                
            if assignment['planned_end']:
                assignment['planned_end_iso'] = assignment['planned_end'].isoformat()
            else:
                assignment['planned_end_iso'] = None
                
            if assignment['actual_start']:
                assignment['actual_start_iso'] = assignment['actual_start'].isoformat()
            else:
                assignment['actual_start_iso'] = None
                
            if assignment['actual_end']:
                assignment['actual_end_iso'] = assignment['actual_end'].isoformat()
            else:
                assignment['actual_end_iso'] = None
        
        for assignment in resource_assignments:
            if assignment['planned_start']:
                assignment['planned_start_iso'] = assignment['planned_start'].isoformat()
            else:
                assignment['planned_start_iso'] = None
                
            if assignment['planned_end']:
                assignment['planned_end_iso'] = assignment['planned_end'].isoformat()
            else:
                assignment['planned_end_iso'] = None
                
            if assignment['actual_start']:
                assignment['actual_start_iso'] = assignment['actual_start'].isoformat()
            else:
                assignment['actual_start_iso'] = None
                
            if assignment['actual_end']:
                assignment['actual_end_iso'] = assignment['actual_end'].isoformat()
            else:
                assignment['actual_end_iso'] = None
        
        # Print summary of conflicts
        print(f"Found {len(employee_conflicts)} employee conflicts and {len(resource_conflicts)} resource conflicts")
        
        # Return all assignments and conflicts
        return jsonify({
            'employee_assignments': employee_assignments,
            'resource_assignments': resource_assignments,
            'employee_conflicts': employee_conflicts,
            'resource_conflicts': resource_conflicts
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/schedule', methods=['POST'])
def run_schedule():
    """
    Run the CP-SAT scheduler to generate an initial schedule
    
    Optional JSON body:
    {
        "start_date": "2025-04-20",
        "end_date": "2025-05-01"
    }
    """
    try:
        # Get optional parameters from request
        # Use get_json with silent=True to avoid errors if no JSON is provided
        data = request.get_json(silent=True) or {}
        
        # Run the full initial scheduler
        try:
            print("Running CP-SAT scheduler...")
            # The cp_sat_scheduler function already calls auto_assign_resources_to_tasks internally
            # so we only need to call it once
            cp_sat_scheduler()
            
            print("Initial scheduling completed successfully")
        except Exception as scheduler_error:
            print(f"Scheduler error: {scheduler_error}")
            import traceback
            traceback.print_exc()
            
            # Generate a sample schedule if the scheduler fails
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if tasks table exists and has data
            cur.execute("SELECT COUNT(*) FROM tasks")
            task_count = cur.fetchone()[0]
            
            if task_count == 0:
                # Create sample tasks if none exist
                print("No tasks found. Creating sample tasks...")
                cur.execute("""
                    INSERT INTO tasks (task_name, description, estimated_hours, priority, phase, preemptable)
                    VALUES 
                    ('Foundation Work', 'Prepare and pour foundation', 40, 1, 'Foundation', FALSE),
                    ('Framing', 'Frame the structure', 60, 2, 'Structure', FALSE),
                    ('Electrical', 'Install electrical systems', 30, 3, 'Systems', TRUE),
                    ('Plumbing', 'Install plumbing systems', 25, 3, 'Systems', TRUE),
                    ('Roofing', 'Install roof', 20, 2, 'Structure', FALSE),
                    ('Drywall', 'Install and finish drywall', 35, 4, 'Interior', TRUE),
                    ('Painting', 'Paint interior and exterior', 25, 5, 'Finishing', TRUE),
                    ('Flooring', 'Install flooring', 20, 5, 'Finishing', TRUE),
                    ('Landscaping', 'Complete outdoor landscaping', 15, 6, 'Exterior', TRUE),
                    ('Final Inspection', 'Complete final inspection', 5, 7, 'Completion', FALSE)
                    ON CONFLICT DO NOTHING
                """)
                conn.commit()
            
            # Generate a simple schedule
            print("Generating a sample schedule...")
            
            # Clear existing schedules
            cur.execute("DELETE FROM schedules")
            
            # Get all tasks
            cur.execute("SELECT task_id, estimated_hours FROM tasks ORDER BY priority")
            tasks = cur.fetchall()
            
            # Create a simple sequential schedule
            start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            for task in tasks:
                task_id, duration = task
                
                # Calculate end date (assuming 8-hour workdays)
                days_needed = duration // 8
                hours_remaining = duration % 8
                
                end_date = start_date + timedelta(days=days_needed)
                if hours_remaining > 0:
                    end_date = end_date + timedelta(hours=hours_remaining)
                
                # Insert into schedules
                cur.execute("""
                    INSERT INTO schedules (task_id, planned_start, planned_end, status)
                    VALUES (%s, %s, %s, 'Scheduled')
                    ON CONFLICT (task_id) DO UPDATE SET
                        planned_start = EXCLUDED.planned_start,
                        planned_end = EXCLUDED.planned_end,
                        status = EXCLUDED.status
                """, (task_id, start_date, end_date))
                
                # Move start date to next task (add a day to ensure separation)
                start_date = end_date + timedelta(days=1)
                start_date = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            conn.commit()
            cur.close()
            
            # Try to auto-assign resources even for the fallback schedule
            try:
                print("Auto-assigning resources to fallback schedule...")
                # Make sure we're not clearing existing assignments since we just created them
                auto_assign_resources_to_tasks(clear_existing=False)
            except Exception as assign_error:
                print(f"Error auto-assigning resources to fallback schedule: {assign_error}")
                traceback.print_exc()
        
        # Fetch the generated schedule from the database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT s.task_id, t.task_name, s.planned_start, s.planned_end, 
                   s.status, t.priority, t.phase
            FROM schedules s
            JOIN tasks t ON s.task_id = t.task_id
            ORDER BY s.planned_start
        """)
        
        schedules = cur.fetchall()
        
        # Convert datetime objects to ISO format strings
        for schedule in schedules:
            schedule['start_iso'] = schedule['planned_start'].isoformat() if schedule['planned_start'] else None
            schedule['end_iso'] = schedule['planned_end'].isoformat() if schedule['planned_end'] else None
            
            # Fetch dependencies for this task
            cur.execute("""
                SELECT depends_on_task_id, lag_hours, dependency_type
                FROM dependencies
                WHERE task_id = %s
            """, (schedule['task_id'],))
            
            dependencies = cur.fetchall()
            schedule['dependencies'] = [dict(dep) for dep in dependencies]
        
        cur.close()
        conn.close()
        
        return jsonify(schedules)
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/reschedule/event', methods=['POST'])
def reschedule_event():
    """
    Handle a rescheduling event
    
    Required JSON body:
    {
        "task_id": 123,
        "event_type": "pause|resume|complete|skip|manual_reschedule|clock_in|clock_out",
        "timestamp": "2025-04-20T14:30:00",
        "details": {
            // Event-specific details
            "reason": "Short break",
            "duration_minutes": 15,  // For pause events
            "new_start": "2025-04-20T16:00:00",  // For manual_reschedule
            "new_end": "2025-04-20T18:00:00",    // For manual_reschedule
            "completed_percentage": 70,          // For clock_out events
            "remaining_hours": 2.5,              // For clock_out events at end of day
            "carry_over": true                   // For clock_out events
        }
    }
    """
    try:
        data = request.json
        
        if not data or not all(k in data for k in ['task_id', 'event_type', 'timestamp']):
            return jsonify({"error": "Missing required fields"}), 400
        
        task_id = data['task_id']
        event_type = data['event_type']
        timestamp = datetime.fromisoformat(data['timestamp'])
        details = data.get('details', {})
        
        # Call the rescheduler's handle_event function
        result = handle_event(
            task_id=task_id,
            event_type=event_type,
            timestamp=timestamp,
            details=details
        )
        
        print(f"Event result: {result}")
        
        # Fetch updated schedules
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT s.task_id, t.task_name, s.planned_start, s.planned_end, 
                   s.actual_start, s.actual_end, s.status, t.priority, t.phase
            FROM schedules s
            JOIN tasks t ON s.task_id = t.task_id
            ORDER BY s.planned_start
        """)
        
        schedules = cur.fetchall()
        
        # Convert datetime objects to ISO format strings
        for schedule in schedules:
            schedule['planned_start_iso'] = schedule['planned_start'].isoformat() if schedule['planned_start'] else None
            schedule['planned_end_iso'] = schedule['planned_end'].isoformat() if schedule['planned_end'] else None
            schedule['actual_start_iso'] = schedule['actual_start'].isoformat() if schedule['actual_start'] else None
            schedule['actual_end_iso'] = schedule['actual_end'].isoformat() if schedule['actual_end'] else None
        
        # Fetch recent change log entries
        cur.execute("""
            SELECT * FROM schedule_change_log
            ORDER BY change_id DESC
            LIMIT 10
        """)
        
        change_log = cur.fetchall()
        
        # Fetch recent pause log entries
        cur.execute("""
            SELECT * FROM task_pause_log
            ORDER BY pause_id DESC
            LIMIT 10
        """)
        
        pause_log = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Include any rescheduled tasks in the response
        response_data = {
            "success": result.get("success", True),
            "message": result.get("message", "Operation completed"),
            "schedules": schedules,
            "change_log": [dict(log) for log in change_log],
            "pause_log": [dict(log) for log in pause_log]
        }
        
        # Add rescheduled tasks if present
        if "rescheduled_tasks" in result:
            response_data["rescheduled_tasks"] = result["rescheduled_tasks"]
            
        return jsonify(response_data)
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    """
    Get all scheduled tasks
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT s.task_id, t.task_name, s.planned_start, s.planned_end, 
                   s.actual_start, s.actual_end, s.status, t.priority, t.phase
            FROM schedules s
            JOIN tasks t ON s.task_id = t.task_id
            ORDER BY s.planned_start
        """)
        
        schedules = cur.fetchall()
        
        # Convert datetime objects to ISO format strings
        for schedule in schedules:
            schedule['planned_start_iso'] = schedule['planned_start'].isoformat() if schedule['planned_start'] else None
            schedule['planned_end_iso'] = schedule['planned_end'].isoformat() if schedule['planned_end'] else None
            schedule['actual_start_iso'] = schedule['actual_start'].isoformat() if schedule['actual_start'] else None
            schedule['actual_end_iso'] = schedule['actual_end'].isoformat() if schedule['actual_end'] else None
            
            # Calculate delay or ahead time
            if schedule['actual_end'] and schedule['planned_end']:
                delta = schedule['actual_end'] - schedule['planned_end']
                hours = delta.total_seconds() / 3600
                schedule['delay_or_ahead'] = f"{'+' if hours >= 0 else ''}{hours:.1f}h"
            else:
                schedule['delay_or_ahead'] = "0h"
        
        cur.close()
        conn.close()
        
        return jsonify(schedules)
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/schedules/log', methods=['GET'])
def get_schedule_logs():
    """
    Get recent entries from schedule_change_log and task_pause_log
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if schedule_change_log table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'schedule_change_log'
            ) as exists
        """)
        
        result = cur.fetchone()
        change_log_exists = result['exists'] if result else False
        
        if change_log_exists:
            # Fetch recent change log entries
            cur.execute("""
                SELECT scl.change_id, scl.task_id, t.task_name, 
                       scl.previous_start, scl.previous_end, 
                       scl.new_start, scl.new_end, 
                       scl.change_type, scl.reason, scl.created_at as change_time
                FROM schedule_change_log scl
                JOIN tasks t ON scl.task_id = t.task_id
                ORDER BY scl.change_id DESC
                LIMIT 20
            """)
            
            change_log = cur.fetchall()
        else:
            change_log = []
        
        # Convert datetime objects to ISO format strings
        if change_log_exists and change_log:
            for log in change_log:
                log['previous_start_iso'] = log['previous_start'].isoformat() if log['previous_start'] else None
                log['previous_end_iso'] = log['previous_end'].isoformat() if log['previous_end'] else None
                log['new_start_iso'] = log['new_start'].isoformat() if log['new_start'] else None
                log['new_end_iso'] = log['new_end'].isoformat() if log['new_end'] else None
                log['change_time_iso'] = log['change_time'].isoformat() if log['change_time'] else None
        
        # Check if task_pause_log table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'task_pause_log'
            ) as exists
        """)
        
        result = cur.fetchone()
        pause_log_exists = result['exists'] if result else False
        
        if pause_log_exists:
            # Fetch recent pause log entries
            cur.execute("""
                SELECT tpl.pause_id, tpl.task_id, t.task_name, 
                       tpl.start_time, tpl.end_time, 
                       tpl.reason, tpl.duration_minutes, tpl.is_on_hold
                FROM task_pause_log tpl
                JOIN tasks t ON tpl.task_id = t.task_id
                ORDER BY tpl.pause_id DESC
                LIMIT 20
            """)
            
            pause_log = cur.fetchall()
        else:
            pause_log = []
        
        # Convert datetime objects to ISO format strings
        if pause_log_exists and pause_log:
            for log in pause_log:
                log['start_time_iso'] = log['start_time'].isoformat() if log['start_time'] else None
                log['end_time_iso'] = log['end_time'].isoformat() if log['end_time'] else None
        
        # Check if task_progress table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'task_progress'
            ) as exists
        """)
        
        result = cur.fetchone()
        task_progress_exists = result['exists'] if result else False
        
        if task_progress_exists:
            # Fetch task progress logs
            cur.execute("""
                SELECT tp.progress_id, tp.task_id, t.task_name, 
                       tp.start_time, tp.end_time, 
                       tp.status, tp.notes
                FROM task_progress tp
                JOIN tasks t ON tp.task_id = t.task_id
                ORDER BY tp.progress_id DESC
                LIMIT 20
            """)
            
            progress_log = cur.fetchall()
        else:
            progress_log = []
        
        # Convert datetime objects to ISO format strings
        if task_progress_exists:
            for log in progress_log:
                log['start_time_iso'] = log['start_time'].isoformat() if log['start_time'] else None
                log['end_time_iso'] = log['end_time'].isoformat() if log['end_time'] else None
        
        # Combine and sort logs by time
        combined_logs = []
        
        if change_log_exists and change_log:
            for log in change_log:
                combined_logs.append({
                    'time': log['change_time'],
                    'time_iso': log['change_time_iso'],
                    'type': 'change',
                    'message': f"Task {log['task_id']} ({log['task_name']}) {log['change_type'].lower()} from {log['previous_start']} to {log['new_start']} due to {log['reason']}",
                    'details': log
                })
        
        if pause_log_exists and pause_log:
            for log in pause_log:
                status = "paused" if log['is_on_hold'] else ("resumed" if log['end_time'] else "paused")
                combined_logs.append({
                    'time': log['start_time'],
                    'time_iso': log['start_time_iso'],
                    'type': 'pause',
                    'message': f"Task {log['task_id']} ({log['task_name']}) {status} for {log['duration_minutes']} minutes due to {log['reason']}",
                    'details': log
                })
            
        if task_progress_exists and progress_log:
            for log in progress_log:
                action = "clocked in" if log['status'] == 'In Progress' and not log['end_time'] else \
                        "clocked out" if log['status'] == 'Paused' and log['end_time'] else \
                        "completed" if log['status'] == 'Completed' else log['status']
                
                duration = ""
                if log['end_time'] and log['start_time']:
                    minutes = (log['end_time'] - log['start_time']).total_seconds() / 60
                    duration = f" (worked for {minutes:.0f} minutes)"
                    
                combined_logs.append({
                    'time': log['start_time'],
                    'time_iso': log['start_time_iso'],
                    'type': 'progress',
                    'message': f"Task {log['task_id']} ({log['task_name']}) {action}{duration}: {log['notes']}",
                    'details': log
                })
        
        # Sort by time, most recent first
        combined_logs.sort(key=lambda x: x['time'], reverse=True)
        
        cur.close()
        conn.close()
        
        response_data = {
            'combined_logs': combined_logs[:20]  # Return top 20 most recent logs
        }
        
        if change_log_exists:
            response_data['change_log'] = [dict(log) for log in change_log]
        else:
            response_data['change_log'] = []
            
        if pause_log_exists:
            response_data['pause_log'] = [dict(log) for log in pause_log]
        else:
            response_data['pause_log'] = []
            
        if task_progress_exists:
            response_data['progress_log'] = [dict(log) for log in progress_log]
        else:
            response_data['progress_log'] = []
            
        return jsonify(response_data)
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Error in get_schedule_logs: {str(e)}")
        print(f"Traceback: {error_traceback}")
        return jsonify({"error": str(e), "traceback": error_traceback}), 500

@app.route('/api/resources', methods=['GET'])
def get_resources():
    """
    Get all resources
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if the resources table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'resources'
            ) as exists
        """)
        
        if not cur.fetchone()['exists']:
            # If resources table doesn't exist, return empty list
            return jsonify([])
        
        # Check which columns exist in the resources table
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'resources'
        """)
        
        columns = [row['column_name'] for row in cur.fetchall()]
        
        # Build a dynamic query based on existing columns
        select_columns = ['resource_id', 'name']
        if 'type' in columns:
            select_columns.append('type')
        else:
            select_columns.append("'Unknown' as type")
            
        if 'availability' in columns:
            select_columns.append('availability')
        else:
            select_columns.append('TRUE as availability')
            
        if 'last_maintenance' in columns:
            select_columns.append('last_maintenance')
        else:
            select_columns.append('NULL as last_maintenance')
        
        query = f"""
            SELECT {', '.join(select_columns)}
            FROM resources
            ORDER BY name
        """
        
        cur.execute(query)
        resources = cur.fetchall()
        
        # Convert datetime objects to ISO format strings
        for resource in resources:
            resource['last_maintenance_iso'] = resource['last_maintenance'].isoformat() if resource['last_maintenance'] else None
        
        cur.close()
        conn.close()
        
        return jsonify(resources)
    
    except Exception as e:
        print(f"Error in get_resources: {e}")
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/employees', methods=['GET'])
def get_employees():
    """
    Get all employees
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # First check if roles table exists and if employees has role_id column
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'roles'
            ) as roles_exist,
            EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'employees' AND column_name = 'role_id'
            ) as role_id_exists
        """)
        
        result = cur.fetchone()
        roles_exist = result['roles_exist']
        role_id_exists = result['role_id_exists']
        
        # If both roles table and role_id column exist, use the join query
        if roles_exist and role_id_exists:
            try:
                cur.execute("""
                    SELECT e.employee_id, e.name, e.contact, e.skill_set, 
                           r.role_id, r.role_name
                    FROM employees e
                    JOIN roles r ON e.role_id = r.role_id
                    ORDER BY e.name
                """)
                employees = cur.fetchall()
            except Exception as join_error:
                print(f"Error joining with roles table: {join_error}")
                # Fallback to basic query without join
                cur.execute("""
                    SELECT employee_id, name, contact, skill_set, 
                           NULL as role_id, 
                           COALESCE(role_name, 'Unknown') as role_name
                    FROM employees
                    ORDER BY name
                """)
                employees = cur.fetchall()
        else:
            # Use a query that works with the existing schema
            # Check if role_name column exists directly in employees table
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'employees' AND column_name = 'role_name'
                ) as role_name_exists
            """)
            
            role_name_exists = cur.fetchone()['role_name_exists']
            
            if role_name_exists:
                # If role_name exists directly in employees table, use it
                cur.execute("""
                    SELECT employee_id, name, contact, skill_set, 
                           NULL as role_id, role_name
                    FROM employees
                    ORDER BY name
                """)
            else:
                # Otherwise, provide a default value for role_name
                cur.execute("""
                    SELECT employee_id, name, contact, skill_set,
                           NULL as role_id, 'Unknown' as role_name
                    FROM employees
                    ORDER BY name
                """)
            
            employees = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify(employees)
    
    except Exception as e:
        print(f"Error in get_employees: {e}")
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """
    Get all tasks
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT task_id, project_id, wbs, task_name, 
                   estimated_days, estimated_hours, 
                   task_type, phase, priority
            FROM tasks
            ORDER BY task_id
        """)
        
        tasks = cur.fetchall()
        
        # For each task, get its dependencies
        for task in tasks:
            cur.execute("""
                SELECT depends_on_task_id, lag_hours, dependency_type
                FROM dependencies
                WHERE task_id = %s
            """, (task['task_id'],))
            
            dependencies = cur.fetchall()
            task['dependencies'] = [dict(dep) for dep in dependencies]
            
            # Get required employees
            cur.execute("""
                SELECT resource_type, resource_group, resource_count
                FROM task_required_employees
                WHERE task_id = %s
            """, (task['task_id'],))
            
            employees = cur.fetchall()
            task['required_employees'] = [dict(emp) for emp in employees]
            
            # Get required resources
            cur.execute("""
                SELECT resource_type, resource_category, resource_count
                FROM task_required_resources
                WHERE task_id = %s
            """, (task['task_id'],))
            
            resources = cur.fetchall()
            task['required_resources'] = [dict(res) for res in resources]
            
            # Get schedule information
            cur.execute("""
                SELECT planned_start, planned_end, status
                FROM schedules
                WHERE task_id = %s
            """, (task['task_id'],))
            
            schedule = cur.fetchone()
            if schedule:
                task['planned_start'] = schedule['planned_start']
                task['planned_end'] = schedule['planned_end']
                task['status'] = schedule['status']
        
        cur.close()
        conn.close()
        
        return jsonify(tasks)
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """
    Update task details
    
    JSON body:
    {
        "task_name": "Updated Task Name",
        "estimated_hours": 5,
        "phase": "activeConstruction",
        "priority": 2,
        "dependencies": [
            {"depends_on_task_id": 1, "lag_hours": 2, "dependency_type": "FS"}
        ]
    }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if task exists
        cur.execute("SELECT task_id FROM tasks WHERE task_id = %s", (task_id,))
        if not cur.fetchone():
            return jsonify({"error": f"Task with ID {task_id} not found"}), 404
        
        # Update task details
        update_fields = []
        update_values = []
        
        if 'task_name' in data:
            update_fields.append("task_name = %s")
            update_values.append(data['task_name'])
        
        if 'estimated_hours' in data:
            update_fields.append("estimated_hours = %s")
            update_values.append(data['estimated_hours'])
        
        if 'estimated_days' in data:
            update_fields.append("estimated_days = %s")
            update_values.append(data['estimated_days'])
        
        if 'phase' in data:
            update_fields.append("phase = %s")
            update_values.append(data['phase'])
        
        if 'priority' in data:
            update_fields.append("priority = %s")
            update_values.append(data['priority'])
        
        if update_fields:
            query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = %s"
            update_values.append(task_id)
            cur.execute(query, update_values)
        
        # Update dependencies if provided
        if 'dependencies' in data:
            # Delete existing dependencies
            cur.execute("DELETE FROM dependencies WHERE task_id = %s", (task_id,))
            
            # Insert new dependencies
            for dep in data['dependencies']:
                depends_on_task_id = dep.get('depends_on_task_id')
                lag_hours = dep.get('lag_hours', 0)
                dependency_type = dep.get('dependency_type', 'FS')  # Default to Finish-to-Start
                
                if depends_on_task_id:
                    try:
                        # First check if this dependency already exists
                        cur.execute("""
                            SELECT COUNT(*) as count
                            FROM dependencies
                            WHERE task_id = %s AND depends_on_task_id = %s
                        """, (task_id, depends_on_task_id))
                        
                        existing = cur.fetchone()
                        if existing and existing['count'] > 0:
                            # Update existing dependency instead of inserting
                            cur.execute("""
                                UPDATE dependencies
                                SET lag_hours = %s, dependency_type = %s
                                WHERE task_id = %s AND depends_on_task_id = %s
                            """, (lag_hours, dependency_type, task_id, depends_on_task_id))
                            continue
                        
                        # Get the next available dependency_id
                        cur.execute("SELECT MAX(dependency_id) as max_id FROM dependencies")
                        max_id_result = cur.fetchone()
                        next_id = 1
                        if max_id_result and max_id_result['max_id'] is not None:
                            next_id = max_id_result['max_id'] + 1
                        
                        # Insert with explicit ID to avoid conflicts
                        cur.execute("""
                            INSERT INTO dependencies (dependency_id, task_id, depends_on_task_id, lag_hours, dependency_type)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (next_id, task_id, depends_on_task_id, lag_hours, dependency_type))
                    except Exception as e:
                        print(f"Error inserting dependency: {e}")
                        # Try a more basic approach as a last resort
                        try:
                            # Get the next available dependency_id again (in case of concurrent updates)
                            cur.execute("SELECT MAX(dependency_id) as max_id FROM dependencies")
                            max_id_result = cur.fetchone()
                            next_id = 1
                            if max_id_result and max_id_result['max_id'] is not None:
                                next_id = max_id_result['max_id'] + 1
                            
                            cur.execute("""
                                INSERT INTO dependencies (dependency_id, task_id, depends_on_task_id)
                                VALUES (%s, %s, %s)
                            """, (next_id + 1, task_id, depends_on_task_id))
                        except Exception as e2:
                            print(f"Final attempt to insert dependency failed: {e2}")
        
        # Determine if we need to reschedule
        needs_reschedule = False
        reschedule_message = ""
        
        # If estimated_hours changed, we need to reschedule
        if 'estimated_hours' in data or 'estimated_days' in data:
            needs_reschedule = True
            reschedule_message = "Task duration was updated."
        
        # If dependencies changed, we need to reschedule
        if 'dependencies' in data:
            needs_reschedule = True
            reschedule_message = "Task dependencies were updated."
        
        # If phase changed, we need to reschedule
        if 'phase' in data:
            needs_reschedule = True
            reschedule_message = "Task phase was updated."
        
        conn.commit()
        
        # If we need to reschedule, do it now
        if needs_reschedule:
            # Close the current connection before running the scheduler
            conn.commit()
            cur.close()
            conn.close()
            
            # Run a full reschedule (like the FullRescheduleButton does)
            try:
                result = run_partial_reschedule()
                # Return the result directly from run_partial_reschedule
                return jsonify({
                    "message": f"Task {task_id} updated successfully. {reschedule_message}",
                    "needs_reschedule": needs_reschedule,
                    "reschedule_message": reschedule_message,
                    "reschedule_result": result.json if hasattr(result, 'json') else result
                })
            except Exception as e:
                return jsonify({
                    "message": f"Task {task_id} updated successfully, but there was an error during rescheduling: {str(e)}",
                    "needs_reschedule": needs_reschedule,
                    "reschedule_message": reschedule_message,
                    "reschedule_error": str(e)
                })
        
        # Only close connections if we didn't already do so for rescheduling
        if 'cur' in locals() and not cur.closed:
            cur.close()
        if 'conn' in locals() and not conn.closed:
            conn.close()
        
        return jsonify({
            "message": f"Task {task_id} updated successfully",
            "needs_reschedule": needs_reschedule,
            "reschedule_message": reschedule_message
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/schedules/<int:task_id>', methods=['PUT'])
def update_task_schedule(task_id):
    """
    Update task schedule (planned start and end dates)
    
    JSON body:
    {
        "planned_start": "2023-06-01T09:00:00",
        "planned_end": "2023-06-02T17:00:00"
    }
    
    Query parameters:
    - check_only: If true, only check for conflicts without updating the schedule
    
    This endpoint will:
    1. Update the schedule for the specified task
    2. Reschedule all dependent tasks
    3. Return the updated schedule and any resource conflicts
    """
    # Check if this is a validation-only request
    check_only = request.args.get('check_only', 'false').lower() == 'true'
    
    # Debug information
    print(f"=== Schedule Update Request ===")
    print(f"Task ID: {task_id}")
    print(f"Check only: {check_only}")
    print(f"Request args: {request.args}")
    print(f"Request data: {request.json}")
    print(f"===============================")
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        if 'planned_start' not in data and 'planned_end' not in data:
            return jsonify({"error": "At least one of planned_start or planned_end must be provided"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if task exists
        cur.execute("SELECT task_id FROM tasks WHERE task_id = %s", (task_id,))
        if not cur.fetchone():
            return jsonify({"error": f"Task with ID {task_id} not found"}), 404
        
        # Check if schedule exists
        cur.execute("SELECT schedule_id, planned_start, planned_end, status FROM schedules WHERE task_id = %s", (task_id,))
        schedule = cur.fetchone()
        
        if not schedule:
            return jsonify({"error": f"No schedule found for task with ID {task_id}"}), 404
        
        # Don't allow updating completed or skipped tasks
        if schedule['status'] in ['Completed', 'Skipped']:
            return jsonify({"error": f"Cannot update schedule for task with status {schedule['status']}"}), 400
            
        # Get the new planned start and end dates
        new_planned_start = data.get('planned_start')
        new_planned_end = data.get('planned_end')
        
        print(f"Raw planned start: {new_planned_start}")
        print(f"Raw planned end: {new_planned_end}")
        
        if new_planned_start:
            try:
                # Check if the format is our custom YYYY-MM-DD HH:MM:SS format
                if ' ' in new_planned_start:
                    print(f"Parsing planned start as local time: {new_planned_start}")
                    new_planned_start = datetime.strptime(new_planned_start, "%Y-%m-%d %H:%M:%S")
                    print(f"Parsed local time: {new_planned_start}")
                else:
                    # Try ISO format with timezone handling
                    print(f"Parsing planned start as ISO: {new_planned_start}")
                    new_planned_start = datetime.fromisoformat(new_planned_start.replace('Z', '+00:00'))
                    print(f"After fromisoformat: {new_planned_start}")
                    new_planned_start = new_planned_start.replace(tzinfo=None)
                    print(f"After removing tzinfo: {new_planned_start}")
            except Exception as e:
                print(f"Error parsing planned start: {e}")
                # Try alternative parsing methods
                try:
                    new_planned_start = datetime.strptime(new_planned_start, "%Y-%m-%dT%H:%M:%S.%fZ")
                    print(f"Parsed with strptime: {new_planned_start}")
                except Exception as e2:
                    print(f"Second parsing attempt failed: {e2}")
                    try:
                        # Last resort - try to extract time components from the string
                        print(f"Attempting to extract time components from: {new_planned_start}")
                        # This is a very basic extraction - adjust as needed
                        if ":" in new_planned_start:
                            time_parts = new_planned_start.split(":")
                            if len(time_parts) >= 2:
                                hour = int(time_parts[0][-2:])
                                minute = int(time_parts[1])
                                # Use today's date with the specified time
                                today = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                                new_planned_start = today
                                print(f"Created time from components: {new_planned_start}")
                    except Exception as e3:
                        print(f"Final parsing attempt failed: {e3}")
        
        if new_planned_end:
            try:
                # Check if the format is our custom YYYY-MM-DD HH:MM:SS format
                if ' ' in new_planned_end:
                    print(f"Parsing planned end as local time: {new_planned_end}")
                    new_planned_end = datetime.strptime(new_planned_end, "%Y-%m-%d %H:%M:%S")
                    print(f"Parsed local time: {new_planned_end}")
                else:
                    # Try ISO format with timezone handling
                    print(f"Parsing planned end as ISO: {new_planned_end}")
                    new_planned_end = datetime.fromisoformat(new_planned_end.replace('Z', '+00:00'))
                    print(f"After fromisoformat: {new_planned_end}")
                    new_planned_end = new_planned_end.replace(tzinfo=None)
                    print(f"After removing tzinfo: {new_planned_end}")
            except Exception as e:
                print(f"Error parsing planned end: {e}")
                # Try alternative parsing methods
                try:
                    new_planned_end = datetime.strptime(new_planned_end, "%Y-%m-%dT%H:%M:%S.%fZ")
                    print(f"Parsed with strptime: {new_planned_end}")
                except Exception as e2:
                    print(f"Second parsing attempt failed: {e2}")
                    try:
                        # Last resort - try to extract time components from the string
                        print(f"Attempting to extract time components from: {new_planned_end}")
                        # This is a very basic extraction - adjust as needed
                        if ":" in new_planned_end:
                            time_parts = new_planned_end.split(":")
                            if len(time_parts) >= 2:
                                hour = int(time_parts[0][-2:])
                                minute = int(time_parts[1])
                                # Use today's date with the specified time
                                today = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                                new_planned_end = today
                                print(f"Created time from components: {new_planned_end}")
                    except Exception as e3:
                        print(f"Final parsing attempt failed: {e3}")
            
        # Validate dependencies - check if all dependencies will be completed before this task starts
        if new_planned_start:
            cur.execute("""
                SELECT d.depends_on_task_id, t.task_name, s.planned_start, s.planned_end, 
                       d.dependency_type, d.lag_hours
                FROM dependencies d
                JOIN tasks t ON d.depends_on_task_id = t.task_id
                JOIN schedules s ON t.task_id = s.task_id
                WHERE d.task_id = %s AND s.status != 'Completed'
            """, (task_id,))
            
            dependencies = cur.fetchall()
            dependency_warnings = []
            
            for dep in dependencies:
                lag_time = timedelta(hours=float(dep['lag_hours'] or 0))
                
                if dep['dependency_type'] == 'FS' and dep['planned_end'] and new_planned_start:
                    # For Finish-to-Start dependencies, the dependency must finish before this task starts
                    if dep['planned_end'] + lag_time > new_planned_start:
                        dependency_warnings.append({
                            "task_id": dep['depends_on_task_id'],
                            "task_name": dep['task_name'],
                            "end_time": dep['planned_end'].isoformat(),
                            "dependency_type": dep['dependency_type'],
                            "lag_hours": dep['lag_hours']
                        })
                elif dep['dependency_type'] == 'SS' and dep['planned_start'] and new_planned_start:
                    # For Start-to-Start dependencies, the dependency must start before this task starts
                    if dep['planned_start'] + lag_time > new_planned_start:
                        dependency_warnings.append({
                            "task_id": dep['depends_on_task_id'],
                            "task_name": dep['task_name'],
                            "start_time": dep['planned_start'].isoformat(),
                            "dependency_type": dep['dependency_type'],
                            "lag_hours": dep['lag_hours']
                        })
                elif dep['dependency_type'] == 'FF' and dep['planned_end'] and new_planned_end:
                    # For Finish-to-Finish dependencies, the dependency must finish before this task finishes
                    if dep['planned_end'] + lag_time > new_planned_end:
                        dependency_warnings.append({
                            "task_id": dep['depends_on_task_id'],
                            "task_name": dep['task_name'],
                            "end_time": dep['planned_end'].isoformat(),
                            "dependency_type": dep['dependency_type'],
                            "lag_hours": dep['lag_hours']
                        })
                elif dep['dependency_type'] == 'SF' and dep['planned_start'] and new_planned_end:
                    # For Start-to-Finish dependencies, the dependency must start before this task finishes
                    if dep['planned_start'] + lag_time > new_planned_end:
                        dependency_warnings.append({
                            "task_id": dep['depends_on_task_id'],
                            "task_name": dep['task_name'],
                            "start_time": dep['planned_start'].isoformat(),
                            "dependency_type": dep['dependency_type'],
                            "lag_hours": dep['lag_hours']
                        })
        
        # Check resource availability during the new time window
        resource_conflicts = []
        employee_conflicts = []
        
        if new_planned_start and new_planned_end:
            # Check for resource conflicts
            cur.execute("""
                WITH task_assignments AS (
                    SELECT r.resource_id, r.name as resource_name
                    FROM resource_assignments ra
                    JOIN resources r ON ra.resource_id = r.resource_id
                    WHERE ra.task_id = %s
                )
                SELECT 
                    ta.resource_id,
                    ta.resource_name,
                    t.task_id,
                    t.task_name,
                    s.planned_start,
                    s.planned_end,
                    s.status
                FROM task_assignments ta
                JOIN resource_assignments ra ON ta.resource_id = ra.resource_id
                JOIN tasks t ON ra.task_id = t.task_id
                JOIN schedules s ON t.task_id = s.task_id
                WHERE 
                    ra.task_id != %s AND
                    s.status NOT IN ('Completed', 'Skipped') AND
                    s.planned_start < %s AND
                    s.planned_end > %s
            """, (task_id, task_id, new_planned_end, new_planned_start))
            
            resource_conflicts = cur.fetchall()
            
            # Check for employee conflicts
            cur.execute("""
                WITH task_assignments AS (
                    SELECT e.employee_id, e.name as employee_name
                    FROM employee_assignments ea
                    JOIN employees e ON ea.employee_id = e.employee_id
                    WHERE ea.task_id = %s
                )
                SELECT 
                    ta.employee_id,
                    ta.employee_name,
                    t.task_id,
                    t.task_name,
                    s.planned_start,
                    s.planned_end,
                    s.status
                FROM task_assignments ta
                JOIN employee_assignments ea ON ta.employee_id = ea.employee_id
                JOIN tasks t ON ea.task_id = t.task_id
                JOIN schedules s ON t.task_id = s.task_id
                WHERE 
                    ea.task_id != %s AND
                    s.status NOT IN ('Completed', 'Skipped') AND
                    s.planned_start < %s AND
                    s.planned_end > %s
            """, (task_id, task_id, new_planned_end, new_planned_start))
            
            employee_conflicts = cur.fetchall()
        
        # If this is a check-only request, we don't update the database
        if not check_only:
            # Update schedule
            update_fields = []
            update_values = []
            
            if 'planned_start' in data:
                update_fields.append("planned_start = %s")
                update_values.append(data['planned_start'])
            
            if 'planned_end' in data:
                update_fields.append("planned_end = %s")
                update_values.append(data['planned_end'])
            
            if update_fields:
                query = f"UPDATE schedules SET {', '.join(update_fields)} WHERE task_id = %s"
                update_values.append(task_id)
                cur.execute(query, update_values)
        
        # Check for resource conflicts after updating the schedule
        cur.execute("""
            WITH task_times AS (
                SELECT 
                    t.task_id,
                    t.task_name,
                    s.planned_start,
                    s.planned_end,
                    s.status
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                WHERE s.status NOT IN ('Completed', 'Skipped')
            )
            SELECT 
                a1.resource_id,
                r.name as resource_name,
                a1.task_id as task1_id,
                t1.task_name as task1_name,
                t1.planned_start as task1_start,
                t1.planned_end as task1_end,
                a2.task_id as task2_id,
                t2.task_name as task2_name,
                t2.planned_start as task2_start,
                t2.planned_end as task2_end
            FROM resource_assignments a1
            JOIN resource_assignments a2 ON 
                a1.resource_id = a2.resource_id AND
                a1.task_id < a2.task_id
            JOIN task_times t1 ON a1.task_id = t1.task_id
            JOIN task_times t2 ON a2.task_id = t2.task_id
            JOIN resources r ON a1.resource_id = r.resource_id
            WHERE 
                t1.planned_start < t2.planned_end AND
                t2.planned_start < t1.planned_end AND
                (t1.task_id = %s OR t2.task_id = %s)
        """, (task_id, task_id))
        
        resource_conflicts = cur.fetchall()
        
        # Also check for employee conflicts
        cur.execute("""
            WITH task_times AS (
                SELECT 
                    t.task_id,
                    t.task_name,
                    s.planned_start,
                    s.planned_end,
                    s.status
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                WHERE s.status NOT IN ('Completed', 'Skipped')
            )
            SELECT 
                a1.employee_id,
                e.name as employee_name,
                a1.task_id as task1_id,
                t1.task_name as task1_name,
                t1.planned_start as task1_start,
                t1.planned_end as task1_end,
                a2.task_id as task2_id,
                t2.task_name as task2_name,
                t2.planned_start as task2_start,
                t2.planned_end as task2_end
            FROM employee_assignments a1
            JOIN employee_assignments a2 ON 
                a1.employee_id = a2.employee_id AND
                a1.task_id < a2.task_id
            JOIN task_times t1 ON a1.task_id = t1.task_id
            JOIN task_times t2 ON a2.task_id = t2.task_id
            JOIN employees e ON a1.employee_id = e.employee_id
            WHERE 
                t1.planned_start < t2.planned_end AND
                t2.planned_start < t1.planned_end AND
                (t1.task_id = %s OR t2.task_id = %s)
        """, (task_id, task_id))
        
        employee_conflicts = cur.fetchall()
        
        # Get the current schedule
        cur.execute("""
            SELECT planned_start, planned_end
            FROM schedules
            WHERE task_id = %s
        """, (task_id,))
        
        original_schedule = cur.fetchone()
        
        # If this is a check-only request, return the conflicts without updating
        if check_only:
            conn.commit()
            cur.close()
            conn.close()
            
            return jsonify({
                "message": "Schedule validation completed",
                "resource_conflicts": [dict(conflict) for conflict in resource_conflicts],
                "employee_conflicts": [dict(conflict) for conflict in employee_conflicts],
                "dependency_warnings": dependency_warnings if 'dependency_warnings' in locals() else [],
                "has_conflicts": len(resource_conflicts) > 0 or len(employee_conflicts) > 0,
                "has_dependency_warnings": len(dependency_warnings) > 0 if 'dependency_warnings' in locals() else False
            })
        
        # For actual updates, commit the changes
        conn.commit()
        
        # Now get the updated schedule and estimated hours after our changes
        cur.execute("""
            SELECT s.planned_start, s.planned_end, t.estimated_hours
            FROM schedules s
            JOIN tasks t ON s.task_id = t.task_id
            WHERE s.task_id = %s
        """, (task_id,))
        
        current_schedule = cur.fetchone()
        
        print(f"Original schedule: {original_schedule}")
        print(f"Updated schedule: {current_schedule}")
        
        # Close the database connection before calling the rescheduler
        conn.commit()
        cur.close()
        conn.close()
        
        # Now update dependent tasks based on the new schedule with a fresh connection
        try:
            # Import the rescheduler function and class
            from rescheduler import ReschedulingManager
            
            # Create a rescheduling manager (this creates its own connection)
            rm = ReschedulingManager()
            
            # Get the original and new schedule times
            original_start = original_schedule['planned_start'] if original_schedule else None
            original_end = original_schedule['planned_end'] if original_schedule else None
            new_start = current_schedule['planned_start'] if current_schedule else None
            new_end = current_schedule['planned_end'] if current_schedule else None
            
            print(f"Original schedule: {original_start} to {original_end}")
            print(f"New schedule: {new_start} to {new_end}")
            
            # Make sure we have valid datetime objects
            if isinstance(new_start, str):
                try:
                    if ' ' in new_start:  # Our custom format
                        new_start = datetime.strptime(new_start, "%Y-%m-%d %H:%M:%S")
                    else:  # ISO format
                        new_start = datetime.fromisoformat(new_start.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception as e:
                    print(f"Error parsing new_start: {e}")
                    return jsonify({"error": f"Invalid start date format: {new_start}"}), 400
                    
            if isinstance(new_end, str):
                try:
                    if ' ' in new_end:  # Our custom format
                        new_end = datetime.strptime(new_end, "%Y-%m-%d %H:%M:%S")
                    else:  # ISO format
                        new_end = datetime.fromisoformat(new_end.replace('Z', '+00:00')).replace(tzinfo=None)
                except Exception as e:
                    print(f"Error parsing new_end: {e}")
                    return jsonify({"error": f"Invalid end date format: {new_end}"}), 400
                
            print(f"Calling manually_reschedule_task with: task_id={task_id}, new_start={new_start}, new_end={new_end}")
            print(f"Start hour: {new_start.hour}, minute: {new_start.minute}")
            print(f"End hour: {new_end.hour}, minute: {new_end.minute}")
            
            # Call the manual reschedule function directly
            rescheduling_result = rm.manually_reschedule_task(
                task_id, 
                new_start, 
                new_end, 
                "Manual schedule update from UI"
            )
            
            print(f"Rescheduling result: {rescheduling_result}")
            
            # Close the rescheduling manager
            rm.close()
            
            # Get a fresh connection to get the final schedule
            fresh_conn = get_db_connection()
            fresh_cur = fresh_conn.cursor(cursor_factory=RealDictCursor)
            
            fresh_cur.execute("""
                SELECT planned_start, planned_end
                FROM schedules
                WHERE task_id = %s
            """, (task_id,))
            
            final_schedule = fresh_cur.fetchone()
            print(f"Final schedule after rescheduling: {final_schedule}")
            
            fresh_cur.close()
            fresh_conn.close()
            
            # We already have the final_schedule from the fresh connection
            
            # Format the response
            response_data = {
                "message": f"Schedule for task {task_id} updated successfully and all dependent tasks have been rescheduled",
                "resource_conflicts": [dict(conflict) for conflict in resource_conflicts],
                "employee_conflicts": [dict(conflict) for conflict in employee_conflicts],
                "dependency_warnings": dependency_warnings if 'dependency_warnings' in locals() else [],
                "has_conflicts": len(resource_conflicts) > 0 or len(employee_conflicts) > 0,
                "has_dependency_warnings": len(dependency_warnings) > 0 if 'dependency_warnings' in locals() else False,
                "rescheduling_result": rescheduling_result
            }
            
            # Add updated schedule if available
            if final_schedule:
                response_data["updated_schedule"] = {
                    "planned_start": final_schedule['planned_start'].isoformat() if final_schedule['planned_start'] else None,
                    "planned_end": final_schedule['planned_end'].isoformat() if final_schedule['planned_end'] else None,
                    "estimated_hours": final_schedule['estimated_hours'] if 'estimated_hours' in final_schedule else None
                }
            elif rescheduling_result and 'new_start' in rescheduling_result and 'new_end' in rescheduling_result:
                # Use the rescheduling result if final_schedule is not available
                # Get the estimated hours from the current schedule
                estimated_hours = current_schedule['estimated_hours'] if current_schedule and 'estimated_hours' in current_schedule else None
                
                response_data["updated_schedule"] = {
                    "planned_start": rescheduling_result['new_start'].isoformat() if rescheduling_result['new_start'] else None,
                    "planned_end": rescheduling_result['new_end'].isoformat() if rescheduling_result['new_end'] else None,
                    "estimated_hours": estimated_hours
                }
            else:
                # Fallback to the current schedule
                response_data["updated_schedule"] = {
                    "planned_start": current_schedule['planned_start'].isoformat() if current_schedule and current_schedule['planned_start'] else None,
                    "planned_end": current_schedule['planned_end'].isoformat() if current_schedule and current_schedule['planned_end'] else None,
                    "estimated_hours": current_schedule['estimated_hours'] if current_schedule and 'estimated_hours' in current_schedule else None
                }
            
            # Add details about rescheduled tasks
            if rescheduling_result.get('rescheduled_tasks'):
                response_data["rescheduled_tasks"] = [
                    {
                        "task_id": task.get('task_id'),
                        "name": task.get('name'),
                        "original_start": task.get('original_start').isoformat() if task.get('original_start') else None,
                        "original_end": task.get('original_end').isoformat() if task.get('original_end') else None,
                        "new_start": task.get('new_start').isoformat() if task.get('new_start') else None,
                        "new_end": task.get('new_end').isoformat() if task.get('new_end') else None
                    }
                    for task in rescheduling_result.get('rescheduled_tasks', [])
                ]
            
            return jsonify(response_data)
        except Exception as e:
            # The connection should already be closed at this point
            print(f"Error during rescheduling: {e}")
            
            # Get a fresh connection to get the current schedule
            try:
                fresh_conn = get_db_connection()
                fresh_cur = fresh_conn.cursor(cursor_factory=RealDictCursor)
                
                fresh_cur.execute("""
                    SELECT planned_start, planned_end
                    FROM schedules
                    WHERE task_id = %s
                """, (task_id,))
                
                final_schedule = fresh_cur.fetchone()
                print(f"Current schedule in error handler: {final_schedule}")
                
                fresh_cur.close()
                fresh_conn.close()
            except Exception as query_error:
                print(f"Error getting current schedule in error handler: {query_error}")
                # Use the schedule we already have
                final_schedule = current_schedule
            
            # Format the error response
            response_data = {
                "message": f"Schedule for task {task_id} updated successfully, but there was an error during rescheduling: {str(e)}",
                "resource_conflicts": [dict(conflict) for conflict in resource_conflicts],
                "employee_conflicts": [dict(conflict) for conflict in employee_conflicts],
                "has_conflicts": len(resource_conflicts) > 0 or len(employee_conflicts) > 0,
                "rescheduling_error": str(e)
            }
            
            # Add updated schedule if available
            if current_schedule:
                response_data["updated_schedule"] = {
                    "planned_start": current_schedule['planned_start'].isoformat() if current_schedule['planned_start'] else None,
                    "planned_end": current_schedule['planned_end'].isoformat() if current_schedule['planned_end'] else None
                }
            
            return jsonify(response_data)
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/task/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """
    Get details for a specific task
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT task_id, project_id, wbs, task_name, 
                   estimated_days, estimated_hours, 
                   task_type, phase, priority
            FROM tasks
            WHERE task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            return jsonify({"error": f"Task {task_id} not found"}), 404
        
        # Get dependencies
        cur.execute("""
            SELECT depends_on_task_id, lag_hours, dependency_type
            FROM dependencies
            WHERE task_id = %s
        """, (task_id,))
        
        dependencies = cur.fetchall()
        task['dependencies'] = [dict(dep) for dep in dependencies]
        
        # Get required employees
        cur.execute("""
            SELECT resource_type, resource_group, resource_count
            FROM task_required_employees
            WHERE task_id = %s
        """, (task_id,))
        
        employees = cur.fetchall()
        task['required_employees'] = [dict(emp) for emp in employees]
        
        # Get required resources
        cur.execute("""
            SELECT resource_type, resource_category, resource_count
            FROM task_required_resources
            WHERE task_id = %s
        """, (task_id,))
        
        resources = cur.fetchall()
        task['required_resources'] = [dict(res) for res in resources]
        
        # Get schedule
        cur.execute("""
            SELECT planned_start, planned_end, actual_start, actual_end, status
            FROM schedules
            WHERE task_id = %s
        """, (task_id,))
        
        schedule = cur.fetchone()
        if schedule:
            task['schedule'] = dict(schedule)
            
            # Convert datetime objects to ISO format strings
            task['schedule']['planned_start_iso'] = task['schedule']['planned_start'].isoformat() if task['schedule']['planned_start'] else None
            task['schedule']['planned_end_iso'] = task['schedule']['planned_end'].isoformat() if task['schedule']['planned_end'] else None
            task['schedule']['actual_start_iso'] = task['schedule']['actual_start'].isoformat() if task['schedule']['actual_start'] else None
            task['schedule']['actual_end_iso'] = task['schedule']['actual_end'].isoformat() if task['schedule']['actual_end'] else None
        
        cur.close()
        conn.close()
        
        return jsonify(task)
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

# Duplicate route removed

@app.route('/api/assignments/create', methods=['POST'])
def create_assignment():
    """
    Create a new employee or resource assignment
    
    Required JSON body:
    {
        "type": "employee|resource",
        "task_id": 123,
        "entity_id": 456,  # employee_id or resource_id
        "entity_name": "John Smith"  # Optional, for display purposes
    }
    """
    try:
        data = request.json
        
        if not data or not all(k in data for k in ['type', 'task_id', 'entity_id']):
            return jsonify({"error": "Missing required fields"}), 400
        
        assignment_type = data['type']
        task_id = data['task_id']
        entity_id = data['entity_id']
        entity_name = data.get('entity_name', '')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if the task exists
        cur.execute("""
            SELECT t.*, s.planned_start, s.planned_end, s.status
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        task = cur.fetchone()
        
        if not task:
            return jsonify({"error": f"Task with ID {task_id} not found"}), 404
        
        # Check if the entity exists
        if assignment_type == 'employee':
            cur.execute("SELECT * FROM employees WHERE employee_id = %s", (entity_id,))
            entity = cur.fetchone()
            table_name = 'employee_assignments'
            id_column = 'employee_id'
            
            # Check if the task requires this type of employee
            cur.execute("""
                SELECT * FROM task_required_employees 
                WHERE task_id = %s AND LOWER(resource_group) = LOWER(%s)
            """, (task_id, entity.get('skill_set', '')))
            required_employee = cur.fetchone()
            
            if not required_employee:
                # Check if the task requires any employees
                cur.execute("SELECT * FROM task_required_employees WHERE task_id = %s", (task_id,))
                any_required = cur.fetchall()
                
                if any_required:
                    return jsonify({
                        "warning": f"Task {task_id} requires employees with skill sets: {', '.join([req['resource_group'] for req in any_required])}, but you're assigning an employee with skill set: {entity.get('skill_set', 'None')}",
                        "can_proceed": True
                    }), 200
        else:  # resource
            cur.execute("SELECT * FROM resources WHERE resource_id = %s", (entity_id,))
            entity = cur.fetchone()
            table_name = 'resource_assignments'
            id_column = 'resource_id'
            
            # Check if the task requires this type of resource
            cur.execute("""
                SELECT * FROM task_required_resources 
                WHERE task_id = %s AND LOWER(resource_category) = LOWER(%s)
            """, (task_id, entity.get('type', '')))
            required_resource = cur.fetchone()
            
            if not required_resource:
                # Check if the task requires any resources
                cur.execute("SELECT * FROM task_required_resources WHERE task_id = %s", (task_id,))
                any_required = cur.fetchall()
                
                if any_required:
                    return jsonify({
                        "warning": f"Task {task_id} requires resources of types: {', '.join([req['resource_category'] for req in any_required])}, but you're assigning a resource of type: {entity.get('type', 'None')}",
                        "can_proceed": True
                    }), 200
        
        if not entity:
            return jsonify({"error": f"{assignment_type.capitalize()} with ID {entity_id} not found"}), 404
        
        # Check if the table exists, create it if it doesn't
        cur.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table_name}'
            ) as exists
        """)
        
        result = cur.fetchone()
        table_exists = result['exists'] if result else False
        
        if not table_exists:
            # Create the table
            cur.execute(f"""
                CREATE TABLE {table_name} (
                    assignment_id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    {id_column} INTEGER NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    is_initial BOOLEAN DEFAULT FALSE,
                    is_modified BOOLEAN DEFAULT FALSE,
                    UNIQUE (task_id, {id_column}),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            conn.commit()
        
        # Check if the assignment already exists
        cur.execute(f"""
            SELECT * FROM {table_name}
            WHERE task_id = %s AND {id_column} = %s
        """, (task_id, entity_id))
        
        existing = cur.fetchone()
        
        if existing:
            return jsonify({"message": f"{assignment_type.capitalize()} assignment already exists", "assignment_id": existing['assignment_id']}), 200
        
        # Check for conflicts with other tasks
        # Get the task's planned start and end times
        task_start = task['planned_start']
        task_end = task['planned_end']
        
        if not task_start or not task_end:
            return jsonify({"error": "Task does not have planned start and end times"}), 400
        
        # Check for overlapping assignments
        cur.execute(f"""
            SELECT a.*, t.task_name, s.planned_start, s.planned_end, s.status
            FROM {table_name} a
            JOIN tasks t ON a.task_id = t.task_id
            JOIN schedules s ON a.task_id = s.task_id
            WHERE a.{id_column} = %s
            AND a.task_id != %s
            AND s.status NOT IN ('Completed', 'Skipped')
        """, (entity_id, task_id))
        
        existing_assignments = cur.fetchall()
        conflicts = []
        
        for assignment in existing_assignments:
            assignment_start = assignment['planned_start']
            assignment_end = assignment['planned_end']
            
            # Skip if the assignment doesn't have planned times
            if not assignment_start or not assignment_end:
                continue
            
            # Check for overlap
            if task_start < assignment_end and task_end > assignment_start:
                # There's a conflict
                conflict = {
                    'task_id': assignment['task_id'],
                    'task_name': assignment['task_name'],
                    'start_time': assignment_start.isoformat(),
                    'end_time': assignment_end.isoformat(),
                    'status': assignment['status']
                }
                conflicts.append(conflict)
                print(f"Found conflict: {assignment_type} {entity_id} is already assigned to task {assignment['task_id']} ({assignment['task_name']}) during overlapping time")
        
        # If there are conflicts, include them as warnings but still create the assignment
        warning_message = None
        if conflicts:
            # Format conflict warning
            conflict_count = len(conflicts)
            warning_message = f"Warning: {assignment_type.capitalize()} is already assigned to {conflict_count} other task(s) during this time period. You may need to reschedule those tasks."
            print(warning_message)
        
        # Check if this is an initial assignment (from scheduler) or a user modification
        is_initial = data.get('is_initial', False)
        is_modified = not is_initial
        
        # Create the assignment
        cur.execute(f"""
            INSERT INTO {table_name} (task_id, {id_column}, is_initial, is_modified)
            VALUES (%s, %s, %s, %s)
            RETURNING assignment_id
        """, (task_id, entity_id, is_initial, is_modified))
        
        result = cur.fetchone()
        assignment_id = result['assignment_id']
        
        conn.commit()
        cur.close()
        conn.close()
        
        response_data = {
            "success": True,
            "message": f"{assignment_type.capitalize()} assignment created successfully",
            "assignment_id": assignment_id
        }
        
        # Add warning and conflicts if they exist
        if warning_message:
            response_data["warning"] = warning_message
            response_data["conflicts"] = conflicts
            response_data["conflict_count"] = len(conflicts)
        
        return jsonify(response_data)
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500



@app.route('/api/tasks/requirements', methods=['GET', 'POST'])
def task_requirements():
    """Get or set task requirements"""
    if request.method == 'GET':
        return get_task_requirements()
    else:
        return set_task_requirements()

def get_task_requirements():
    """
    Get resource and employee requirements for a task or all tasks
    
    Query parameters:
    - task_id: Optional. If provided, returns requirements for this task only
    """
    try:
        task_id = request.args.get('task_id')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if task_id:
            # Check if task exists
            cur.execute("SELECT task_id, task_name FROM tasks WHERE task_id = %s", (task_id,))
            task = cur.fetchone()
            
            if not task:
                return jsonify({"error": f"Task with ID {task_id} not found"}), 404
            
            # Get employee requirements
            cur.execute("""
                SELECT resource_group, resource_count
                FROM task_required_employees
                WHERE task_id = %s
            """, (task_id,))
            employee_requirements = cur.fetchall()
            
            # Get resource requirements
            cur.execute("""
                SELECT resource_category, resource_count
                FROM task_required_resources
                WHERE task_id = %s
            """, (task_id,))
            resource_requirements = cur.fetchall()
            
            result = {
                "task_id": task['task_id'],
                "task_name": task['task_name'],
                "required_employees": employee_requirements,
                "required_resources": resource_requirements
            }
            
            return jsonify(result)
        else:
            # Get all tasks with their requirements
            cur.execute("SELECT task_id, task_name FROM tasks ORDER BY task_id")
            tasks = cur.fetchall()
            
            results = []
            for task in tasks:
                task_id = task['task_id']
                
                # Get employee requirements
                cur.execute("""
                    SELECT resource_group, resource_count
                    FROM task_required_employees
                    WHERE task_id = %s
                """, (task_id,))
                employee_requirements = cur.fetchall()
                
                # Get resource requirements
                cur.execute("""
                    SELECT resource_category, resource_count
                    FROM task_required_resources
                    WHERE task_id = %s
                """, (task_id,))
                resource_requirements = cur.fetchall()
                
                task_result = {
                    "task_id": task_id,
                    "task_name": task['task_name'],
                    "required_employees": employee_requirements,
                    "required_resources": resource_requirements
                }
                
                results.append(task_result)
            
            return jsonify(results)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def set_task_requirements():
    """
    Set resource and employee requirements for a task
    
    JSON body:
    {
        "task_id": 123,
        "required_employees": [
            {"resource_group": "management", "resource_count": 1},
            {"resource_group": "technical", "resource_count": 2}
        ],
        "required_resources": [
            {"resource_category": "vehicle", "resource_count": 1},
            {"resource_category": "equipment", "resource_count": 1}
        ]
    }
    """
    try:
        data = request.json
        
        if not data or 'task_id' not in data:
            return jsonify({"error": "Missing required field: task_id"}), 400
        
        task_id = data['task_id']
        required_employees = data.get('required_employees', [])
        required_resources = data.get('required_resources', [])
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if task exists
        cur.execute("SELECT task_id FROM tasks WHERE task_id = %s", (task_id,))
        if not cur.fetchone():
            return jsonify({"error": f"Task with ID {task_id} not found"}), 404
        
        # Clear existing requirements
        cur.execute("DELETE FROM task_required_employees WHERE task_id = %s", (task_id,))
        cur.execute("DELETE FROM task_required_resources WHERE task_id = %s", (task_id,))
        
        # Insert required employees if any
        for emp in required_employees:
            resource_group = emp.get('resource_group')
            resource_count = emp.get('resource_count', 1)
            
            if resource_group:
                cur.execute("""
                    INSERT INTO task_required_employees (task_id, resource_group, resource_count)
                    VALUES (%s, %s, %s)
                """, (task_id, resource_group, resource_count))
        
        # Insert required resources if any
        for res in required_resources:
            resource_category = res.get('resource_category')
            resource_count = res.get('resource_count', 1)
            
            if resource_category:
                cur.execute("""
                    INSERT INTO task_required_resources (task_id, resource_category, resource_count)
                    VALUES (%s, %s, %s)
                """, (task_id, resource_category, resource_count))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True, 
            "message": f"Requirements set for task {task_id}",
            "employee_requirements": len(required_employees),
            "resource_requirements": len(required_resources)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/assignments/auto-assign', methods=['POST'])
def auto_assign_resources():
    """
    Automatically assign resources and employees to tasks
    
    Optional JSON body:
    {
        "task_id": 123  // If provided, only assign to this task
    }
    """
    try:
        data = request.json or {}
        task_id = data.get('task_id')
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
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
            conn.commit()
        
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
            conn.commit()
        
        # Get tasks to assign resources to
        if task_id:
            cur.execute("""
                SELECT t.task_id, t.task_name
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                WHERE t.task_id = %s
            """, (task_id,))
        else:
            cur.execute("""
                SELECT t.task_id, t.task_name
                FROM tasks t
                JOIN schedules s ON t.task_id = s.task_id
                WHERE s.status = 'Scheduled'
            """)
        
        tasks = cur.fetchall()
        
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
            # Create the employees table
            cur.execute("""
                CREATE TABLE employees (
                    employee_id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    role_name VARCHAR(100),
                    skill_set VARCHAR(100),
                    availability BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Insert sample employees
            cur.execute("""
                INSERT INTO employees (name, role_name, skill_set, availability)
                VALUES 
                ('John Smith', 'Project Manager', 'management', TRUE),
                ('Jane Doe', 'Engineer', 'engineering', TRUE),
                ('Bob Johnson', 'Technician', 'technical', TRUE),
                ('Alice Brown', 'Designer', 'design', TRUE)
            """)
            conn.commit()
        
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
            # Create the resources table
            cur.execute("""
                CREATE TABLE resources (
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
            """)
            conn.commit()
        
        # Get all employees and resources
        cur.execute("SELECT employee_id, name, role_name FROM employees")
        employees = cur.fetchall()
        
        cur.execute("SELECT resource_id, name, type FROM resources")
        resources = cur.fetchall()
        
        # For each task, assign resources and employees
        assigned_tasks = []
        
        for task in tasks:
            task_id = task['task_id']
            task_name = task['task_name']
            
            # Check if this task already has assignments
            cur.execute("SELECT COUNT(*) FROM employee_assignments WHERE task_id = %s", (task_id,))
            employee_count = cur.fetchone()['count']
            
            # Only assign if no assignments exist
            if employee_count == 0 and employees:
                # For simplicity, just assign the first employee
                employee = employees[0]
                employee_id = employee['employee_id']
                
                cur.execute("""
                    INSERT INTO employee_assignments (task_id, employee_id, is_initial, is_modified)
                    VALUES (%s, %s, TRUE, FALSE)
                    ON CONFLICT (task_id, employee_id) DO NOTHING
                """, (task_id, employee_id))
                
                assigned_tasks.append({
                    'task_id': task_id,
                    'task_name': task_name,
                    'employee_id': employee_id,
                    'employee_name': employee['name']
                })
            
            # Check if this task already has resource assignments
            cur.execute("SELECT COUNT(*) FROM resource_assignments WHERE task_id = %s", (task_id,))
            resource_count = cur.fetchone()['count']
            
            # Only assign if no assignments exist
            if resource_count == 0 and resources:
                # For simplicity, just assign the first resource
                resource = resources[0]
                resource_id = resource['resource_id']
                
                cur.execute("""
                    INSERT INTO resource_assignments (task_id, resource_id, is_initial, is_modified)
                    VALUES (%s, %s, TRUE, FALSE)
                    ON CONFLICT (task_id, resource_id) DO NOTHING
                """, (task_id, resource_id))
                
                assigned_tasks.append({
                    'task_id': task_id,
                    'task_name': task_name,
                    'resource_id': resource_id,
                    'resource_name': resource['name']
                })
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Assigned resources to {len(assigned_tasks)} tasks',
            'assigned_tasks': assigned_tasks
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

@app.route('/api/assignments/reschedule', methods=['POST'])
def reschedule_after_assignment_change():
    """
    Trigger a reschedule after assignments have been changed
    
    Required JSON body:
    {
        "task_id": 123,
        "full_reschedule": false  # Optional, if true will reschedule all incomplete tasks
    }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "Missing request data"}), 400
        
        # Check if this is a full reschedule request
        full_reschedule = data.get('full_reschedule', False)
        
        if full_reschedule:
            # Use the CP-SAT scheduler to reschedule all incomplete tasks
            return run_partial_reschedule()
        
        # If not a full reschedule, we need a task_id
        if 'task_id' not in data:
            return jsonify({"error": "Missing task_id"}), 400
            
        task_id = data['task_id']
        
        # Get the current schedule for the task
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get task details
        cur.execute("""
            SELECT t.task_id, t.task_name, t.estimated_hours, t.priority, t.phase,
                   s.planned_start, s.planned_end, s.status
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cur.fetchone()
        
        if not task:
            return jsonify({"error": f"Task with ID {task_id} not found"}), 404
        
        # Find the next available time slot
        # This is a simplified approach - in a real system, you'd use a more sophisticated algorithm
        cur.execute("""
            SELECT s.planned_end
            FROM schedules s
            WHERE s.status NOT IN ('Completed', 'Skipped')
            ORDER BY s.planned_end DESC
            LIMIT 1
        """)
        
        latest_end = cur.fetchone()
        new_start = latest_end['planned_end'] if latest_end else datetime.now()
        
        # Add a small buffer (15 minutes)
        new_start = new_start + timedelta(minutes=15)
        
        # Calculate new end time based on task duration
        duration_hours = task['estimated_hours'] or 1  # Default to 1 hour if null
        new_end = new_start + timedelta(hours=float(duration_hours))
        
        # Update the schedule
        cur.execute("""
            UPDATE schedules
            SET planned_start = %s, planned_end = %s
            WHERE task_id = %s
        """, (new_start, new_end, task_id))
        
        # Log the change
        cur.execute("""
            INSERT INTO schedule_changes 
            (task_id, change_type, old_start, old_end, new_start, new_end, reason)
            VALUES (%s, 'manual_reschedule', %s, %s, %s, %s, %s)
        """, (
            task_id, 
            task['planned_start'], 
            task['planned_end'], 
            new_start, 
            new_end, 
            'Rescheduled due to resource conflict'
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "message": f"Task {task_id} has been rescheduled",
            "task_name": task['task_name'],
            "old_start": task['planned_start'].isoformat(),
            "old_end": task['planned_end'].isoformat(),
            "new_start": new_start.isoformat(),
            "new_end": new_end.isoformat()
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

def run_partial_reschedule():
    """
    Run the CP-SAT scheduler but only for incomplete and unstarted tasks.
    Preserves tasks that are already completed or in progress.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Get all tasks that are completed or in progress - these will be preserved
        cur.execute("""
            SELECT t.task_id, t.task_name, s.status, s.planned_start, s.planned_end, 
                   s.actual_start, s.actual_end
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE s.status IN ('Completed', 'In Progress', 'Clocked In')
        """)
        
        preserved_tasks = cur.fetchall()
        preserved_task_ids = [t['task_id'] for t in preserved_tasks]
        
        print(f"Preserving {len(preserved_tasks)} tasks that are completed or in progress")
        
        # 2. Get all tasks that need to be rescheduled
        cur.execute("""
            SELECT t.task_id, t.task_name, t.estimated_hours, t.priority, t.phase, t.preemptable,
                   s.status, s.planned_start, s.planned_end
            FROM tasks t
            JOIN schedules s ON t.task_id = s.task_id
            WHERE s.status NOT IN ('Completed', 'In Progress', 'Clocked In')
        """)
        
        tasks_to_reschedule = cur.fetchall()
        
        print(f"Rescheduling {len(tasks_to_reschedule)} incomplete tasks")
        
        if not tasks_to_reschedule:
            return jsonify({
                "success": True,
                "message": "No tasks to reschedule",
                "preserved_tasks": len(preserved_tasks),
                "rescheduled_tasks": 0
            })
        
        # 3. Call the CP-SAT scheduler with a flag to only reschedule specific tasks
        try:
            # Import the scheduler function
            from initial_scheduler import cp_sat_scheduler
            
            # Run the scheduler with the list of tasks to preserve
            cp_sat_scheduler(preserve_task_ids=preserved_task_ids)
            
            # Get the updated schedule
            cur.execute("""
                SELECT s.task_id, t.task_name, s.planned_start, s.planned_end, 
                       s.status, t.priority, t.phase
                FROM schedules s
                JOIN tasks t ON s.task_id = t.task_id
                ORDER BY s.planned_start
            """)
            
            updated_schedules = cur.fetchall()
            
            # Convert datetime objects to ISO format strings
            for schedule in updated_schedules:
                schedule['start_iso'] = schedule['planned_start'].isoformat() if schedule['planned_start'] else None
                schedule['end_iso'] = schedule['planned_end'].isoformat() if schedule['planned_end'] else None
            
            return jsonify({
                "success": True,
                "message": f"Successfully rescheduled {len(tasks_to_reschedule)} tasks",
                "preserved_tasks": len(preserved_tasks),
                "rescheduled_tasks": len(tasks_to_reschedule),
                "schedules": updated_schedules
            })
            
        except Exception as scheduler_error:
            print(f"Error in CP-SAT scheduler: {scheduler_error}")
            import traceback
            traceback.print_exc()
            
            # Fall back to a simpler approach if the CP-SAT scheduler fails
            print("Falling back to simple sequential rescheduling")
            
            # Clear existing schedules for tasks that need to be rescheduled
            task_ids_to_reschedule = [t['task_id'] for t in tasks_to_reschedule]
            task_ids_str = ','.join(str(tid) for tid in task_ids_to_reschedule)
            
            if task_ids_str:
                # Get the latest end time from preserved tasks
                if preserved_tasks:
                    latest_preserved_end = max(t['planned_end'] for t in preserved_tasks if t['planned_end'])
                    start_date = latest_preserved_end + timedelta(hours=1)
                else:
                    start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
                
                # Sort tasks by priority (higher priority first)
                tasks_to_reschedule.sort(key=lambda x: x['priority'] or 0, reverse=True)
                
                # Create a simple sequential schedule
                for task in tasks_to_reschedule:
                    task_id = task['task_id']
                    duration = task['estimated_hours'] or 1  # Default to 1 hour if null
                    
                    # Calculate end date (assuming 8-hour workdays)
                    days_needed = int(duration) // 8
                    hours_remaining = int(duration) % 8
                    
                    end_date = start_date + timedelta(days=days_needed)
                    if hours_remaining > 0:
                        end_date = end_date + timedelta(hours=hours_remaining)
                    
                    # Update the schedule
                    cur.execute("""
                        UPDATE schedules
                        SET planned_start = %s, planned_end = %s
                        WHERE task_id = %s
                    """, (start_date, end_date, task_id))
                    
                    # Move start date to next task (add a day to ensure separation)
                    start_date = end_date + timedelta(hours=1)
                    if start_date.hour >= 17:  # After 5 PM
                        # Move to next day 9 AM
                        start_date = (start_date + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
                
                conn.commit()
            
            # Get the updated schedule
            cur.execute("""
                SELECT s.task_id, t.task_name, s.planned_start, s.planned_end, 
                       s.status, t.priority, t.phase
                FROM schedules s
                JOIN tasks t ON s.task_id = t.task_id
                ORDER BY s.planned_start
            """)
            
            updated_schedules = cur.fetchall()
            
            # Convert datetime objects to ISO format strings
            for schedule in updated_schedules:
                schedule['start_iso'] = schedule['planned_start'].isoformat() if schedule['planned_start'] else None
                schedule['end_iso'] = schedule['planned_end'].isoformat() if schedule['planned_end'] else None
            
            return jsonify({
                "success": True,
                "message": f"Successfully rescheduled {len(tasks_to_reschedule)} tasks using fallback method",
                "preserved_tasks": len(preserved_tasks),
                "rescheduled_tasks": len(tasks_to_reschedule),
                "schedules": updated_schedules,
                "warning": "Used fallback scheduling method due to CP-SAT scheduler error"
            })
    
    except Exception as e:
        print(f"Error in run_partial_reschedule: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/assignments/delete', methods=['POST'])
def delete_assignment():
    """
    Delete an employee or resource assignment
    
    Required JSON body:
    {
        "type": "employee|resource",
        "assignment_id": 123  # Optional if task_id and entity_id are provided
        
        # Alternative identification (for conflict resolution)
        "task_id": 456,  # Optional if assignment_id is provided
        "employee_id": 789,  # Optional, used with task_id for employee assignments
        "resource_id": 789   # Optional, used with task_id for resource assignments
    }
    """
    try:
        data = request.json
        
        if not data or 'type' not in data:
            return jsonify({"error": "Missing required field: type"}), 400
        
        assignment_type = data['type']
        
        # Determine the table name and ID column based on assignment type
        if assignment_type == 'employee':
            table_name = 'employee_assignments'
            entity_id_column = 'employee_id'
        else:  # resource
            table_name = 'resource_assignments'
            entity_id_column = 'resource_id'
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if the table exists
        cur.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table_name}'
            ) as exists
        """)
        
        result = cur.fetchone()
        table_exists = result['exists'] if result else False
        
        if not table_exists:
            return jsonify({"error": f"No {assignment_type} assignments exist"}), 404
        
        # Determine how to identify the assignment to delete
        if 'assignment_id' in data and data['assignment_id'] is not None:
            # Delete by assignment_id
            assignment_id = data['assignment_id']
            
            # Check if the assignment exists
            cur.execute(f"""
                SELECT * FROM {table_name}
                WHERE assignment_id = %s
            """, (assignment_id,))
            
            existing = cur.fetchone()
            
            if not existing:
                return jsonify({"error": f"{assignment_type.capitalize()} assignment with ID {assignment_id} not found"}), 404
            
            # Delete the assignment
            cur.execute(f"""
                DELETE FROM {table_name}
                WHERE assignment_id = %s
            """, (assignment_id,))
        
        elif 'task_id' in data and entity_id_column in data:
            # Delete by task_id and entity_id
            task_id = data['task_id']
            entity_id = data[entity_id_column]
            
            # Check if the assignment exists
            cur.execute(f"""
                SELECT * FROM {table_name}
                WHERE task_id = %s AND {entity_id_column} = %s
            """, (task_id, entity_id))
            
            existing = cur.fetchone()
            
            if not existing:
                return jsonify({"error": f"No {assignment_type} assignment found for task {task_id} and {entity_id_column} {entity_id}"}), 404
            
            # Delete the assignment
            cur.execute(f"""
                DELETE FROM {table_name}
                WHERE task_id = %s AND {entity_id_column} = %s
            """, (task_id, entity_id))
        
        else:
            return jsonify({"error": "Missing required fields. Either assignment_id or both task_id and entity_id are required"}), 400
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "message": f"{assignment_type.capitalize()} assignment deleted successfully"
        })
    
    except Exception as e:
        return jsonify({"error": str(e), "traceback": str(sys.exc_info())}), 500

# Helper function to check for resource conflicts
def check_resource_conflicts(conn, task_id, resource_id=None, employee_id=None):
    """
    Check if assigning a resource or employee to a task would create a conflict
    
    Args:
        conn: Database connection
        task_id: The task ID to check
        resource_id: Optional resource ID to check for conflicts
        employee_id: Optional employee ID to check for conflicts
        
    Returns:
        List of conflicts found
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conflicts = []
    
    try:
        # Get the task's planned start and end times
        cur.execute("""
            SELECT planned_start, planned_end
            FROM schedules
            WHERE task_id = %s
        """, (task_id,))
        
        task_schedule = cur.fetchone()
        if not task_schedule:
            return []  # Task not found or not scheduled
            
        task_start = task_schedule['planned_start']
        task_end = task_schedule['planned_end']
        
        # Check for employee conflicts if employee_id is provided
        if employee_id:
            cur.execute("""
                SELECT s.task_id, t.task_name, s.planned_start, s.planned_end
                FROM schedules s
                JOIN tasks t ON s.task_id = t.task_id
                JOIN employee_assignments ea ON s.task_id = ea.task_id
                WHERE 
                    ea.employee_id = %s AND
                    s.task_id != %s AND
                    s.status NOT IN ('Completed', 'Skipped') AND
                    s.planned_start < %s AND
                    s.planned_end > %s
            """, (employee_id, task_id, task_end, task_start))
            
            employee_conflicts = cur.fetchall()
            conflicts.extend([{
                'type': 'employee',
                'entity_id': employee_id,
                'task_id': conflict['task_id'],
                'task_name': conflict['task_name'],
                'start_time': conflict['planned_start'],
                'end_time': conflict['planned_end']
            } for conflict in employee_conflicts])
        
        # Check for resource conflicts if resource_id is provided
        if resource_id:
            cur.execute("""
                SELECT s.task_id, t.task_name, s.planned_start, s.planned_end
                FROM schedules s
                JOIN tasks t ON s.task_id = t.task_id
                JOIN resource_assignments ra ON s.task_id = ra.task_id
                WHERE 
                    ra.resource_id = %s AND
                    s.task_id != %s AND
                    s.status NOT IN ('Completed', 'Skipped') AND
                    s.planned_start < %s AND
                    s.planned_end > %s
            """, (resource_id, task_id, task_end, task_start))
            
            resource_conflicts = cur.fetchall()
            conflicts.extend([{
                'type': 'resource',
                'entity_id': resource_id,
                'task_id': conflict['task_id'],
                'task_name': conflict['task_name'],
                'start_time': conflict['planned_start'],
                'end_time': conflict['planned_end']
            } for conflict in resource_conflicts])
            
        return conflicts
    finally:
        cur.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)