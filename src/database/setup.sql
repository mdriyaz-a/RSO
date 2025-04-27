CREATE DATABASE RSO;

\c RSO;

-- Create sequences for all tables
CREATE SEQUENCE tenants_tenant_id_seq;
CREATE SEQUENCE roles_role_id_seq;
CREATE SEQUENCE projects_project_id_seq;
CREATE SEQUENCE employees_employee_id_seq;
CREATE SEQUENCE resources_resource_id_seq;
CREATE SEQUENCE tasks_task_id_seq;
CREATE SEQUENCE dependencies_dependency_id_seq;
CREATE SEQUENCE complex_dependencies_complex_dep_id_seq;
CREATE SEQUENCE dependency_types_type_id_seq;
CREATE SEQUENCE schedules_schedule_id_seq;
CREATE SEQUENCE employee_assignments_assignment_id_seq;
CREATE SEQUENCE resource_assignments_assignment_id_seq;
CREATE SEQUENCE task_progress_progress_id_seq;
CREATE SEQUENCE task_segments_segment_id_seq;
CREATE SEQUENCE task_required_employees_id_seq;
CREATE SEQUENCE task_required_resources_id_seq;
CREATE SEQUENCE task_pause_log_pause_id_seq;
CREATE SEQUENCE task_skip_log_skip_id_seq;
CREATE SEQUENCE crew_pause_log_pause_id_seq;
CREATE SEQUENCE working_hours_working_hours_id_seq;
CREATE SEQUENCE holidays_holiday_id_seq;
CREATE SEQUENCE weather_data_weather_id_seq;
CREATE SEQUENCE schedule_changes_change_id_seq;
CREATE SEQUENCE schedule_change_log_change_id_seq;
CREATE SEQUENCE notifications_notification_id_seq;
CREATE SEQUENCE optimization_history_optimization_id_seq;
CREATE SEQUENCE user_preferences_preference_id_seq;

-- Create base tables first

-- Tenants table
CREATE TABLE tenants (
    tenant_id INTEGER NOT NULL DEFAULT nextval('tenants_tenant_id_seq'::regclass),
    tenant_name CHARACTER VARYING(255) NOT NULL,
    contact_email CHARACTER VARYING(255),
    contact_phone CHARACTER VARYING(50),
    address TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT true,
    PRIMARY KEY (tenant_id)
);

-- Roles table
CREATE TABLE roles (
    role_id INTEGER NOT NULL DEFAULT nextval('roles_role_id_seq'::regclass),
    role_name CHARACTER VARYING(50) NOT NULL,
    description TEXT,
    PRIMARY KEY (role_id)
);

