import React, { useState, useEffect, useRef } from 'react';
import { Button, Card, Form, OverlayTrigger, Tooltip } from 'react-bootstrap';
import axios from 'axios';
import './Calendar.css';

function Calendar() {
  const [schedules, setSchedules] = useState([]);
  const [resources, setResources] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [resourceAssignments, setResourceAssignments] = useState({
    employee_assignments: [],
    resource_assignments: [],
    employee_conflicts: [],
    resource_conflicts: []
  });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    type: 'none',
    id: ''
  });
  const [showConflicts, setShowConflicts] = useState(true);
  const [selectedTask, setSelectedTask] = useState(null);
  const [selectedTaskDetails, setSelectedTaskDetails] = useState({
    employeeAssignments: [],
    resourceAssignments: [],
    employeeConflicts: [],
    resourceConflicts: []
  });
  
  const calendarRef = useRef(null);
  const calendarInstance = useRef(null);

  // Initialize FullCalendar
  useEffect(() => {
    console.log('Initializing FullCalendar');
    
    const initializeCalendar = async () => {
      try {
        const { Calendar } = await import('@fullcalendar/core');
        const { default: dayGridPlugin } = await import('@fullcalendar/daygrid');
        const { default: timeGridPlugin } = await import('@fullcalendar/timegrid');
        const { default: interactionPlugin } = await import('@fullcalendar/interaction');
        
        if (calendarRef.current) {
          console.log('Calendar ref exists, creating calendar instance');
          
          // Destroy existing calendar if it exists
          if (calendarInstance.current) {
            console.log('Destroying existing calendar instance');
            calendarInstance.current.destroy();
          }
          
          calendarInstance.current = new Calendar(calendarRef.current, {
            plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
            initialView: 'timeGridWeek',
            headerToolbar: {
              left: 'prev,next today',
              center: 'title',
              right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            slotMinTime: '08:00:00',
            slotMaxTime: '20:00:00',
            height: 'auto',
            eventClick: handleEventClick
          });
          
          calendarInstance.current.render();
          console.log('Calendar rendered');
          
          // If we already have schedules, update the calendar
          if (schedules.length > 0) {
            updateCalendarEvents();
          }
        }
      } catch (error) {
        console.error('Error initializing calendar:', error);
      }
    };
    
    initializeCalendar();
    
    return () => {
      if (calendarInstance.current) {
        console.log('Cleaning up calendar instance');
        calendarInstance.current.destroy();
        calendarInstance.current = null;
      }
    };
  }, [schedules.length]);
  
  // Handle event click
  const handleEventClick = (info) => {
    try {
      // Get task details when a task is clicked
      const eventId = info.event.id;
      console.log('Event clicked with ID:', eventId);
      
      // Get the task ID from the event's extendedProps if available, otherwise parse the event ID
      const taskId = info.event.extendedProps?.taskId || parseInt(eventId);
      console.log('Task ID:', taskId);
      
      // Log all schedules for debugging
      console.log('All schedules:', schedules);
      console.log('All schedule IDs:', schedules.map(s => s.task_id));
      
      // Find the task in the schedules array - try both string and number comparison
      let task = schedules.find(t => t.task_id === taskId);
      
      // If not found, try string comparison
      if (!task) {
        task = schedules.find(t => String(t.task_id) === String(taskId));
      }
      
      console.log('Found task:', task);
      
      if (!task) {
        console.error('Task not found in schedules:', taskId);
        console.log('Available task IDs:', schedules.map(t => t.task_id));
        
        // Try to fetch the task directly from the server
        fetchTaskById(taskId);
        return;
      }
      
      // Log all resource assignments for debugging
      console.log('All employee assignments:', resourceAssignments.employee_assignments);
      console.log('All resource assignments:', resourceAssignments.resource_assignments);
      
      // Get resource assignments for this task
      const employeeAssignments = resourceAssignments.employee_assignments
        .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
      console.log('Employee assignments for task:', employeeAssignments);
        
      const resourceAssignmentsList = resourceAssignments.resource_assignments
        .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
      console.log('Resource assignments for task:', resourceAssignmentsList);
      
      // If no assignments found, try to refresh assignments data
      if (employeeAssignments.length === 0 && resourceAssignmentsList.length === 0) {
        console.log('No assignments found for task, refreshing assignments data...');
        
        // Fetch fresh assignments data
        axios.get('/api/assignments')
          .then(response => {
            console.log('Fresh assignments data:', response.data);
            setResourceAssignments(response.data);
            
            // Try again with fresh data
            const freshEmployeeAssignments = response.data.employee_assignments
              .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
            console.log('Fresh employee assignments for task:', freshEmployeeAssignments);
              
            const freshResourceAssignments = response.data.resource_assignments
              .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
            console.log('Fresh resource assignments for task:', freshResourceAssignments);
            
            // Update the selected task details with fresh data
            setSelectedTaskDetails({
              employeeAssignments: freshEmployeeAssignments,
              resourceAssignments: freshResourceAssignments,
              employeeConflicts: [],
              resourceConflicts: []
            });
          })
          .catch(error => {
            console.error('Error refreshing assignments:', error);
          });
      }
      
      // Get conflicts for this task
      const employeeConflicts = resourceAssignments.employee_conflicts
        .filter(c => 
          c.task1_id === taskId || String(c.task1_id) === String(taskId) || 
          c.task2_id === taskId || String(c.task2_id) === String(taskId)
        )
        .map(c => {
          // Add a property to indicate which task in the conflict is the selected one
          return {
            ...c,
            isTask1Selected: c.task1_id === taskId || String(c.task1_id) === String(taskId)
          };
        });
      console.log('Employee conflicts for task:', employeeConflicts);
      
      const resourceConflicts = resourceAssignments.resource_conflicts
        .filter(c => 
          c.task1_id === taskId || String(c.task1_id) === String(taskId) || 
          c.task2_id === taskId || String(c.task2_id) === String(taskId)
        )
        .map(c => {
          // Add a property to indicate which task in the conflict is the selected one
          return {
            ...c,
            isTask1Selected: c.task1_id === taskId || String(c.task1_id) === String(taskId)
          };
        });
      console.log('Resource conflicts for task:', resourceConflicts);
      
      // Set the selected task and its details
      setSelectedTask(task);
      setSelectedTaskDetails({
        employeeAssignments,
        resourceAssignments: resourceAssignmentsList,
        employeeConflicts,
        resourceConflicts
      });
      
      console.log('Selected task set:', task);
      console.log('Selected task details set:', {
        employeeAssignments,
        resourceAssignments: resourceAssignmentsList,
        employeeConflicts,
        resourceConflicts
      });
    } catch (error) {
      console.error('Error handling event click:', error);
      alert('An error occurred while getting task details. Please try again.');
    }
  };
  
  // Fetch a specific task by ID
  const fetchTaskById = async (taskId) => {
    try {
      console.log('Fetching task by ID:', taskId);
      setLoading(true);
      
      // Fetch the specific task
      const response = await axios.get(`/api/schedules/${taskId}`);
      console.log('Task fetch response:', response.data);
      
      if (response.data) {
        // Add the task to the schedules array if it's not already there
        const existingTaskIndex = schedules.findIndex(t => 
          t.task_id === taskId || String(t.task_id) === String(taskId)
        );
        
        let updatedSchedules = [...schedules];
        
        if (existingTaskIndex >= 0) {
          // Update the existing task
          updatedSchedules[existingTaskIndex] = response.data;
        } else {
          // Add the new task
          updatedSchedules.push(response.data);
        }
        
        // Update the schedules state
        setSchedules(updatedSchedules);
        
        // Now try to select the task again
        const task = response.data;
        
        // Fetch fresh assignments data to ensure we have the latest
        try {
          const assignmentsResponse = await axios.get('/api/assignments');
          console.log('Fresh assignments data:', assignmentsResponse.data);
          
          // Update the resource assignments state
          setResourceAssignments(assignmentsResponse.data);
          
          // Get resource assignments for this task from fresh data
          const employeeAssignments = assignmentsResponse.data.employee_assignments
            .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
          console.log('Fresh employee assignments for task:', employeeAssignments);
            
          const resourceAssignmentsList = assignmentsResponse.data.resource_assignments
            .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
          console.log('Fresh resource assignments for task:', resourceAssignmentsList);
          
          // Get conflicts for this task from fresh data
          const employeeConflicts = assignmentsResponse.data.employee_conflicts
            .filter(c => 
              c.task1_id === taskId || String(c.task1_id) === String(taskId) || 
              c.task2_id === taskId || String(c.task2_id) === String(taskId)
            )
            .map(c => ({
              ...c,
              isTask1Selected: c.task1_id === taskId || String(c.task1_id) === String(taskId)
            }));
          
          const resourceConflicts = assignmentsResponse.data.resource_conflicts
            .filter(c => 
              c.task1_id === taskId || String(c.task1_id) === String(taskId) || 
              c.task2_id === taskId || String(c.task2_id) === String(taskId)
            )
            .map(c => ({
              ...c,
              isTask1Selected: c.task1_id === taskId || String(c.task1_id) === String(taskId)
            }));
          
          // Set the selected task and its details
          setSelectedTask(task);
          setSelectedTaskDetails({
            employeeAssignments,
            resourceAssignments: resourceAssignmentsList,
            employeeConflicts,
            resourceConflicts
          });
        } catch (assignmentsError) {
          console.error('Error fetching assignments:', assignmentsError);
          
          // Fall back to using existing assignments data
          const employeeAssignments = resourceAssignments.employee_assignments
            .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
            
          const resourceAssignmentsList = resourceAssignments.resource_assignments
            .filter(a => a.task_id === taskId || String(a.task_id) === String(taskId));
          
          // Get conflicts for this task
          const employeeConflicts = resourceAssignments.employee_conflicts
            .filter(c => 
              c.task1_id === taskId || String(c.task1_id) === String(taskId) || 
              c.task2_id === taskId || String(c.task2_id) === String(taskId)
            )
            .map(c => ({
              ...c,
              isTask1Selected: c.task1_id === taskId || String(c.task1_id) === String(taskId)
            }));
          
          const resourceConflicts = resourceAssignments.resource_conflicts
            .filter(c => 
              c.task1_id === taskId || String(c.task1_id) === String(taskId) || 
              c.task2_id === taskId || String(c.task2_id) === String(taskId)
            )
            .map(c => ({
              ...c,
              isTask1Selected: c.task1_id === taskId || String(c.task1_id) === String(taskId)
            }));
          
          // Set the selected task and its details
          setSelectedTask(task);
          setSelectedTaskDetails({
            employeeAssignments,
            resourceAssignments: resourceAssignmentsList,
            employeeConflicts,
            resourceConflicts
          });
        }
      } else {
        alert(`Task with ID ${taskId} could not be found.`);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching task by ID:', error);
      alert(`Error fetching task with ID ${taskId}. Please try refreshing the page.`);
      setLoading(false);
    }
  };
  
  // Fetch data when component mounts
  useEffect(() => {
    console.log('Fetching initial data');
    fetchData();
  }, []);

  useEffect(() => {
    console.log('Data changed, updating calendar events');
    if (schedules.length > 0) {
      updateCalendarEvents();
    }
  }, [schedules, resourceAssignments, filter, showConflicts]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch schedules
      const schedulesResponse = await axios.get('/api/schedules');
      setSchedules(schedulesResponse.data);
      
      // Fetch resources
      const resourcesResponse = await axios.get('/api/resources');
      setResources(resourcesResponse.data);
      
      // Fetch employees
      const employeesResponse = await axios.get('/api/employees');
      setEmployees(employeesResponse.data);
      
      // Fetch resource assignments and conflicts
      const assignmentsResponse = await axios.get('/api/assignments');
      setResourceAssignments(assignmentsResponse.data);
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching data:', error);
      setLoading(false);
    }
  };

  const updateCalendarEvents = () => {
    console.log('Updating calendar events');
    
    if (!calendarInstance.current) {
      console.error('Calendar instance not available');
      return;
    }
    
    // Check if we have schedules
    if (!schedules || schedules.length === 0) {
      console.warn('No schedules available to display');
      return;
    }
    
    console.log('Available schedules:', schedules.length);
    console.log('Schedule task IDs:', schedules.map(s => s.task_id));
    
    // Clear existing events
    console.log('Removing all events');
    calendarInstance.current.removeAllEvents();
    
    // Filter schedules based on selected resource or employee
    let filteredSchedules = [...schedules];
    
    if (filter.type === 'resource' && filter.id) {
      // Filter by resource assignments
      const resourceId = parseInt(filter.id);
      console.log('Filtering by resource ID:', resourceId);
      
      // Log resource assignments for debugging
      console.log('Resource assignments:', resourceAssignments.resource_assignments);
      
      const taskIds = resourceAssignments.resource_assignments
        .filter(a => a.resource_id === resourceId)
        .map(a => a.task_id);
      
      console.log('Tasks assigned to resource:', taskIds);
      
      // If we don't have any assignments, fall back to the old method
      if (taskIds.length === 0) {
        console.log('No resource assignments found, using fallback filter');
        filteredSchedules = schedules.filter(task => 
          task.task_id % parseInt(filter.id) === 0
        );
      } else {
        filteredSchedules = schedules.filter(task => 
          taskIds.includes(task.task_id)
        );
      }
    } else if (filter.type === 'employee' && filter.id) {
      // Filter by employee assignments
      const employeeId = parseInt(filter.id);
      console.log('Filtering by employee ID:', employeeId);
      
      // Log employee assignments for debugging
      console.log('Employee assignments:', resourceAssignments.employee_assignments);
      
      const taskIds = resourceAssignments.employee_assignments
        .filter(a => a.employee_id === employeeId)
        .map(a => a.task_id);
      
      console.log('Tasks assigned to employee:', taskIds);
      
      // If we don't have any assignments, fall back to the old method
      if (taskIds.length === 0) {
        console.log('No employee assignments found, using fallback filter');
        filteredSchedules = schedules.filter(task => 
          task.task_id % parseInt(filter.id) === 0
        );
      } else {
        filteredSchedules = schedules.filter(task => 
          taskIds.includes(task.task_id)
        );
      }
    } else if (filter.type === 'phase' && filter.id) {
      // Filter by phase
      filteredSchedules = schedules.filter(task => 
        task.phase === filter.id
      );
    }
    
    console.log('Filtered schedules:', filteredSchedules.length);
    console.log('Filtered task IDs:', filteredSchedules.map(s => s.task_id));
    
    // Add events to calendar
    const events = filteredSchedules.map(task => {
      // Ensure task_id is a number
      const taskId = typeof task.task_id === 'string' ? parseInt(task.task_id) : task.task_id;
      
      // Determine color based on status and phase
      let statusColor;
      switch (task.status) {
        case 'Completed':
          statusColor = '#28a745'; // green
          break;
        case 'In Progress':
          statusColor = '#007bff'; // blue
          break;
        case 'Paused':
          statusColor = '#ffc107'; // yellow
          break;
        case 'On Hold':
          statusColor = '#dc3545'; // red
          break;
        case 'Skipped':
          statusColor = '#6c757d'; // gray
          break;
        default:
          statusColor = '#007bff'; // blue
      }
      
      // Check if this task has resource conflicts
      const hasEmployeeConflict = resourceAssignments.employee_conflicts.some(
        c => c.task1_id === taskId || c.task2_id === taskId
      );
      
      const hasResourceConflict = resourceAssignments.resource_conflicts.some(
        c => c.task1_id === taskId || c.task2_id === taskId
      );
      
      // Determine if we should show conflicts
      const hasConflict = (hasEmployeeConflict || hasResourceConflict) && showConflicts;
      
      // Set color based on conflict status if conflicts are enabled
      let color = statusColor;
      let textColor = 'white';
      let borderColor = null;
      
      if (hasConflict) {
        if (hasEmployeeConflict && hasResourceConflict) {
          // Both employee and resource conflicts
          color = '#9c27b0'; // purple
          borderColor = '#ff5722'; // orange border
        } else if (hasEmployeeConflict) {
          // Only employee conflict
          color = '#9c27b0'; // purple
        } else if (hasResourceConflict) {
          // Only resource conflict
          color = '#ff5722'; // orange
        }
      }
      
      // Create a title with conflict indicator if needed
      let title = `[${task.phase || 'No Phase'}] ${task.task_name}`;
      if (hasConflict) {
        title = `⚠️ ${title}`;
      }
      
      return {
        id: taskId.toString(), // Ensure ID is a string for FullCalendar
        title: title,
        start: task.planned_start_iso || task.planned_start,
        end: task.planned_end_iso || task.planned_end,
        color: color,
        textColor: textColor,
        borderColor: borderColor,
        extendedProps: {
          taskId: taskId, // Store the original task ID
          status: task.status,
          priority: task.priority,
          phase: task.phase,
          hasEmployeeConflict: hasEmployeeConflict,
          hasResourceConflict: hasResourceConflict
        }
      };
    });
    
    console.log('Adding events to calendar:', events.length);
    console.log('Event IDs:', events.map(e => e.id));
    
    // Add events to calendar
    calendarInstance.current.addEventSource(events);
    console.log('Events added to calendar');
  };

  const handleFilterChange = (e) => {
    const [type, id] = e.target.value.split(':');
    setFilter({ type, id });
  };

  // Get unique phases from schedules
  const getPhases = () => {
    return [...new Set(schedules.map(task => task.phase))].filter(Boolean);
  };
  
  // Format date for display
  const formatDate = (dateString) => {
    if (!dateString) return 'Not set';
    const date = new Date(dateString);
    return date.toLocaleString();
  };
  
  // Calculate duration between two dates
  const calculateDuration = (startIso, endIso) => {
    if (!startIso || !endIso) return 'Unknown';
    
    const start = new Date(startIso);
    const end = new Date(endIso);
    
    // Calculate difference in milliseconds
    const diffMs = end - start;
    
    // Convert to hours and minutes
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    
    if (diffHours === 0) {
      return `${diffMinutes} minutes`;
    } else if (diffMinutes === 0) {
      return `${diffHours} hours`;
    } else {
      return `${diffHours} hours, ${diffMinutes} minutes`;
    }
  };
  
  // Close the task details panel
  const closeTaskDetails = () => {
    setSelectedTask(null);
  };

  // Debug selected task state
  useEffect(() => {
    console.log('Selected task state changed:', selectedTask);
  }, [selectedTask]);

  return (
    <div className="dashboard-container">
      <div className="dashboard-controls">
        <div className="filter-controls">
          <div className="filter-group">
            <label className="filter-label">Filter By:</label>
            <Form.Select 
              className="filter-select" 
              onChange={handleFilterChange}
              value={`${filter.type}:${filter.id}`}
            >
              <option value="none:">All Tasks</option>
              
              <optgroup label="Phases">
                {getPhases().map(phase => (
                  <option key={`phase-${phase}`} value={`phase:${phase}`}>
                    Phase: {phase}
                  </option>
                ))}
              </optgroup>
              
              <optgroup label="Resources">
                {resources.map(resource => (
                  <option key={`resource-${resource.resource_id}`} value={`resource:${resource.resource_id}`}>
                    {resource.name} ({resource.type})
                  </option>
                ))}
              </optgroup>
              
              <optgroup label="Employees">
                {employees.map(employee => (
                  <option key={`employee-${employee.employee_id}`} value={`employee:${employee.employee_id}`}>
                    {employee.name} ({employee.role_name})
                  </option>
                ))}
              </optgroup>
            </Form.Select>
          </div>
          
          <div className="toggle-group">
            <Form.Check 
              type="switch"
              id="conflict-switch"
              label="Show Conflicts"
              checked={showConflicts}
              onChange={(e) => setShowConflicts(e.target.checked)}
            />
          </div>
          
          <Button 
            variant="primary" 
            className="refresh-button"
            onClick={fetchData}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                Loading...
              </>
            ) : (
              <>
                <i className="bi bi-arrow-clockwise me-1"></i>
                Refresh
              </>
            )}
          </Button>
        </div>
        
        <div className="legend-container">
          <div className="legend-item">
            <span className="legend-color bg-success"></span>
            <span className="legend-label">Completed</span>
          </div>
          <div className="legend-item">
            <span className="legend-color bg-primary"></span>
            <span className="legend-label">In Progress</span>
          </div>
          <div className="legend-item">
            <span className="legend-color bg-warning"></span>
            <span className="legend-label">Paused</span>
          </div>
          <div className="legend-item">
            <span className="legend-color bg-danger"></span>
            <span className="legend-label">On Hold</span>
          </div>
          <div className="legend-item">
            <span className="legend-color bg-secondary"></span>
            <span className="legend-label">Skipped</span>
          </div>
          
          {showConflicts && (
            <>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#9c27b0' }}></span>
                <span className="legend-label">Employee Conflict</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#ff5722' }}></span>
                <span className="legend-label">Resource Conflict</span>
              </div>
              <div className="legend-item">
                <span className="legend-color" style={{ backgroundColor: '#9c27b0', border: '2px solid #ff5722' }}></span>
                <span className="legend-label">Both Conflicts</span>
              </div>
            </>
          )}
        </div>
        
        <div className="filter-info">
          <small className="text-muted">
            {filter.type === 'none' ? 'Showing all tasks' : 
             filter.type === 'phase' ? `Filtered by Phase: ${filter.id}` :
             filter.type === 'resource' ? `Filtered by Resource: ${resources.find(r => r.resource_id === parseInt(filter.id))?.name || filter.id}` :
             `Filtered by Employee: ${employees.find(e => e.employee_id === parseInt(filter.id))?.name || filter.id}`}
          </small>
          
          {/* Show conflict statistics */}
          {showConflicts && (
            <small className="text-muted">
              <span className="me-2">
                <strong>Conflicts:</strong> {resourceAssignments.employee_conflicts.length + resourceAssignments.resource_conflicts.length} total
              </span>
              <span className="me-2">
                ({resourceAssignments.employee_conflicts.length} employee, {resourceAssignments.resource_conflicts.length} resource)
              </span>
            </small>
          )}
        </div>
      </div>
      
      <div className="dashboard-content">
        <div className={`calendar-container ${selectedTask ? 'with-sidebar' : ''}`}>
          <div className="calendar-wrapper">
            <div ref={calendarRef}></div>
          </div>
        </div>
        
        {/* Task Details Panel */}
        {selectedTask && (
          <div className="task-details-panel">
            <Card className="task-details-card">
              <div className="task-details-header">
                <div>
                  <h5 className="mb-0">Task Details</h5>
                  <div className="text-muted small">ID: {selectedTask.task_id}</div>
                </div>
                <Button 
                  variant="light" 
                  size="sm" 
                  className="rounded-circle" 
                  onClick={closeTaskDetails}
                  style={{ width: '32px', height: '32px', padding: '0' }}
                >
                  <i className="bi bi-x-lg"></i>
                </Button>
              </div>
              
              <Card.Body className="task-details-body">
                {/* Task Header */}
                <div className="task-details-section">
                  <div className="d-flex align-items-center mb-3">
                    <div className="me-auto">
                      <h4 className="mb-1">{selectedTask.task_name}</h4>
                      <div className="d-flex align-items-center">
                        <span className={`status-badge me-2 ${
                          selectedTask.status === 'Completed' ? 'bg-success' :
                          selectedTask.status === 'In Progress' ? 'bg-primary' :
                          selectedTask.status === 'Paused' ? 'bg-warning' :
                          selectedTask.status === 'On Hold' ? 'bg-danger' :
                          selectedTask.status === 'Skipped' ? 'bg-secondary' :
                          'bg-info'
                        }`}>
                          {selectedTask.status}
                        </span>
                        {selectedTask.phase && (
                          <span className="badge bg-light text-dark me-2">
                            Phase: {selectedTask.phase}
                          </span>
                        )}
                        {selectedTask.priority && (
                          <span className="badge bg-light text-dark">
                            Priority: {selectedTask.priority}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Schedule Information */}
                <div className="task-details-section">
                  <h6 className="task-details-section-title">
                    <i className="bi bi-calendar-check me-2"></i>Schedule
                  </h6>
                  
                  <div className="task-property">
                    <div className="task-property-label">Planned Start:</div>
                    <div className="task-property-value">{formatDate(selectedTask.planned_start_iso)}</div>
                  </div>
                  
                  <div className="task-property">
                    <div className="task-property-label">Planned End:</div>
                    <div className="task-property-value">{formatDate(selectedTask.planned_end_iso)}</div>
                  </div>
                  
                  {selectedTask.actual_start_iso && (
                    <div className="task-property">
                      <div className="task-property-label">Actual Start:</div>
                      <div className="task-property-value">{formatDate(selectedTask.actual_start_iso)}</div>
                    </div>
                  )}
                  
                  {selectedTask.actual_end_iso && (
                    <div className="task-property">
                      <div className="task-property-label">Actual End:</div>
                      <div className="task-property-value">{formatDate(selectedTask.actual_end_iso)}</div>
                    </div>
                  )}
                  
                  <div className="task-property">
                    <div className="task-property-label">Duration:</div>
                    <div className="task-property-value">
                      {calculateDuration(selectedTask.planned_start_iso, selectedTask.planned_end_iso)}
                    </div>
                  </div>
                </div>
                
                {/* Employee Assignments */}
                <div className="task-details-section">
                  <h6 className="task-details-section-title">
                    <i className="bi bi-people me-2"></i>Assigned Employees
                  </h6>
                  
                  {selectedTaskDetails.employeeAssignments.length > 0 ? (
                    <div className="list-group">
                      {selectedTaskDetails.employeeAssignments.map(assignment => {
                        const employee = employees.find(e => e.employee_id === assignment.employee_id);
                        return (
                          <div key={`emp-${assignment.employee_id}`} className="list-group-item list-group-item-action d-flex align-items-center border-0 px-0 py-2">
                            <div className="d-flex align-items-center">
                              <div className="rounded-circle bg-primary d-flex align-items-center justify-content-center text-white me-3" style={{ width: '40px', height: '40px' }}>
                                <i className="bi bi-person"></i>
                              </div>
                              <div>
                                <div className="fw-bold">{employee?.name || `Employee #${assignment.employee_id}`}</div>
                                <div className="text-muted small">{employee?.role_name || 'Unknown role'}</div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="alert alert-light border">
                      <i className="bi bi-info-circle me-2"></i>
                      No employees assigned to this task
                    </div>
                  )}
                </div>
                
                {/* Resource Assignments */}
                <div className="task-details-section">
                  <h6 className="task-details-section-title">
                    <i className="bi bi-tools me-2"></i>Assigned Resources
                  </h6>
                  
                  {selectedTaskDetails.resourceAssignments.length > 0 ? (
                    <div className="list-group">
                      {selectedTaskDetails.resourceAssignments.map(assignment => {
                        const resource = resources.find(r => r.resource_id === assignment.resource_id);
                        return (
                          <div key={`res-${assignment.resource_id}`} className="list-group-item list-group-item-action d-flex align-items-center border-0 px-0 py-2">
                            <div className="d-flex align-items-center">
                              <div className="rounded-circle bg-success d-flex align-items-center justify-content-center text-white me-3" style={{ width: '40px', height: '40px' }}>
                                <i className="bi bi-gear"></i>
                              </div>
                              <div>
                                <div className="fw-bold">{resource?.name || `Resource #${assignment.resource_id}`}</div>
                                <div className="text-muted small">{resource?.type || 'Unknown type'}</div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="alert alert-light border">
                      <i className="bi bi-info-circle me-2"></i>
                      No resources assigned to this task
                    </div>
                  )}
                </div>
                
                {/* Conflicts */}
                {(selectedTaskDetails.employeeConflicts.length > 0 || selectedTaskDetails.resourceConflicts.length > 0) && (
                  <div className="task-details-section">
                    <h6 className="task-details-section-title text-danger">
                      <i className="bi bi-exclamation-triangle-fill me-2"></i>
                      Resource Conflicts
                    </h6>
                    
                    {/* Employee Conflicts */}
                    {selectedTaskDetails.employeeConflicts.length > 0 && (
                      <div className="mb-3">
                        <h6 className="text-purple mb-2">
                          <i className="bi bi-person-fill me-1"></i>
                          Employee Conflicts
                        </h6>
                        
                        <div className="list-group">
                          {selectedTaskDetails.employeeConflicts.map((conflict, index) => {
                            const otherTaskId = conflict.isTask1Selected ? conflict.task2_id : conflict.task1_id;
                            const otherTask = schedules.find(t => t.task_id === otherTaskId);
                            const employee = employees.find(e => e.employee_id === conflict.employee_id);
                            
                            return (
                              <div key={`emp-conflict-${index}`} className="list-group-item border-0 rounded mb-2" style={{ backgroundColor: 'rgba(156, 39, 176, 0.1)' }}>
                                <div className="d-flex align-items-center mb-2">
                                  <div className="rounded-circle bg-purple d-flex align-items-center justify-content-center text-white me-2" style={{ width: '28px', height: '28px', backgroundColor: '#9c27b0' }}>
                                    <i className="bi bi-person-fill"></i>
                                  </div>
                                  <div className="fw-bold">{employee?.name || `Employee #${conflict.employee_id}`}</div>
                                </div>
                                
                                <div className="ps-4">
                                  <div className="text-muted mb-1">Also assigned to:</div>
                                  <div className="fw-bold">{otherTask?.task_name || `Task #${otherTaskId}`}</div>
                                  <div className="small">
                                    <i className="bi bi-clock me-1"></i>
                                    {formatDate(otherTask?.planned_start_iso)} - {formatDate(otherTask?.planned_end_iso)}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    
                    {/* Resource Conflicts */}
                    {selectedTaskDetails.resourceConflicts.length > 0 && (
                      <div>
                        <h6 className="text-orange mb-2">
                          <i className="bi bi-tools me-1"></i>
                          Resource Conflicts
                        </h6>
                        
                        <div className="list-group">
                          {selectedTaskDetails.resourceConflicts.map((conflict, index) => {
                            const otherTaskId = conflict.isTask1Selected ? conflict.task2_id : conflict.task1_id;
                            const otherTask = schedules.find(t => t.task_id === otherTaskId);
                            const resource = resources.find(r => r.resource_id === conflict.resource_id);
                            
                            return (
                              <div key={`res-conflict-${index}`} className="list-group-item border-0 rounded mb-2" style={{ backgroundColor: 'rgba(255, 87, 34, 0.1)' }}>
                                <div className="d-flex align-items-center mb-2">
                                  <div className="rounded-circle d-flex align-items-center justify-content-center text-white me-2" style={{ width: '28px', height: '28px', backgroundColor: '#ff5722' }}>
                                    <i className="bi bi-tools"></i>
                                  </div>
                                  <div className="fw-bold">{resource?.name || `Resource #${conflict.resource_id}`}</div>
                                </div>
                                
                                <div className="ps-4">
                                  <div className="text-muted mb-1">Also assigned to:</div>
                                  <div className="fw-bold">{otherTask?.task_name || `Task #${otherTaskId}`}</div>
                                  <div className="small">
                                    <i className="bi bi-clock me-1"></i>
                                    {formatDate(otherTask?.planned_start_iso)} - {formatDate(otherTask?.planned_end_iso)}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Action Buttons */}
                <div className="task-details-section">
                  <div className="d-flex justify-content-end">
                    <Button 
                      variant="outline-primary" 
                      className="btn-modern me-2"
                      onClick={() => window.location.href = `/dashboard?task=${selectedTask.task_id}`}
                    >
                      <i className="bi bi-pencil me-1"></i>
                      Edit Task
                    </Button>
                    <Button 
                      variant="primary" 
                      className="btn-modern"
                      onClick={() => alert(`Reschedule functionality for task ${selectedTask.task_id} would go here`)}
                    >
                      <i className="bi bi-calendar-check me-1"></i>
                      Reschedule
                    </Button>
                  </div>
                </div>
              </Card.Body>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

export default Calendar;