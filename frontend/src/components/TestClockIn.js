import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button, Card, Alert, Form, ListGroup, Badge } from 'react-bootstrap';
import { formatDate, formatTime } from '../utils/timeFormatters';
import TaskTimeDisplay from './TaskTimeDisplay';

function TestClockIn() {
  const [tasks, setTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [clockedIn, setClockedIn] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [startTime, setStartTime] = useState(null);
  const [useTaskStartTime, setUseTaskStartTime] = useState(false);
  const [showAllTasks, setShowAllTasks] = useState(false);
  const [activeTasks, setActiveTasks] = useState([]);
  const [resourceAssignments, setResourceAssignments] = useState({
    employee_assignments: [],
    resource_assignments: [],
    employee_conflicts: [],
    resource_conflicts: []
  });
  const [resourceConflictWarning, setResourceConflictWarning] = useState(null);

  // Fetch available tasks and resource assignments
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch tasks
        const tasksResponse = await axios.get('/api/schedules');
        
        // Filter tasks that are not completed
        // Note: We include skipped tasks in the list, but will disable the clock-in button for them
        const availableTasks = tasksResponse.data.filter(t => 
          t.status !== 'Completed'
        );
        
        // Find tasks that are already in progress
        const inProgressTasks = availableTasks.filter(t => 
          t.status === 'In Progress' && t.actual_start && !t.actual_end
        );
        
        setActiveTasks(inProgressTasks);
        setTasks(availableTasks);
        
        // Fetch resource assignments
        const assignmentsResponse = await axios.get('/api/assignments');
        setResourceAssignments(assignmentsResponse.data);
        
        if (availableTasks.length > 0 && !selectedTask) {
          setSelectedTask(availableTasks[0]);
          console.log('Selected first available task:', availableTasks[0]);
        } else if (availableTasks.length === 0) {
          setError('No available tasks found for testing');
        }
      } catch (err) {
        setError('Error fetching data: ' + err.message);
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Timer effect
  useEffect(() => {
    let timerId;
    
    if (clockedIn && startTime) {
      // Update elapsed time every second
      timerId = setInterval(() => {
        const now = new Date();
        const elapsed = Math.floor((now - startTime) / 1000);
        setElapsedTime(elapsed);
      }, 1000);
    }
    
    return () => {
      if (timerId) clearInterval(timerId);
    };
  }, [clockedIn, startTime]);

  // Check for resource conflicts with active tasks
  const checkResourceConflicts = (task) => {
    if (!task || activeTasks.length === 0) return null;
    
    const taskId = task.task_id;
    const conflicts = [];
    
    // Check employee assignments
    const taskEmployeeAssignments = resourceAssignments.employee_assignments.filter(
      a => a.task_id === taskId
    );
    
    // For each employee assigned to this task
    taskEmployeeAssignments.forEach(assignment => {
      const employeeId = assignment.employee_id;
      
      // Check if any active task is using the same employee
      activeTasks.forEach(activeTask => {
        const activeTaskEmployees = resourceAssignments.employee_assignments.filter(
          a => a.task_id === activeTask.task_id && a.employee_id === employeeId
        );
        
        if (activeTaskEmployees.length > 0) {
          conflicts.push({
            type: 'employee',
            resourceId: employeeId,
            resourceName: assignment.employee_name,
            activeTaskId: activeTask.task_id,
            activeTaskName: activeTask.task_name
          });
        }
      });
    });
    
    // Check resource assignments
    const taskResourceAssignments = resourceAssignments.resource_assignments.filter(
      a => a.task_id === taskId
    );
    
    // For each resource assigned to this task
    taskResourceAssignments.forEach(assignment => {
      const resourceId = assignment.resource_id;
      
      // Check if any active task is using the same resource
      activeTasks.forEach(activeTask => {
        const activeTaskResources = resourceAssignments.resource_assignments.filter(
          a => a.task_id === activeTask.task_id && a.resource_id === resourceId
        );
        
        if (activeTaskResources.length > 0) {
          conflicts.push({
            type: 'resource',
            resourceId: resourceId,
            resourceName: assignment.resource_name,
            activeTaskId: activeTask.task_id,
            activeTaskName: activeTask.task_name
          });
        }
      });
    });
    
    return conflicts.length > 0 ? conflicts : null;
  };

  // Handle task selection
  const handleTaskSelect = (task) => {
    setSelectedTask(task);
    console.log('Selected task:', task);
    
    // Check for resource conflicts
    const conflicts = checkResourceConflicts(task);
    if (conflicts) {
      const conflictMessages = conflicts.map(c => 
        `${c.type === 'employee' ? 'Employee' : 'Resource'} "${c.resourceName}" is already assigned to active task ${c.activeTaskId} (${c.activeTaskName})`
      );
      
      setResourceConflictWarning(
        `Warning: This task has resource conflicts with currently active tasks:\n${conflictMessages.join('\n')}`
      );
    } else {
      setResourceConflictWarning(null);
    }
  };

  // Find tasks scheduled at the same time
  const getTasksAtSameTime = (task) => {
    if (!task || !task.planned_start_iso) return [];
    
    return tasks.filter(t => 
      t.task_id !== task.task_id && 
      t.planned_start_iso === task.planned_start_iso &&
      t.status !== 'Completed' && 
      t.status !== 'Skipped' &&
      !(t.status === 'In Progress' && t.actual_start && !t.actual_end)
    );
  };

  const handleClockIn = async () => {
    if (!selectedTask) return;
    
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      
      console.log('Clocking in task:', selectedTask.task_id);
      
      // Determine timestamp to use
      let timestamp;
      if (useTaskStartTime && selectedTask.planned_start_iso) {
        timestamp = selectedTask.planned_start_iso;
        console.log('Using planned start time for clock-in:', timestamp);
      } else {
        timestamp = new Date().toISOString();
        console.log('Using current time for clock-in:', timestamp);
      }
      
      const response = await axios.post('/api/reschedule/event', {
        task_id: selectedTask.task_id,
        event_type: 'clock_in',
        timestamp: timestamp,
        details: {
          reason: 'Test clock-in'
        }
      });
      
      console.log('Clock-in response:', response.data);
      
      if (response.data.success) {
        setSuccess(`Successfully clocked in task ${selectedTask.task_id}`);
        setClockedIn(true);
        setStartTime(new Date(timestamp));
        setResourceConflictWarning(null);
        
        // Fetch the updated tasks
        const updatedResponse = await axios.get('/api/schedules');
        const updatedTasks = updatedResponse.data.filter(t => 
          t.status !== 'Completed' && 
          t.status !== 'Skipped'
        );
        
        setTasks(updatedTasks);
        
        // Update the selected task
        const updatedTask = updatedResponse.data.find(t => t.task_id === selectedTask.task_id);
        if (updatedTask) {
          setSelectedTask(updatedTask);
          console.log('Updated task after clock-in:', updatedTask);
        }
        
        // Update active tasks
        const inProgressTasks = updatedResponse.data.filter(t => 
          t.status === 'In Progress' && t.actual_start && !t.actual_end
        );
        setActiveTasks(inProgressTasks);
        
        // Refresh resource assignments
        const assignmentsResponse = await axios.get('/api/assignments');
        setResourceAssignments(assignmentsResponse.data);
      } else {
        setError(`Failed to clock in: ${response.data.message}`);
      }
    } catch (err) {
      setError('Error clocking in: ' + err.message);
      console.error('Error clocking in:', err);
    } finally {
      setLoading(false);
    }
  };

  const [completedPercentage, setCompletedPercentage] = useState(50);
  const [remainingHours, setRemainingHours] = useState(1);
  const [carryOver, setCarryOver] = useState(false);
  
  const handleClockOut = async () => {
    if (!selectedTask || !clockedIn) return;
    
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      
      console.log('Clocking out task:', selectedTask.task_id);
      
      // Check if it's end of day
      const now = new Date();
      const isEndOfDay = now.getHours() >= 17; // 5:00 PM
      
      // Prepare the details object
      const details = {
        reason: 'Test clock-out',
        completed_percentage: completedPercentage,
        carry_over: carryOver
      };
      
      // If it's end of day or carry-over is requested, include remaining_hours
      if (isEndOfDay || carryOver) {
        details.remaining_hours = remainingHours;
      }
      
      const response = await axios.post('/api/reschedule/event', {
        task_id: selectedTask.task_id,
        event_type: 'clock_out',
        timestamp: now.toISOString(),
        details: details
      });
      
      console.log('Clock-out response:', response.data);
      
      if (response.data.success) {
        setSuccess(`Successfully clocked out task ${selectedTask.task_id}`);
        setClockedIn(false);
        setStartTime(null);
        setElapsedTime(0);
        setResourceConflictWarning(null);
        
        // Fetch the updated tasks
        const updatedResponse = await axios.get('/api/schedules');
        const updatedTasks = updatedResponse.data.filter(t => 
          t.status !== 'Completed' && 
          t.status !== 'Skipped'
        );
        
        setTasks(updatedTasks);
        
        // Update the selected task
        const updatedTask = updatedResponse.data.find(t => t.task_id === selectedTask.task_id);
        if (updatedTask) {
          setSelectedTask(updatedTask);
          console.log('Updated task after clock-out:', updatedTask);
        }
        
        // Update active tasks
        const inProgressTasks = updatedResponse.data.filter(t => 
          t.status === 'In Progress' && t.actual_start && !t.actual_end
        );
        setActiveTasks(inProgressTasks);
        
        // Refresh resource assignments
        const assignmentsResponse = await axios.get('/api/assignments');
        setResourceAssignments(assignmentsResponse.data);
      } else {
        setError(`Failed to clock out: ${response.data.message}`);
      }
    } catch (err) {
      setError('Error clocking out: ' + err.message);
      console.error('Error clocking out:', err);
    } finally {
      setLoading(false);
    }
  };

  // Format seconds into HH:MM:SS
  const formatTime = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    return [
      hours.toString().padStart(2, '0'),
      minutes.toString().padStart(2, '0'),
      seconds.toString().padStart(2, '0')
    ].join(':');
  };

  // We're now using the imported formatDate function from timeFormatters.js
  
  // We're now using the TaskTimeDisplay component instead of this function
  // This function is kept for backward compatibility with any code that might still use it
  const formatTaskSchedule = (startDateStr, endDateStr) => {
    if (!startDateStr || !endDateStr) return 'Schedule not set';
    
    const startDate = new Date(startDateStr);
    const endDate = new Date(endDateStr);
    
    // Calculate duration in hours and minutes
    const durationMs = endDate - startDate;
    const durationHours = Math.floor(durationMs / (1000 * 60 * 60));
    const durationMinutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    
    // Format using our new utility
    return `🕓 ${formatTime(startDate)} – ${formatTime(endDate)} (${formatDate(startDate)})`;
  };

  return (
    <Card className="mb-4">
      <Card.Header>
        <h5>Clock-In Test Tool</h5>
      </Card.Header>
      <Card.Body>
        {loading && <Alert variant="info">Loading...</Alert>}
        {error && <Alert variant="danger">{error}</Alert>}
        {success && <Alert variant="success">{success}</Alert>}
        
        {tasks.length > 0 ? (
          <div>
            <Form.Group className="mb-3">
              <Form.Check 
                type="checkbox" 
                label="Use task's planned start time for clock-in" 
                checked={useTaskStartTime}
                onChange={(e) => setUseTaskStartTime(e.target.checked)}
              />
              <Form.Check 
                type="checkbox" 
                label="Show all available tasks" 
                checked={showAllTasks}
                onChange={(e) => setShowAllTasks(e.target.checked)}
              />
            </Form.Group>
            
            <h6>Select a Task:</h6>
            <ListGroup className="mb-3">
              {/* Show tasks scheduled at the same time as the selected task */}
              {!showAllTasks && selectedTask && getTasksAtSameTime(selectedTask).length > 0 && (
                <>
                  <ListGroup.Item 
                    active={selectedTask}
                    onClick={() => handleTaskSelect(selectedTask)}
                    style={{ cursor: 'pointer' }}
                  >
                    <strong>{selectedTask.task_name}</strong> (ID: {selectedTask.task_id})
                    <div><small>Schedule:</small></div>
                    <TaskTimeDisplay 
                      startDate={selectedTask.planned_start_iso} 
                      endDate={selectedTask.planned_end_iso} 
                    />
                  </ListGroup.Item>
                  
                  {getTasksAtSameTime(selectedTask).map(task => (
                    <ListGroup.Item 
                      key={task.task_id}
                      active={selectedTask && selectedTask.task_id === task.task_id}
                      onClick={() => handleTaskSelect(task)}
                      style={{ cursor: 'pointer' }}
                    >
                      <strong>{task.task_name}</strong> (ID: {task.task_id})
                      <div>
                        <small>Status: </small>
                        <span className={`badge bg-${task.status === 'Skipped' ? 'warning' : task.status === 'In Progress' ? 'primary' : 'secondary'}`}>
                          {task.status}
                        </span>
                      </div>
                      <div><small>Schedule:</small></div>
                      <TaskTimeDisplay 
                        startDate={task.planned_start_iso} 
                        endDate={task.planned_end_iso} 
                      />
                    </ListGroup.Item>
                  ))}
                </>
              )}
              
              {/* Show all tasks if requested */}
              {showAllTasks && tasks.map(task => (
                <ListGroup.Item 
                  key={task.task_id}
                  active={selectedTask && selectedTask.task_id === task.task_id}
                  onClick={() => handleTaskSelect(task)}
                  style={{ cursor: 'pointer' }}
                >
                  <strong>{task.task_name}</strong> (ID: {task.task_id})
                  <div>
                    <small>Status: </small>
                    <span className={`badge bg-${task.status === 'Skipped' ? 'warning' : task.status === 'In Progress' ? 'primary' : 'secondary'}`}>
                      {task.status}
                    </span>
                  </div>
                  <div><small>Schedule:</small></div>
                  <TaskTimeDisplay 
                    startDate={task.planned_start_iso} 
                    endDate={task.planned_end_iso} 
                  />
                </ListGroup.Item>
              ))}
            </ListGroup>
            
            {selectedTask && (
              <div className="mb-3">
                <h6>Selected Task Details:</h6>
                <p>
                  <strong>ID:</strong> {selectedTask.task_id}<br />
                  <strong>Name:</strong> {selectedTask.task_name}<br />
                  <strong>Status:</strong> {selectedTask.status}<br />
                  <strong>Schedule:</strong><br />
                  <TaskTimeDisplay 
                    startDate={selectedTask.planned_start_iso} 
                    endDate={selectedTask.planned_end_iso} 
                  /><br />
                  <strong>Actual Start:</strong> {selectedTask.actual_start_iso ? formatDate(selectedTask.actual_start_iso) + ' ' + formatTime(selectedTask.actual_start_iso) : 'None'}<br />
                  <strong>Actual End:</strong> {selectedTask.actual_end_iso ? formatDate(selectedTask.actual_end_iso) + ' ' + formatTime(selectedTask.actual_end_iso) : 'None'}
                </p>
                
                {/* Display resource assignments for this task */}
                <div className="mt-2">
                  <h6>Resource Assignments:</h6>
                  {resourceAssignments.employee_assignments.filter(a => a.task_id === selectedTask.task_id).length > 0 ? (
                    <div className="mb-2">
                      <strong>Employees:</strong>{' '}
                      {resourceAssignments.employee_assignments
                        .filter(a => a.task_id === selectedTask.task_id)
                        .map(a => (
                          <Badge key={a.assignment_id} bg="info" className="me-1">
                            {a.employee_name}
                          </Badge>
                        ))}
                    </div>
                  ) : (
                    <div className="mb-2">No employees assigned</div>
                  )}
                  
                  {resourceAssignments.resource_assignments.filter(a => a.task_id === selectedTask.task_id).length > 0 ? (
                    <div>
                      <strong>Resources:</strong>{' '}
                      {resourceAssignments.resource_assignments
                        .filter(a => a.task_id === selectedTask.task_id)
                        .map(a => (
                          <Badge key={a.assignment_id} bg="secondary" className="me-1">
                            {a.resource_name}
                          </Badge>
                        ))}
                    </div>
                  ) : (
                    <div>No resources assigned</div>
                  )}
                </div>
              </div>
            )}
            
            {/* Display resource conflict warning */}
            {resourceConflictWarning && (
              <Alert variant="warning" className="mb-3">
                <Alert.Heading>Resource Conflict Warning</Alert.Heading>
                <p>This task has resource conflicts with currently active tasks:</p>
                <ul>
                  {checkResourceConflicts(selectedTask).map((conflict, index) => (
                    <li key={index}>
                      {conflict.type === 'employee' ? 'Employee' : 'Resource'} <strong>"{conflict.resourceName}"</strong> is 
                      already assigned to active task {conflict.activeTaskId} ({conflict.activeTaskName})
                    </li>
                  ))}
                </ul>
                <p className="mb-0">
                  You can still clock in this task, but be aware that the same resources will be working on multiple tasks simultaneously.
                </p>
              </Alert>
            )}
            
            {clockedIn && (
              <div className="mb-3">
                <Alert variant="primary" className="d-flex align-items-center">
                  <div className="me-3">
                    <Badge bg="danger" className="timer-badge large-timer" style={{ minWidth: '140px', textAlign: 'center' }}>
                      <i className="bi bi-stopwatch-fill me-2"></i>
                      {formatTime(elapsedTime)}
                    </Badge>
                  </div>
                  <div>
                    <strong>Task in progress</strong>
                    <div><small>Started at: {formatDate(startTime)}</small></div>
                  </div>
                </Alert>
              </div>
            )}
            
            {activeTasks.length > 0 && (
              <div className="mb-3">
                <h6>Currently Active Tasks:</h6>
                <ListGroup>
                  {activeTasks.map(task => (
                    <ListGroup.Item key={task.task_id}>
                      <strong>{task.task_name}</strong> (ID: {task.task_id})
                      <div><small>Started at: {formatDate(task.actual_start_iso)}</small></div>
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              </div>
            )}
            
            {clockedIn && (
              <div className="mb-3">
                <h6>Clock-Out Options:</h6>
                <Form.Group className="mb-2">
                  <Form.Label>Completed Percentage:</Form.Label>
                  <Form.Control
                    type="number"
                    min="0"
                    max="100"
                    value={completedPercentage}
                    onChange={(e) => setCompletedPercentage(parseInt(e.target.value))}
                  />
                </Form.Group>
                
                <Form.Group className="mb-2">
                  <Form.Check 
                    type="checkbox" 
                    label="Carry over to next day" 
                    checked={carryOver}
                    onChange={(e) => setCarryOver(e.target.checked)}
                  />
                </Form.Group>
                
                {(carryOver || new Date().getHours() >= 17) && (
                  <Form.Group className="mb-2">
                    <Form.Label>Remaining Work Hours:</Form.Label>
                    <Form.Control
                      type="number"
                      min="0.1"
                      step="0.1"
                      value={remainingHours}
                      onChange={(e) => setRemainingHours(parseFloat(e.target.value))}
                    />
                    <Form.Text className="text-muted">
                      Estimate how many hours of work remain on this task
                    </Form.Text>
                  </Form.Group>
                )}
              </div>
            )}
            
            <div className="d-flex gap-2">
              <Button 
                variant="primary" 
                onClick={handleClockIn}
                disabled={loading || clockedIn || !selectedTask || selectedTask?.status === 'Skipped'}
              >
                Clock In
              </Button>
              
              <Button 
                variant="secondary" 
                onClick={handleClockOut}
                disabled={loading || !clockedIn || !selectedTask}
              >
                Clock Out
              </Button>
            </div>
          </div>
        ) : !loading && (
          <Alert variant="warning">No tasks available for testing</Alert>
        )}
      </Card.Body>
    </Card>
  );
}

export default TestClockIn;