-- Projects table
CREATE TABLE projects (
    project_id INTEGER NOT NULL DEFAULT nextval('projects_project_id_seq'::regclass),
    tenant_id INTEGER NOT NULL,
    project_name CHARACTER VARYING(255) NOT NULL,
    description TEXT,
    start_date DATE,
    target_end_date DATE,
    actual_end_date DATE,
    status CHARACTER VARYING(50) DEFAULT 'Planning'::character varying,
    location JSON,
    weather_api_location CHARACTER VARYING(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id),
    CONSTRAINT projects_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

-- Employees table
CREATE TABLE employees (
    employee_id INTEGER NOT NULL DEFAULT nextval('employees_employee_id_seq'::regclass),
    name CHARACTER VARYING(255) NOT NULL,
    role_id INTEGER NOT NULL,
    contact CHARACTER VARYING(255),
    skill_set CHARACTER VARYING(255),
availability BOOLEAN DEFAULT TRUE,
    tenant_id INTEGER,
    PRIMARY KEY (employee_id),
    CONSTRAINT employees_role_id_fkey FOREIGN KEY (role_id) REFERENCES roles(role_id),
    CONSTRAINT fk_employee_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

-- Resources table
CREATE TABLE resources (
    resource_id INTEGER NOT NULL DEFAULT nextval('resources_resource_id_seq'::regclass),
    name CHARACTER VARYING(255) NOT NULL,
    type CHARACTER VARYING(50),
    availability BOOLEAN,
    last_maintenance DATE,
    details JSON,
    tenant_id INTEGER,
    PRIMARY KEY (resource_id),
    CONSTRAINT fk_resource_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

-- Tasks table
CREATE TABLE tasks (
    task_id INTEGER NOT NULL DEFAULT nextval('tasks_task_id_seq'::regclass),
    project_id INTEGER NOT NULL,
    wbs CHARACTER VARYING(50),
    task_name TEXT NOT NULL,
    estimated_days NUMERIC,
    estimated_hours NUMERIC,
    task_type CHARACTER VARYING(50),
    phase CHARACTER VARYING(50),
    additional_data JSON,
    priority INTEGER,
    dependency_expression TEXT,
    priority_weight INTEGER DEFAULT 50,
    preemptable BOOLEAN DEFAULT false,
    tenant_id INTEGER,
    PRIMARY KEY (task_id),
    CONSTRAINT fk_project FOREIGN KEY (project_id) REFERENCES projects(project_id),
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

-- Dependency types table
CREATE TABLE dependency_types (
    type_id INTEGER NOT NULL DEFAULT nextval('dependency_types_type_id_seq'::regclass),
    type_code CHARACTER VARYING(10) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (type_id)
);

-- Dependencies table
CREATE TABLE dependencies (
    dependency_id INTEGER NOT NULL DEFAULT nextval('dependencies_dependency_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    depends_on_task_id INTEGER NOT NULL,
    lag_hours NUMERIC(10,2),
    dependency_type CHARACTER VARYING(10) DEFAULT 'FS'::character varying,
    PRIMARY KEY (dependency_id),
    CONSTRAINT dependencies_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    CONSTRAINT dependencies_depends_on_task_id_fkey FOREIGN KEY (depends_on_task_id) REFERENCES tasks(task_id)
);

-- Complex dependencies table
CREATE TABLE complex_dependencies (
    complex_dep_id INTEGER NOT NULL DEFAULT nextval('complex_dependencies_complex_dep_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    depends_on_task_id INTEGER NOT NULL,
    dependency_type CHARACTER VARYING(10) NOT NULL,
    lag_hours INTEGER DEFAULT 0,
    lag_expression TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (complex_dep_id),
    CONSTRAINT complex_dependencies_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    CONSTRAINT complex_dependencies_depends_on_task_id_fkey FOREIGN KEY (depends_on_task_id) REFERENCES tasks(task_id)
);

-- Schedules table
CREATE TABLE schedules (
    schedule_id INTEGER NOT NULL DEFAULT nextval('schedules_schedule_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    planned_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    planned_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    actual_start TIMESTAMP WITHOUT TIME ZONE,
    actual_end TIMESTAMP WITHOUT TIME ZONE,
    status CHARACTER VARYING(50) DEFAULT 'Scheduled'::character varying,
    remarks TEXT,
    PRIMARY KEY (schedule_id),
    CONSTRAINT schedules_task_id_key UNIQUE (task_id),
    CONSTRAINT schedules_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Employee assignments table
CREATE TABLE employee_assignments (
    assignment_id INTEGER NOT NULL DEFAULT nextval('employee_assignments_assignment_id_seq'::regclass),
    employee_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    assigned_date TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_date TIMESTAMP WITHOUT TIME ZONE,
    end_date TIMESTAMP WITHOUT TIME ZONE,
    status CHARACTER VARYING(50) DEFAULT 'Assigned'::character varying,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_initial BOOLEAN DEFAULT false,
    is_modified BOOLEAN DEFAULT false,
    PRIMARY KEY (assignment_id),
    CONSTRAINT employee_assignments_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    CONSTRAINT employee_assignments_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Resource assignments table
CREATE TABLE resource_assignments (
    assignment_id INTEGER NOT NULL DEFAULT nextval('resource_assignments_assignment_id_seq'::regclass),
    resource_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    assigned_date TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    start_date TIMESTAMP WITHOUT TIME ZONE,
    end_date TIMESTAMP WITHOUT TIME ZONE,
    status CHARACTER VARYING(50) DEFAULT 'Assigned'::character varying,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_initial BOOLEAN DEFAULT false,
    is_modified BOOLEAN DEFAULT false,
    PRIMARY KEY (assignment_id),
    CONSTRAINT resource_assignments_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES resources(resource_id),
    CONSTRAINT resource_assignments_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Correct task_progress table
CREATE TABLE task_progress (
    progress_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(50) NOT NULL,
accumulated_minutes INTEGER DEFAULT 0,
    notes TEXT,
    duration_minutes NUMERIC DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_percentage NUMERIC(5,2) DEFAULT 0,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Correct task_segments table
CREATE TABLE task_segments (
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


-- Task required employees table
CREATE TABLE task_required_employees (
    id INTEGER NOT NULL DEFAULT nextval('task_required_employees_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    resource_type CHARACTER VARYING(50),
    resource_group CHARACTER VARYING(50),
    resource_count INTEGER,
    PRIMARY KEY (id),
    CONSTRAINT task_required_employees_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Task required resources table
CREATE TABLE task_required_resources (
    id INTEGER NOT NULL DEFAULT nextval('task_required_resources_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    resource_type CHARACTER VARYING(50) NOT NULL,
    resource_category CHARACTER VARYING(50) NOT NULL,
    resource_count INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT task_required_resources_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Task pause log table
CREATE TABLE task_pause_log (
    pause_id INTEGER NOT NULL DEFAULT nextval('task_pause_log_pause_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    start_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    end_time TIMESTAMP WITHOUT TIME ZONE,
    reason TEXT,
    duration_minutes NUMERIC(10,2),
    is_on_hold BOOLEAN DEFAULT false,
    expected_resume_time TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pause_id),
    CONSTRAINT task_pause_log_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Task skip log table
CREATE TABLE task_skip_log (
    skip_id INTEGER NOT NULL DEFAULT nextval('task_skip_log_skip_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    skip_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    reason TEXT,
    PRIMARY KEY (skip_id),
    CONSTRAINT task_skip_log_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Crew pause log table
CREATE TABLE crew_pause_log (
    pause_id INTEGER NOT NULL DEFAULT nextval('crew_pause_log_pause_id_seq'::regclass),
    project_id INTEGER NOT NULL,
    pause_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    pause_end TIMESTAMP WITHOUT TIME ZONE,
    pause_type CHARACTER VARYING(50) NOT NULL,
    reason TEXT,
    affected_employees JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pause_id),
    CONSTRAINT crew_pause_log_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Working hours table
CREATE TABLE working_hours (
    working_hours_id INTEGER NOT NULL DEFAULT nextval('working_hours_working_hours_id_seq'::regclass),
    tenant_id INTEGER NOT NULL,
    project_id INTEGER,
    day_of_week INTEGER NOT NULL,
    start_time TIME WITHOUT TIME ZONE NOT NULL,
    end_time TIME WITHOUT TIME ZONE NOT NULL,
    is_working_day BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (working_hours_id),
    CONSTRAINT working_hours_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    CONSTRAINT working_hours_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Holidays table
CREATE TABLE holidays (
    holiday_id INTEGER NOT NULL DEFAULT nextval('holidays_holiday_id_seq'::regclass),
    tenant_id INTEGER NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_name CHARACTER VARYING(100) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (holiday_id),
    CONSTRAINT holidays_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

-- Weather data table
CREATE TABLE weather_data (
    weather_id INTEGER NOT NULL DEFAULT nextval('weather_data_weather_id_seq'::regclass),
    project_id INTEGER NOT NULL,
    forecast_date DATE NOT NULL,
    weather_condition CHARACTER VARYING(50),
    temperature_high NUMERIC,
    temperature_low NUMERIC,
    precipitation_chance NUMERIC,
    wind_speed NUMERIC,
    weather_data JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (weather_id),
    CONSTRAINT weather_data_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

-- Schedule changes table
CREATE TABLE schedule_changes (
    change_id INTEGER NOT NULL DEFAULT nextval('schedule_changes_change_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    change_type CHARACTER VARYING(50) NOT NULL,
    old_start TIMESTAMP WITHOUT TIME ZONE,
    old_end TIMESTAMP WITHOUT TIME ZONE,
    new_start TIMESTAMP WITHOUT TIME ZONE,
    new_end TIMESTAMP WITHOUT TIME ZONE,
    reason TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (change_id),
    CONSTRAINT schedule_changes_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Schedule change log table
CREATE TABLE schedule_change_log (
    change_id INTEGER NOT NULL DEFAULT nextval('schedule_change_log_change_id_seq'::regclass),
    task_id INTEGER NOT NULL,
    previous_start TIMESTAMP WITHOUT TIME ZONE,
    previous_end TIMESTAMP WITHOUT TIME ZONE,
    new_start TIMESTAMP WITHOUT TIME ZONE,
    new_end TIMESTAMP WITHOUT TIME ZONE,
    change_type CHARACTER VARYING(50) NOT NULL,
    reason TEXT,
    changed_by INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (change_id),
    CONSTRAINT schedule_change_log_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    CONSTRAINT schedule_change_log_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES employees(employee_id)
);

-- Notifications table
CREATE TABLE notifications (
    notification_id INTEGER NOT NULL DEFAULT nextval('notifications_notification_id_seq'::regclass),
    tenant_id INTEGER NOT NULL,
    project_id INTEGER,
    task_id INTEGER,
    notification_type CHARACTER VARYING(50) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (notification_id),
    CONSTRAINT notifications_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    CONSTRAINT notifications_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(project_id),
    CONSTRAINT notifications_task_id_fkey FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- Optimization history table
CREATE TABLE optimization_history (
    optimization_id INTEGER NOT NULL DEFAULT nextval('optimization_history_optimization_id_seq'::regclass),
    tenant_id INTEGER NOT NULL,
    project_id INTEGER,
    optimization_type CHARACTER VARYING(50) NOT NULL,
    triggered_by INTEGER,
    start_time TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    end_time TIMESTAMP WITHOUT TIME ZONE,
    status CHARACTER VARYING(50) DEFAULT 'Running'::character varying,
    affected_tasks JSON,
    optimization_params JSON,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (optimization_id),
    CONSTRAINT optimization_history_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    CONSTRAINT optimization_history_project_id_fkey FOREIGN KEY (project_id) REFERENCES projects(project_id),
    CONSTRAINT optimization_history_triggered_by_fkey FOREIGN KEY (triggered_by) REFERENCES employees(employee_id)
);

-- User preferences table
CREATE TABLE user_preferences (
    preference_id INTEGER NOT NULL DEFAULT nextval('user_preferences_preference_id_seq'::regclass),
    employee_id INTEGER NOT NULL,
    preference_key CHARACTER VARYING(50) NOT NULL,
    preference_value TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (preference_id),
    CONSTRAINT user_preferences_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);


INSERT INTO tenants (tenant_id, tenant_name, contact_email, contact_phone, address)
VALUES 
(1, 'Greenhouse Construction Co.', 'info@greenhouse.com', '555-123-4567', '123 Main St, Anytown, USA');


INSERT INTO roles (role_id, role_name, description)
VALUES 
(1, 'Admin', 'Oversees operations, no field work'),
(2, 'Sales', 'Handles customer interactions and estimates'),
(3, 'Purchase Officer', 'Manages finances and procurement'),
(4, 'Foreman', 'Manages field work and construction crew'),
(5, 'labour', 'Performs construction tasks');


INSERT INTO employees (employee_id, tenant_id, name, role_id, contact, skill_set)
VALUES 
(1, 1, 'Alice Johnson', 1, 'alice@greenhouse.com', 'Admin'),
(2, 1, 'Bob Smith', 2, 'bob@greenhouse.com', 'Sales'),
(6, 1, 'Riyaz', 5, 'riyaz@greenhouse.com', 'labour'),
(4, 1, 'David Kim', 4, 'david@greenhouse.com', 'Foreman'),
(7, 1, 'Mohamed', 5, 'mohamed@greenhouse.com', 'labour'),
(3, 1, 'Carol Lee', 3, 'carol@greenhouse.com', 'PurchaseOfficer');


INSERT INTO projects (project_id,tenant_id,  project_name, description, start_date,status)
VALUES
(1, 1, 'Greenhouse Construction', 'Construction of a new greenhouse facility', '2025-04-01', 'In Progress');



INSERT INTO tasks (task_id, project_id, wbs, task_name, estimated_days, estimated_hours, task_type, phase, additional_data, priority, preemptable, tenant_id)
VALUES 
(1, 1, '1.1', 'sales', 1.35, 33.08, 'nan', 'sales', NULL, 2, false, 1),
(2, 1, '1.1.1', 'Collect customer info and information necessary to create a quote', 0.005, 0.12, 'Manual Task', 'sales', NULL, 2, false, 1),
(3, 1, '1.1.2', 'Create account for Customer in GMS', 0.002, 0.07, 'Manual Task', 'sales', NULL, 3, false, 1),
(4, 1, '1.1.3', 'Enter customer''s information in hubspot & assign to salesperson', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(5, 1, '1.1.4', 'Enter into Hubspot deals, stage: Contacted', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(6, 1, '1.1.5', 'Send welcome/thank you email', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(7, 1, '1.1.6', 'Meet Customer to create estimate/quote', 0.041, 1.0, 'Manual Task', 'sales', NULL, 1, false, 1),
(8, 1, '1.1.7', 'Create BOM for Materials', 0.02, 0.5, 'Create BOM Task', 'sales', NULL, 2, false, 1),
(9, 1, '1.1.8', 'Create & Submit Estimate for Customer', 0.01, 0.25, 'Create Estimate Task', 'sales', NULL, 1, false, 1),
(10, 1, '1.1.9', 'Approve and Send Contract(Implicit send contract email)', 0.005, 0.12, 'Approve Contract Task', 'sales', NULL, 1, false, 1),
(11, 1, '1.1.10', 'Create Digital file (to store images, invoices, quotes, etc (file naming should file this format)', 0.005, 0.12, 'Manual Task', 'sales', NULL, 3, false, 1),
(12, 1, '1.1.11', 'Enter into Hubspot deals, stage: Quote Sent', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(13, 1, '1.1.12', 'Set a follow up in Hubspot for every 7-10 days', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(14, 1, '1.1.13', 'If project requires engineering: Get payment for engineering (upload deposit reciept to GMS)', 0.005, 0.12, 'Manual Task', 'sales', NULL, 3, false, 1),
(15, 1, '1.1.14', 'If project requires engineering: Submit to engineering', 0.005, 0.12, 'Manual Task', 'sales', NULL, 3, false, 1),
(16, 1, '1.1.15', 'Customer quote accepted. Request BC to create a layout (drawings, not concrete) - If customer rejected,  change hubspot status to Lost.', 0.002, 0.06, 'Manual Task', 'sales', NULL, 2, false, 1),
(17, 1, '1.1.16', 'When layout is recieved from BC,  schedule a meeting (can be virtual) with customer to review', 0.002, 0.06, 'Manual Task', 'sales', NULL, 2, false, 1),
(18, 1, '1.1.17', 'Enter into Hubspot deals, stage: Quote Revised', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(19, 1, '1.1.18', 'Follow up with customer to learn about their timeline (also to get permission to send contract)', 0.005, 0.12, 'Manual Task', 'sales', NULL, 2, false, 1),
(20, 1, '1.1.19', 'Send Final order confirmation: 1) Final Order 2) Terms & Conditions 3) Watertight 4) Layout 5) Expectations 6) DELIVERY REQUIREMENTS-tentative date, to site, to shop?', 0.004, 0.1, 'Manual Task', 'sales', NULL, 1, false, 1),
(21, 1, '1.1.20', 'Customer Signs a contract', 0.004, 0.1, 'Customer Task', 'sales', NULL, 1, false, 1),
(22, 1, '1.1.21', 'Remind Customer to sign contract', 0.002, 0.06, 'Remainder Customer Task', 'sales', NULL, 1, false, 1),
(23, 1, '1.1.22', 'Generate Invoice for customer #1', 0.002, 0.06, 'Create Invoice Task', 'sales', NULL, 1, false, 1),
(24, 1, '1.1.23', 'Approve and Send Invoice to Customer #1', 0.004, 0.1, 'Approve Invoice Task', 'sales', NULL, 1, false, 1),
(25, 1, '1.1.24', 'customer pays invoice #1', 1.0, 24.0, 'Payment Task', 'sales', NULL, 1, false, 1),
(26, 1, '1.1.25', 'Remind Customer to Pay the invoice #1', 0.0, 0.083, 'Remainder Invoice Task', 'sales', NULL, 1, false, 1),
(27, 1, '1.1.26', 'Enter into Hubspot deals, stage: Terms & Conditions', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(28, 1, '1.1.27', '(if cash or check) Payment Verification & Uploading Receipt against Payment invoice #1', 0.02, 0.5, 'Payment Verification Task', 'sales', NULL, 2, false, 1),
(29, 1, '1.1.28', 'Enter into Hubspot deals, stage: Winner Circle', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(30, 1, '1.1.29', 'Move Prospect''s digital folder to: Unshipped', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(31, 1, '1.1.30', 'Adds project to Excel Tab: Invoice Summary', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(32, 1, '1.1.31', 'Adds project to Excel Tab: Scheduled', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(33, 1, '1.1.32', 'Adds project to Jordan''s Excel Document', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(34, 1, '1.1.33', 'Generate PO for material Vendor', 0.002, 0.06, 'Create PO Task', 'sales', NULL, 1, false, 1),
(35, 1, '1.1.34', 'Approve and Send PO to material Vendor (implicit email send po to vendor) with delivery requirements (this prompts order for foundation drawings request <2w turn time)', 0.02, 0.5, 'Approve PO Task', 'sales', NULL, 1, false, 1),
(36, 1, '1.1.35', 'Discuss with Customer to determine a suitable Material Delivery date', 0.002, 0.06, 'Manual Task', 'sales', NULL, 2, false, 1),
(37, 1, '1.1.36', 'receive confirmation or Remind material Vendor to Process PO', 0.002, 0.06, 'Confirm PO Task', 'sales', NULL, 2, false, 1),
(38, 1, '1.1.37', 'Sales team checks Vendor''s email to get material delivery date and enters the date in WGC''s Excel Sheet', 0.002, 0.06, 'Manual Task', 'sales', NULL, 2, false, 1),
(39, 1, '1.1.38', 'Notes from Vendor is reviewed and addressed.', 0.02, 0.5, 'Manual Task', 'sales', NULL, 2, false, 1),
(40, 1, '1.1.39', 'If other accessories required, order from the different distributors', 0.02, 0.5, 'Manual Task', 'sales', NULL, 3, false, 1),
(41, 1, '1.1.40', 'Set a reminder in HubSpot to email follow up to BC for foundation drawings in 7 days. Reoccuring email every 2 days here after.', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(42, 1, '1.1.41', 'Once foundation recieved, email customer & concrete contractor templated email from hubspot requesting approx install/completion time/date (takes 3w-6m, usually <2m)', 0.005, 0.12, 'Manual Task', 'sales', NULL, 2, false, 1),
(43, 1, '1.1.42', 'If electrical required, confirm customer connects the electrical contractor with the concrete contractor prior to foundation work begining', 0.005, 0.12, 'Manual Task', 'sales', NULL, 3, false, 1),
(44, 1, '1.1.43', 'If not recieved in 10 days - send reoccuring email reminder/follow-up to customer/concrete contractor seeking approx install/completion date', 0.002, 0.06, 'Manual Task', 'sales', NULL, 3, false, 1),
(45, 1, '1.1.44', 'Once foundation completed, email customer instructions for photos and verification the foundation is the right size by asking customer to measure certain dimensions.', 0.002, 0.06, 'Manual Task', 'sales', NULL, 2, false, 1),
(46, 1, '1.1.45', 'Once email recieved from customer verifying concrete work is completed, IF wrong dimensions, figure out how to make it work through discussions with either or both, the concrete contractor and BC.', 0.041, 1.0, 'Manual Task', 'sales', NULL, 1, false, 1),
(47, 1, '1.1.46', 'Once email recieved from customer verifying concrete work is completed, IF correct dimensions, in excel document in the scheduling tab change cust color to green', 0.041, 1.0, 'Manual Task', 'sales', NULL, 2, false, 1),
(48, 1, '1.1.47', 'Once confirmation recieved materials are completed and avaiable for pick up from BC, get qty, weights, and sizes of packages, and determine if shipping direct to site or to shop', 0.005, 0.12, 'Manual Task', 'sales', NULL, 2, false, 1),
(49, 1, '1.1.48', 'if other accessories ordered, confirm reciept and location', 0.02, 0.5, 'Manual Task', 'sales', NULL, 3, false, 1),
(50, 1, '1.2', 'Pre-Construction', 2.15, 2.98, 'nan', 'preConstruction', NULL, 2, false, 1),
(51, 1, '1.2.1', 'Schedule delivery through trucking company: ABF / ROEHL / Carson / Freight Quote', 0.07, 1.74, 'Manual Task', 'preConstruction', NULL, 1, false, 1),
(52, 1, '1.2.2', 'Remind customer One Week before material delivery to make sure they are ready to receive it.', 0.005, 0.12, 'Manual Task', 'preConstruction', NULL, 2, false, 1),
(53, 1, '1.2.3', 'Create Project in Slack, and upload: Customer address, phone number, gate code, drawings, pack list, contact for concrete contractor, electrical contractor, GC if applicable.', 0.02, 0.5, 'Manual Task', 'preConstruction', NULL, 2, false, 1),
(54, 1, '1.2.4', 'Move in to google Calendar (when, who is installing, turcks needs, materials/parts located where?)', 0.02, 0.5, 'Manual Task', 'preConstruction', NULL, 2, false, 1),
(55, 1, '1.2.5', 'Call Customer to confirm dates work', 0.005, 0.12, 'Manual Task', 'preConstruction', NULL, 1, false, 1),
(56, 1, '1.2.6', 'If dates don''t work, update google calendar & call customers impacted of updated plan', 0.01, 0.25, 'Manual Task', 'preConstruction', NULL, 2, false, 1),
(57, 1, '1.2.7', 'Email and/or text employees what they''re doing', 0.01, 0.25, 'Manual Task', 'preConstruction', NULL, 2, false, 1),
(58, 1, '1.3', 'activeConstruction', 2.02, 49.48, 'nan', 'activeConstruction', NULL, 1, false, 1),
(59, 1, '1.3.1', 'Identify if a lift will be needed & order', 0.005, 0.12, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(60, 1, '1.3.2', 'Restock truck with any neccessary caluk, blads, drill sets, trashbags, and tools', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(61, 1, '1.3.3', 'if anything is needed from shop, load truck before departure (check box in WGC shop)', 0.005, 0.12, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(62, 1, '1.3.4', 'If overnight required, Troy records 3/4 of the day for per diem for all crew members', 0.005, 0.12, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(63, 1, '1.3.5', 'Drive to site (call and notify customer prior to departure)', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(64, 1, '1.3.6', 'Drive to site', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(65, 1, '1.3.7', 'Arrive to site and introduce ourselves', 0.005, 0.12, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(66, 1, '1.3.8', 'Recieve & Stage Materials', 0.02, 0.5, 'Receive PO Task', 'activeConstruction', NULL, 1, false, 1),
(67, 1, '1.3.9', 'Verify Materials from Vendor - Verify packing list with materials. Packing list available from Slack.', 0.02, 0.5, 'Verify PO Task', 'activeConstruction', NULL, 1, false, 1),
(68, 1, '1.3.10', 'Measure and check foundation for faults and Issues', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 1, false, 1),
(69, 1, '1.3.11', 'Check layouts/prints and looks at the Slack file for specific instructions if any', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(70, 1, '1.3.12', 'Assemble nuts and bolts togther', 0.041, 1.0, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(71, 1, '1.3.13', 'Square the foundation', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 1, false, 1),
(72, 1, '1.3.14', 'Tape Bars', 0.041, 1.0, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(73, 1, '1.3.15', 'Load and set ladders and scaffolding where required from Truck', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(74, 1, '1.3.16', 'Install base perimiter on foundation', 0.062, 1.5, 'Install Task', 'activeConstruction', NULL, 1, false, 1),
(75, 1, '1.3.17', 'Verify installation of base perimiter on foundation', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 1, false, 1),
(76, 1, '1.3.18', 'Frame Greenhouse', 0.33, 8.0, 'Install Task', 'activeConstruction', NULL, 1, false, 1),
(77, 1, '1.3.19', 'Verify installation of Greenhouse Frame', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 1, false, 1),
(78, 1, '1.3.20', 'Install the roof system', 0.166, 4.0, 'Install Task', 'activeConstruction', NULL, 1, false, 1),
(79, 1, '1.3.21', 'Verify installation of roof system', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 1, false, 1),
(80, 1, '1.3.22', 'Install the windows/glazing', 0.33, 8.0, 'Install Task', 'activeConstruction', NULL, 1, false, 1),
(81, 1, '1.3.23', 'Verify installation of windows/glazing', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 1, false, 1),
(82, 1, '1.3.24', 'Install Doors', 0.166, 4.0, 'Install Task', 'activeConstruction', NULL, 1, false, 1),
(83, 1, '1.3.25', 'Verify installation of doors', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 1, false, 1),
(84, 1, '1.3.26', 'if applicable, Install roof vents', 0.08, 2.0, 'Install Task', 'activeConstruction', NULL, 2, false, 1),
(85, 1, '1.3.27', 'Verify installation of roof vents', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 2, false, 1),
(86, 1, '1.3.28', 'if applicable, Install side vents', 0.08, 2.0, 'Install Task', 'activeConstruction', NULL, 2, false, 1),
(87, 1, '1.3.29', 'Verify installation of side vents', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 2, false, 1),
(88, 1, '1.3.30', 'if applicable, install other mechanical', 0.166, 4.0, 'Install Task', 'activeConstruction', NULL, 2, false, 1),
(89, 1, '1.3.31', 'Verify installation of mechanical', 0.02, 0.5, 'Verify Task', 'activeConstruction', NULL, 2, false, 1),
(90, 1, '1.3.32', 'Take trash to dumpster/truck', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(91, 1, '1.3.33', 'Take pictures (should be from the same place as the before pictures were taken)', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(92, 1, '1.3.34', 'Upload Completed Project photos into Slack', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(93, 1, '1.3.35', 'If there are parts left over, take pictures and upload to slack', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(94, 1, '1.3.36', 'If there are parts left over, send the pictures and instructions to electrician or to whom ever necessary', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(95, 1, '1.3.37', 'if electrical required, let electrical contractor know they can begin connecting the mechanicals', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(96, 1, '1.3.38', 'if there is a punchlist, create list of whats needed, and upload with instructions into slack', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(97, 1, '1.3.39', 'if there is a punchlist and parts are needed, purchase', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 2, false, 1),
(98, 1, '1.3.40', 'Communicate with customer work completed, show them how to operat the electronics, vents, etc. (if unavaiable, call and leave a message that the work has been completed and thank them)', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 1, false, 1),
(99, 1, '1.3.41', 'Load tools and items into truck and head back to WGC', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(100, 1, '1.3.42', 'Drive back', 0.02, 0.5, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(101, 1, '1.3.43', 'Drop off truck & trailer (if applicable)', 0.041, 1.0, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(102, 1, '1.3.44', 'If trash broght back, empty', 0.01, 0.25, 'Manual Task', 'activeConstruction', NULL, 3, false, 1),
(103, 1, '1.4', 'postConstruction', 0.054, 1.3, 'nan', 'postConstruction', NULL, 2, false, 1),
(104, 1, '1.4.1', 'If overnight required, upon return Troy records 3/4 of the day for per diem for all crew members', 0.01, 0.25, 'Manual Task', 'postConstruction', NULL, 3, false, 1),
(105, 1, '1.4.2', 'Email instructions for green house to customer', 0.005, 0.12, 'Manual Task', 'postConstruction', NULL, 2, false, 1),
(106, 1, '1.4.3', 'In hubspot, change customer stage/status to: Winners Circle', 0.005, 0.12, 'Manual Task', 'postConstruction', NULL, 3, false, 1),
(107, 1, '1.4.4', 'Send Thank you card', 0.02, 0.5, 'Thank You Card Task', 'postConstruction', NULL, 3, false, 1),
(108, 1, '1.4.5', 'Salesperson calls customer to make sure that they are satisfied with the job.', 0.01, 0.25, 'Manual Task', 'postConstruction', NULL, 2, false, 1),
(109, 1, '1.4.6', '10 days later email customer to confirm satisfaction, and request pictures of the space being used', 0.002, 0.06, 'Manual Task', 'postConstruction', NULL, 3, false, 1);



INSERT INTO dependencies (dependency_id, task_id, depends_on_task_id, lag_hours, dependency_type) VALUES
(1, 3, 2, NULL, 'FS'),
(2, 4, 3, NULL, 'FS'),
(3, 5, 4, NULL, 'FS'),
(4, 6, 5, 24, 'FS'),
(5, 7, 3, NULL, 'FS'),
(6, 8, 7, NULL, 'FS'),
(7, 9, 8, NULL, 'FS'),
(8, 10, 9, NULL, 'FS'),
(9, 11, 3, NULL, 'FS'),
(10, 12, 10, NULL, 'FS'),
(11, 13, 10, NULL, 'FS'),
(12, 14, 10, NULL, 'FS'),
(13, 15, 11, NULL, 'FS'),
(14, 16, 10, NULL, 'FS'),
(15, 17, 16, 48, 'FS'),
(16, 18, 17, NULL, 'FS'),
(17, 19, 17, NULL, 'FS'),
(18, 20, 19, NULL, 'FS'),
(19, 21, 20, 48, 'FS'),
(20, 22, 21, 48, 'FS'),
(21, 23, 21, NULL, 'FS'),
(22, 24, 21, NULL, 'FS'),
(23, 25, 24, NULL, 'FS'),
(24, 26, 24, 48, 'FS'),
(25, 27, 25, NULL, 'FS'),
(26, 28, 25, NULL, 'FS'),
(27, 29, 25, NULL, 'FS'),
(28, 30, 25, NULL, 'FS'),
(29, 31, 25, NULL, 'FS'),
(30, 32, 25, NULL, 'FS'),
(31, 33, 25, NULL, 'FS'),
(32, 34, 25, NULL, 'FS'),
(33, 35, 34, NULL, 'FS'),
(34, 36, 25, NULL, 'FS'),
(35, 37, 35, 24, 'FS'),
(36, 39, 37, NULL, 'FS'),
(37, 40, 34, NULL, 'FS'),
(38, 41, 34, NULL, 'FS'),
(39, 42, 34, NULL, 'FS'),
(40, 43, 42, NULL, 'FS'),
(41, 44, 43, NULL, 'FS'),
(42, 45, 44, 120, 'FS'),
(43, 46, 45, NULL, 'FS'),
(44, 47, 45, NULL, 'FS'),
(45, 48, 35, NULL, 'FS'),
(46, 49, 40, NULL, 'FS'),
(47, 52, 51, NULL, 'FS'),
(48, 53, 51, NULL, 'FS'),
(49, 54, 53, NULL, 'FS'),
(50, 55, 54, NULL, 'FS'),
(51, 56, 55, NULL, 'FS'),
(52, 57, 55, NULL, 'FS'),
(53, 60, 59, NULL, 'FS'),
(54, 61, 60, NULL, 'FS'),
(55, 62, 61, NULL, 'FS'),
(56, 63, 59, NULL, 'FS'),
(57, 64, 63, NULL, 'FS'),
(58, 65, 64, NULL, 'FS'),
(59, 66, 65, NULL, 'FS'),
(60, 67, 65, NULL, 'FS'),
(61, 68, 65, NULL, 'FS'),
(62, 69, 67, NULL, 'FS'),
(63, 70, 66, NULL, 'FS'),
(64, 71, 69, NULL, 'FS'),
(65, 72, 68, NULL, 'FS'),
(66, 73, 70, NULL, 'FS'),
(67, 74, 73, NULL, 'FS'),
(68, 75, 74, NULL, 'FS'),
(69, 76, 75, NULL, 'FS'),
(70, 77, 76, NULL, 'FS'),
(71, 78, 77, NULL, 'FS'),
(72, 79, 78, NULL, 'FS'),
(73, 80, 79, NULL, 'FS'),
(74, 81, 80, NULL, 'FS'),
(75, 82, 81, NULL, 'FS'),
(76, 83, 82, NULL, 'FS'),
(77, 84, 81, NULL, 'FS'),
(78, 85, 84, NULL, 'FS'),
(79, 86, 83, NULL, 'FS'),
(80, 87, 86, NULL, 'FS'),
(81, 88, 85, NULL, 'FS'),
(82, 89, 88, NULL, 'FS'),
(83, 90, 77, NULL, 'FS'),
(84, 91, 77, NULL, 'FS'),
(85, 92, 91, NULL, 'FS'),
(86, 93, 92, NULL, 'FS'),
(87, 94, 93, NULL, 'FS'),
(88, 95, 94, NULL, 'FS'),
(89, 96, 95, NULL, 'FS'),
(90, 97, 96, NULL, 'FS'),
(91, 98, 96, NULL, 'FS'),
(92, 99, 77, NULL, 'FS'),
(93, 100, 99, NULL, 'FS'),
(94, 101, 100, NULL, 'FS'),
(95, 102, 100, NULL, 'FS'),
(96, 104, 100, NULL, 'FS'),
(97, 105, 98, NULL, 'FS'),
(98, 106, 105, NULL, 'FS'),
(99, 107, 106, NULL, 'FS'),
(100, 108, 107, NULL, 'FS'),
(101, 109, 108, NULL, 'FS');

INSERT INTO resources (resource_id, name, type, availability, last_maintenance, details) VALUES
(1, 'Truck', 'Truck', true, '2025-03-05', '{"description": "Heavy-duty truck for transporting materials"}'),
(2, 'Ladder', 'Ladder', true, '2025-02-20', '{"description": "Folding ladder for reaching high areas"}'),
(3, 'Scaffolding', 'Scaffolding', true, '2025-02-10', '{"description": "Scaffolding system for construction sites"}'),
(4, 'Dumpster', 'Dumpster', true, '2025-03-03', '{"description": "Large dumpster for debris removal"}'),
(5, 'Truck 2', 'Truck', false, '2025-03-05', '{"description": "Additional heavy-duty truck for transporting materials"}'),
(6, 'Truck 3', 'Truck', false, '2025-03-05', '{"description": "Additional heavy-duty truck for transporting materials"}'),
(7, 'Truck 4', 'Truck', false, '2025-03-05', '{"description": "Additional heavy-duty truck for transporting materials"}');

INSERT INTO task_required_employees (id, task_id, resource_type, resource_group, resource_count) VALUES
(1, 2, 'W2', 'sales', 1),
(2, 3, 'W2', 'sales', 1),
(3, 4, 'W2', 'sales', 1),
(4, 5, 'W2', 'sales', 1),
(5, 6, 'W2', 'sales', 1),
(6, 7, 'W2', 'sales', 1),
(7, 8, 'W2', 'sales', 1),
(8, 9, 'W2', 'sales', 1),
(9, 10, 'W2', 'sales', 1),
(10, 11, 'W2', 'sales', 1),
(11, 12, 'W2', 'sales', 1),
(12, 13, 'W2', 'sales', 1),
(13, 14, 'W2', 'sales', 1),
(14, 15, 'W2', 'sales', 1),
(15, 16, 'W2', 'sales', 1),
(16, 17, 'W2', 'sales', 1),
(17, 18, 'W2', 'sales', 1),
(18, 19, 'W2', 'sales', 1),
(19, 20, 'W2', 'sales', 1),
(20, 24, 'W2', 'purchaseOfficer', 1),
(21, 27, 'W2', 'sales', 1),
(22, 28, 'W2', 'sales', 1),
(23, 29, 'W2', 'admin', 1),
(24, 30, 'W2', 'sales', 1),
(25, 31, 'W2', 'admin', 1),
(26, 32, 'W2', 'sales', 1),
(27, 33, 'W2', 'sales', 1),
(28, 35, 'W2', 'purchaseOfficer', 1),
(29, 36, 'W2', 'sales', 1),
(30, 37, 'W2', 'purchaseOfficer', 1),
(31, 38, 'W2', 'sales', 1),
(32, 39, 'W2', 'sales', 1),
(33, 40, 'W2', 'sales', 1),
(34, 41, 'W2', 'sales', 1),
(35, 42, 'W2', 'sales', 1),
(36, 43, 'W2', 'sales', 1),
(37, 44, 'W2', 'sales', 1),
(38, 45, 'W2', 'sales', 1),
(39, 46, 'W2', 'sales', 1),
(40, 47, 'W2', 'sales', 1),
(41, 48, 'W2', 'sales', 1),
(42, 49, 'W2', 'sales', 1),
(43, 51, 'W2', 'admin', 1),
(44, 52, 'W2', 'admin', 1),
(45, 53, 'W2', 'sales', 1),
(46, 54, 'W2', 'admin', 1),
(47, 55, 'W2', 'sales', 1),
(48, 56, 'W2', 'admin', 1),
(49, 57, 'W2', 'sales', 1),
(50, 59, 'W2', 'foreman', 1),
(51, 60, 'W2', 'foreman', 1),
(52, 61, 'W2', 'foreman', 1),
(53, 62, 'W2', 'admin', 1),
(54, 63, 'W2', 'foreman', 1),
(55, 64, 'W2', 'labour', 2),
(56, 65, 'W2', 'foreman', 1),
(57, 65, 'W2', 'labour', 2),
(58, 66, 'W2', 'labour', 1),
(59, 67, 'W2', 'foreman', 1),
(60, 68, 'W2', 'labour', 1),
(61, 69, 'W2', 'foreman', 1),
(62, 70, 'W2', 'labour', 1),
(63, 71, 'W2', 'foreman', 1),
(64, 72, 'W2', 'labour', 1),
(65, 73, 'W2', 'labour', 1),
(66, 74, 'W2', 'labour', 2),
(67, 75, 'W2', 'foreman', 1),
(68, 76, 'W2', 'labour', 2),
(69, 77, 'W2', 'foreman', 1),
(70, 78, 'W2', 'labour', 2),
(71, 79, 'W2', 'foreman', 1),
(72, 80, 'W2', 'labour', 1),
(73, 81, 'W2', 'foreman', 1),
(74, 82, 'W2', 'labour', 1),
(75, 83, 'W2', 'foreman', 1),
(76, 84, 'W2', 'labour', 1),
(77, 85, 'W2', 'foreman', 1),
(78, 86, 'W2', 'labour', 1),
(79, 87, 'W2', 'foreman', 1),
(80, 88, 'W2', 'labour', 1),
(81, 89, 'W2', 'foreman', 1),
(82, 90, 'W2', 'labour', 1),
(83, 91, 'W2', 'foreman', 1),
(84, 92, 'W2', 'foreman', 1),
(85, 93, 'W2', 'foreman', 1),
(86, 94, 'W2', 'foreman', 1),
(87, 95, 'W2', 'foreman', 1),
(88, 96, 'W2', 'foreman', 1),
(89, 97, 'W2', 'sales', 1),
(90, 98, 'W2', 'foreman', 1),
(91, 99, 'W2', 'labour', 1),
(92, 100, 'W2', 'foreman', 1),
(93, 100, 'W2', 'labour', 2),
(94, 101, 'W2', 'foreman', 1),
(95, 102, 'W2', 'labour', 2),
(96, 104, 'W2', 'sales', 1),
(97, 105, 'W2', 'sales', 1),
(98, 106, 'W2', 'sales', 1),
(99, 107, 'W2', 'admin', 1),
(100, 108, 'W2', 'sales', 1),
(101, 109, 'W2', 'sales', 1);


INSERT INTO task_required_resources (id, task_id, resource_type, resource_category, resource_count)
VALUES 
(1, 51, 'Vehicle', 'Truck', 1),
(2, 60, 'Vehicle', 'Truck', 1),
(3, 63, 'Vehicle', 'Truck', 1),
(4, 64, 'Vehicle', 'Truck', 1),
(5, 99, 'Vehicle', 'Truck', 1),
(6, 100, 'Vehicle', 'Truck', 1),
(7, 101, 'Vehicle', 'Truck', 1),
(8, 102, 'Vehicle', 'Truck', 1),
(9, 73, 'Equipment', 'Ladder', 1),
(10, 73, 'Equipment', 'Scaffolding', 1),
(11, 102, 'Equipment', 'Dumpster', 1);