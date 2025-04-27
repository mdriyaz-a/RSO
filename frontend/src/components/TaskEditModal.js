import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col, ListGroup, Badge } from 'react-bootstrap';
import axios from 'axios';
import DatePicker from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";

function TaskEditModal({ show, onHide, task, onTaskUpdated, allTasks }) {
  const [formData, setFormData] = useState({
    task_name: '',
    estimated_hours: 0,
    phase: '',
    priority: 1,
    dependencies: []
  });
  const [availableTasks, setAvailableTasks] = useState([]);
  const [newDependency, setNewDependency] = useState({
    depends_on_task_id: '',
    lag_hours: 0,
    dependency_type: 'FS'
  });
  const [plannedStart, setPlannedStart] = useState(null);
  const [plannedEnd, setPlannedEnd] = useState(null);
  const [editMode, setEditMode] = useState('details'); // 'details' or 'schedule'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [warnings, setWarnings] = useState([]);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingSubmitData, setPendingSubmitData] = useState(null);
  
  // Helper function to calculate default end date (start date + estimated hours)
  const calculateDefaultEndDate = (startDate, estimatedHours = 1) => {
    if (!startDate) return null;
    const endDate = new Date(startDate);
    endDate.setHours(endDate.getHours() + (estimatedHours || 1)); // Use estimated hours or default to 1 hour
    return endDate;
  };
  
  // Helper function to get current date and time
  const getCurrentDateTime = () => {
    const now = new Date();
    // Add a small buffer (1 minute) to account for the time it takes to select a time
    now.setMinutes(now.getMinutes() + 1);
    return now;
  };

  // Initialize form data when task changes
  useEffect(() => {
    if (task) {
      console.log("Task data in modal:", task);
      
      setFormData({
        task_name: task.task_name || '',
        estimated_hours: task.estimated_hours || 0,
        phase: task.phase || '',
        priority: task.priority || 1,
        dependencies: Array.isArray(task.dependencies) ? task.dependencies : []
      });

      // Set planned start and end dates if available
      if (task.planned_start) {
        const startDate = new Date(task.planned_start);
        console.log('Setting planned start from task.planned_start:', task.planned_start);
        console.log('Converted to Date object:', startDate);
        setPlannedStart(startDate);
      } else if (task.planned_start_iso) {
        const startDate = new Date(task.planned_start_iso);
        console.log('Setting planned start from task.planned_start_iso:', task.planned_start_iso);
        console.log('Converted to Date object:', startDate);
        setPlannedStart(startDate);
      }
      
      if (task.planned_end) {
        const endDate = new Date(task.planned_end);
        console.log('Setting planned end from task.planned_end:', task.planned_end);
        console.log('Converted to Date object:', endDate);
        setPlannedEnd(endDate);
      } else if (task.planned_end_iso) {
        const endDate = new Date(task.planned_end_iso);
        console.log('Setting planned end from task.planned_end_iso:', task.planned_end_iso);
        console.log('Converted to Date object:', endDate);
        setPlannedEnd(endDate);
      }

      // Filter out the current task from available tasks for dependencies
      if (allTasks) {
        const filtered = allTasks.filter(t => t.task_id !== task.task_id);
        setAvailableTasks(filtered);
      }
    }
  }, [task, allTasks]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: name === 'estimated_hours' || name === 'priority' ? Number(value) : value
    });
  };

  const handleAddDependency = () => {
    if (!newDependency.depends_on_task_id) {
      setError('Please select a task for the dependency');
      return;
    }

    // Ensure dependencies is an array
    const currentDependencies = Array.isArray(formData.dependencies) ? formData.dependencies : [];

    // Convert depends_on_task_id to number for comparison
    const newDependsOnTaskId = Number(newDependency.depends_on_task_id);

    // Check if dependency already exists
    const exists = currentDependencies.some(
      dep => Number(dep.depends_on_task_id) === newDependsOnTaskId
    );

    if (exists) {
      setError('This dependency already exists');
      return;
    }

    // Add the new dependency
    const updatedDependencies = [
      ...currentDependencies,
      {
        ...newDependency,
        depends_on_task_id: newDependsOnTaskId,
        lag_hours: Number(newDependency.lag_hours)
      }
    ];

    console.log("Adding dependency:", newDependency);
    console.log("Updated dependencies:", updatedDependencies);

    setFormData({
      ...formData,
      dependencies: updatedDependencies
    });

    // Reset the new dependency form
    setNewDependency({
      depends_on_task_id: '',
      lag_hours: 0,
      dependency_type: 'FS'
    });

    setError('');
  };

  const handleRemoveDependency = (dependsOnTaskId) => {
    // Ensure dependencies is an array
    if (!Array.isArray(formData.dependencies)) {
      console.error("Dependencies is not an array:", formData.dependencies);
      return;
    }
    
    console.log("Removing dependency with ID:", dependsOnTaskId);
    
    const updatedDependencies = formData.dependencies.filter(
      dep => Number(dep.depends_on_task_id) !== Number(dependsOnTaskId)
    );
    
    console.log("Updated dependencies after removal:", updatedDependencies);

    setFormData({
      ...formData,
      dependencies: updatedDependencies
    });
  };

  const handleSubmit = async (forceSubmit = false) => {
    setLoading(true);
    setError('');
    setSuccess('');
    setWarnings([]);

    try {
      if (editMode === 'details') {
        // Update task details
        console.log("Submitting task details:", formData);
        const response = await axios.put(`/api/tasks/${task.task_id}`, formData);
        
        console.log("Task update response:", response.data);
        setSuccess(response.data.message);
        
        // If task needs rescheduling, show that message
        if (response.data.needs_reschedule) {
          setSuccess(`${response.data.message} ${response.data.reschedule_message}`);
        }
        
        // If there's a reschedule result, show details
        if (response.data.reschedule_result) {
          const rescheduleData = response.data.reschedule_result;
          if (typeof rescheduleData === 'object') {
            if (rescheduleData.preserved_tasks && rescheduleData.rescheduled_tasks) {
              setSuccess(prev => `${prev} ${rescheduleData.rescheduled_tasks} tasks were rescheduled.`);
            }
          }
        }
      } else {
        // Update task schedule
        const scheduleData = {};
        
        // Check if dates are in the past
        const now = getCurrentDateTime();
        
        // Check if at least one date is provided
        if (!plannedStart && !plannedEnd) {
          setLoading(false);
          setError("Please provide at least a start date or end date for the task.");
          return;
        }
        
        if (plannedStart) {
          console.log('Planned start before conversion:', plannedStart);
          console.log('Planned start type:', typeof plannedStart);
          console.log('Planned start instanceof Date:', plannedStart instanceof Date);
          
          // Ensure we have a valid Date object
          const startDate = plannedStart instanceof Date ? plannedStart : new Date(plannedStart);
          
          // Check if start date is in the past
          if (startDate < now) {
            setLoading(false);
            setError("You can't schedule a task in the past. Please select a future date and time.");
            return;
          }
          
          // Create a string that preserves the local time
          const startYear = startDate.getFullYear();
          const startMonth = String(startDate.getMonth() + 1).padStart(2, '0');
          const startDay = String(startDate.getDate()).padStart(2, '0');
          const startHours = String(startDate.getHours()).padStart(2, '0');
          const startMinutes = String(startDate.getMinutes()).padStart(2, '0');
          const startSeconds = String(startDate.getSeconds()).padStart(2, '0');
          
          // Format: YYYY-MM-DD HH:MM:SS (this will be interpreted as local time by the server)
          scheduleData.planned_start = `${startYear}-${startMonth}-${startDay} ${startHours}:${startMinutes}:${startSeconds}`;
          
          console.log('Final planned_start value:', scheduleData.planned_start);
        }
        
        if (plannedEnd) {
          console.log('Planned end before conversion:', plannedEnd);
          console.log('Planned end type:', typeof plannedEnd);
          console.log('Planned end instanceof Date:', plannedEnd instanceof Date);
          
          // Ensure we have a valid Date object
          const endDate = plannedEnd instanceof Date ? plannedEnd : new Date(plannedEnd);
          
          // Check if end date is in the past
          if (endDate < now) {
            setLoading(false);
            setError("You can't schedule a task end time in the past. Please select a future date and time.");
            return;
          }
          
          // Check if end date is before start date
          if (plannedStart && endDate < plannedStart) {
            setLoading(false);
            setError("End date must be after start date. Please adjust your selection.");
            return;
          }
          
          // Create a string that preserves the local time
          const endYear = endDate.getFullYear();
          const endMonth = String(endDate.getMonth() + 1).padStart(2, '0');
          const endDay = String(endDate.getDate()).padStart(2, '0');
          const endHours = String(endDate.getHours()).padStart(2, '0');
          const endMinutes = String(endDate.getMinutes()).padStart(2, '0');
          const endSeconds = String(endDate.getSeconds()).padStart(2, '0');
          
          // Format: YYYY-MM-DD HH:MM:SS (this will be interpreted as local time by the server)
          scheduleData.planned_end = `${endYear}-${endMonth}-${endDay} ${endHours}:${endMinutes}:${endSeconds}`;
          
          console.log('Final planned_end value:', scheduleData.planned_end);
        }
        
        console.log("Submitting schedule update:", scheduleData);
        
        // Debug the actual data being sent
        console.log("JSON payload:", JSON.stringify(scheduleData));
        
        // If we're not forcing the submit, check for conflicts first
        if (!forceSubmit) {
          // Store the data for later use if we need to confirm
          setPendingSubmitData(scheduleData);
          
          // Make a preliminary request to check for conflicts
          try {
            const checkResponse = await axios.put(`/api/schedules/${task.task_id}?check_only=true`, scheduleData);
            console.log("Schedule check response:", checkResponse.data);
            
            // Check for dependency warnings
            if (checkResponse.data.has_dependency_warnings) {
              const dependencyWarnings = checkResponse.data.dependency_warnings;
              if (dependencyWarnings && dependencyWarnings.length > 0) {
                setWarnings(prev => [
                  ...prev,
                  ...dependencyWarnings.map(dep => ({
                    type: 'dependency',
                    message: `Task depends on "${dep.task_name}" which ends after the new planned start.`,
                    details: dep
                  }))
                ]);
              }
            }
            
            // Check for resource conflicts
            if (checkResponse.data.has_conflicts) {
              const resourceConflicts = checkResponse.data.resource_conflicts || [];
              const employeeConflicts = checkResponse.data.employee_conflicts || [];
              
              if (resourceConflicts.length > 0) {
                setWarnings(prev => [
                  ...prev,
                  ...resourceConflicts.map(conflict => ({
                    type: 'resource',
                    message: `Resource "${conflict.resource_name}" is already assigned to task "${conflict.task_name}" during this time.`,
                    details: conflict
                  }))
                ]);
              }
              
              if (employeeConflicts.length > 0) {
                setWarnings(prev => [
                  ...prev,
                  ...employeeConflicts.map(conflict => ({
                    type: 'employee',
                    message: `Employee "${conflict.employee_name}" is already assigned to task "${conflict.task_name}" during this time.`,
                    details: conflict
                  }))
                ]);
              }
            }
            
            // If we have warnings, show the confirmation dialog
            if (warnings.length > 0 || 
                (checkResponse.data.has_dependency_warnings) || 
                (checkResponse.data.has_conflicts)) {
              setShowConfirmDialog(true);
              setLoading(false);
              return; // Exit early to show the dialog
            }
          } catch (checkErr) {
            console.error("Error checking schedule conflicts:", checkErr);
            // Continue with the update even if the check fails
          }
        }
        
        // If we get here, either there are no conflicts or the user confirmed
        const response = await axios.put(`/api/schedules/${task.task_id}`, scheduleData);
        
        console.log("Schedule update response:", response.data);
        
        // If the API returned updated schedule data, update the form
        if (response.data.updated_schedule) {
          console.log("Received updated schedule:", response.data.updated_schedule);
          
          if (response.data.updated_schedule.planned_start) {
            const newStart = new Date(response.data.updated_schedule.planned_start);
            console.log("Setting new planned start:", newStart);
            setPlannedStart(newStart);
          }
          
          if (response.data.updated_schedule.planned_end) {
            const newEnd = new Date(response.data.updated_schedule.planned_end);
            console.log("Setting new planned end:", newEnd);
            setPlannedEnd(newEnd);
          }
          
          // If estimated_hours was updated, update the form data
          if (response.data.updated_schedule.estimated_hours) {
            console.log("Setting new estimated hours:", response.data.updated_schedule.estimated_hours);
            setFormData(prev => ({
              ...prev,
              estimated_hours: response.data.updated_schedule.estimated_hours
            }));
          }
        }
        
        // If there was a rescheduling result, show it
        if (response.data.rescheduling_result) {
          console.log("Rescheduling result:", response.data.rescheduling_result);
          
          if (response.data.rescheduling_result.rescheduled_tasks && 
              response.data.rescheduling_result.rescheduled_tasks.length > 0) {
            const count = response.data.rescheduling_result.rescheduled_tasks.length;
            setSuccess(`${response.data.message}. ${count} dependent task(s) were rescheduled.`);
            
            // Show the rescheduled tasks
            const rescheduledTaskNames = response.data.rescheduling_result.rescheduled_tasks
              .map(t => `${t.name} (ID: ${t.task_id})`)
              .join(', ');
            
            console.log(`Rescheduled tasks: ${rescheduledTaskNames}`);
          } else if (response.data.rescheduling_result.success) {
            setSuccess(`${response.data.message}. Schedule updated successfully.`);
          } else {
            setError(`Schedule updated but rescheduling failed: ${response.data.rescheduling_result.message}`);
          }
        }
        
        setSuccess(response.data.message);
        
        // If there are conflicts, show a warning
        if (response.data.has_conflicts) {
          setError('Schedule updated but resource conflicts were detected. Please check the resource assignments.');
        }
        
        // If there was a rescheduling error, show it
        if (response.data.rescheduling_error) {
          setError(`Warning: ${response.data.rescheduling_error}`);
        }
        
        // Reset the confirmation dialog state
        setShowConfirmDialog(false);
        setPendingSubmitData(null);
      }

      // Notify parent component that task was updated
      if (onTaskUpdated) {
        onTaskUpdated();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred while updating the task');
      console.error('Error updating task:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleConfirmSubmit = () => {
    // User confirmed despite warnings, proceed with the update
    handleSubmit(true);
  };
  
  const handleCancelSubmit = () => {
    // User canceled the update
    setShowConfirmDialog(false);
    setPendingSubmitData(null);
    setWarnings([]);
    setLoading(false);
  };

  const getTaskNameById = (taskId) => {
    if (!allTasks || !Array.isArray(allTasks)) {
      return `Task ${taskId}`;
    }
    
    // Convert taskId to number if it's a string
    const numericTaskId = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId;
    
    const task = allTasks.find(t => t.task_id === numericTaskId);
    return task ? task.task_name : `Task ${taskId}`;
  };

  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>
          Edit Task: {task?.task_name}
          <div className="mt-2">
            <Badge 
              variant={editMode === 'details' ? 'primary' : 'secondary'} 
              onClick={() => setEditMode('details')}
              style={{ cursor: 'pointer', marginRight: '10px' }}
            >
              Task Details
            </Badge>
            <Badge 
              variant={editMode === 'schedule' ? 'primary' : 'secondary'} 
              onClick={() => setEditMode('schedule')}
              style={{ cursor: 'pointer' }}
            >
              Schedule
            </Badge>
          </div>
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}
        
        {editMode === 'details' ? (
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Task Name</Form.Label>
              <Form.Control
                type="text"
                name="task_name"
                value={formData.task_name}
                onChange={handleInputChange}
              />
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Label>Estimated Hours</Form.Label>
              <Form.Control
                type="number"
                name="estimated_hours"
                value={formData.estimated_hours}
                onChange={handleInputChange}
                min="0"
                step="0.5"
              />
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Label>Phase</Form.Label>
              <Form.Control
                as="select"
                name="phase"
                value={formData.phase}
                onChange={handleInputChange}
              >
                <option value="">Select Phase</option>
                <option value="sales">Sales</option>
                <option value="preConstruction">Pre-Construction</option>
                <option value="activeConstruction">Active Construction</option>
                <option value="postConstruction">Post-Construction</option>
              </Form.Control>
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Label>Priority</Form.Label>
              <Form.Control
                type="number"
                name="priority"
                value={formData.priority}
                onChange={handleInputChange}
                min="1"
                max="10"
              />
            </Form.Group>
            
            <h5 className="mt-4">Dependencies</h5>
            
            <ListGroup className="mb-3">
              {Array.isArray(formData.dependencies) && formData.dependencies.map((dep) => (
                <ListGroup.Item 
                  key={dep.depends_on_task_id} 
                  className="d-flex justify-content-between align-items-center"
                >
                  <div>
                    <strong>{getTaskNameById(dep.depends_on_task_id)}</strong>
                    <span className="ms-2">
                      ({dep.dependency_type || 'FS'}, Lag: {dep.lag_hours || 0} hours)
                    </span>
                  </div>
                  <Button 
                    variant="danger" 
                    size="sm"
                    onClick={() => handleRemoveDependency(dep.depends_on_task_id)}
                  >
                    Remove
                  </Button>
                </ListGroup.Item>
              ))}
              {(!Array.isArray(formData.dependencies) || formData.dependencies.length === 0) && (
                <ListGroup.Item className="text-muted">No dependencies</ListGroup.Item>
              )}
            </ListGroup>
            
            <h6>Add Dependency</h6>
            <Row className="mb-3">
              <Col md={5}>
                <Form.Control
                  as="select"
                  value={newDependency.depends_on_task_id}
                  onChange={(e) => setNewDependency({...newDependency, depends_on_task_id: e.target.value})}
                >
                  <option value="">Select Task</option>
                  {availableTasks.map((t) => (
                    <option key={t.task_id} value={t.task_id}>
                      {t.task_name}
                    </option>
                  ))}
                </Form.Control>
              </Col>
              <Col md={3}>
                <Form.Control
                  as="select"
                  value={newDependency.dependency_type}
                  onChange={(e) => setNewDependency({...newDependency, dependency_type: e.target.value})}
                >
                  <option value="FS">Finish-to-Start</option>
                  <option value="SS">Start-to-Start</option>
                  <option value="FF">Finish-to-Finish</option>
                  <option value="SF">Start-to-Finish</option>
                </Form.Control>
              </Col>
              <Col md={2}>
                <Form.Control
                  type="number"
                  placeholder="Lag (hrs)"
                  value={newDependency.lag_hours}
                  onChange={(e) => setNewDependency({...newDependency, lag_hours: e.target.value})}
                  min="0"
                />
              </Col>
              <Col md={2}>
                <Button onClick={handleAddDependency} variant="primary" size="sm">
                  Add
                </Button>
              </Col>
            </Row>
          </Form>
        ) : (
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Planned Start <small className="text-muted">(future dates only)</small></Form.Label>
              <div>
                <DatePicker
                  selected={plannedStart}
                  onChange={date => {
                    console.log('Selected start date:', date);
                    console.log('ISO string:', date ? date.toISOString() : null);
                    
                    // Ensure the selected date is not in the past
                    const now = getCurrentDateTime();
                    if (date && date < now) {
                      // If selected time is in the past, set it to current time
                      console.log('Selected time is in the past, adjusting to current time');
                      date = now;
                    }
                    
                    setPlannedStart(date);
                    
                    if (date) {
                      // If end date is before the new start date or not set, update end date
                      if (!plannedEnd || plannedEnd < date) {
                        // Calculate new end date based on estimated hours
                        const newEndDate = calculateDefaultEndDate(date, formData.estimated_hours);
                        setPlannedEnd(newEndDate);
                        console.log('Auto-updated end date:', newEndDate);
                      }
                    }
                  }}
                  showTimeSelect
                  timeFormat="HH:mm"
                  timeIntervals={15}
                  dateFormat="MMMM d, yyyy h:mm aa"
                  className="form-control"
                  popperPlacement="bottom-start"
                  popperModifiers={{
                    preventOverflow: {
                      enabled: true,
                      escapeWithReference: false,
                      boundariesElement: 'viewport'
                    }
                  }}
                  timeCaption="Time"
                  minDate={getCurrentDateTime()} // Prevent selecting dates and times before now
                  filterTime={(time) => {
                    const now = getCurrentDateTime();
                    const selectedDate = new Date(plannedStart || now);
                    const selectedTime = new Date(selectedDate);
                    selectedTime.setHours(time.getHours(), time.getMinutes(), 0, 0);
                    
                    // If the selected date is today, filter out past times
                    if (selectedDate.toDateString() === now.toDateString()) {
                      return selectedTime >= now;
                    }
                    
                    // For future dates, allow all times
                    return true;
                  }}
                />
              </div>
              {plannedStart && (
                <small className="text-muted">
                  Selected: {plannedStart.toLocaleString()} ({plannedStart.toISOString()})
                </small>
              )}
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Label>Planned End <small className="text-muted">(future dates only)</small></Form.Label>
              <div>
                <DatePicker
                  selected={plannedEnd}
                  onChange={date => {
                    console.log('Selected end date:', date);
                    console.log('ISO string:', date ? date.toISOString() : null);
                    
                    // Ensure the selected date is not in the past
                    const now = getCurrentDateTime();
                    if (date && date < now) {
                      // If selected time is in the past, set it to current time
                      console.log('Selected time is in the past, adjusting to current time');
                      date = now;
                    }
                    
                    // Ensure end date is after start date
                    if (date && plannedStart && date < plannedStart) {
                      // If end date is before start date, set it to start date + 1 hour
                      console.log('End date is before start date, adjusting');
                      date = calculateDefaultEndDate(plannedStart, 1);
                    }
                    
                    setPlannedEnd(date);
                  }}
                  showTimeSelect
                  timeFormat="HH:mm"
                  timeIntervals={15}
                  dateFormat="MMMM d, yyyy h:mm aa"
                  className="form-control"
                  popperPlacement="bottom-start"
                  popperModifiers={{
                    preventOverflow: {
                      enabled: true,
                      escapeWithReference: false,
                      boundariesElement: 'viewport'
                    }
                  }}
                  timeCaption="Time"
                  minDate={plannedStart || getCurrentDateTime()} // Use planned start or current time if no start date selected
                  filterTime={(time) => {
                    const now = getCurrentDateTime();
                    const selectedDate = new Date(plannedEnd || plannedStart || now);
                    const selectedTime = new Date(selectedDate);
                    selectedTime.setHours(time.getHours(), time.getMinutes(), 0, 0);
                    
                    // If the selected date is today, filter out past times
                    if (selectedDate.toDateString() === now.toDateString()) {
                      return selectedTime >= now;
                    }
                    
                    // For future dates, allow all times
                    return true;
                  }}
                />
              </div>
              {plannedEnd && (
                <small className="text-muted">
                  Selected: {plannedEnd.toLocaleString()} ({plannedEnd.toISOString()})
                </small>
              )}
            </Form.Group>
            
            <div className="alert alert-warning">
              <strong>Warning:</strong> Manually changing the schedule may cause resource conflicts. 
              The system will check for conflicts when you save.
            </div>
            
            <div className="alert alert-info">
              <strong>Note:</strong> You cannot schedule tasks in the past. All dates and times must be in the future.
            </div>
          </Form>
        )}
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>
          Cancel
        </Button>
        <Button 
          variant="primary" 
          onClick={() => handleSubmit(false)}
          disabled={loading}
        >
          {loading ? 'Saving...' : 'Save Changes'}
        </Button>
      </Modal.Footer>
      
      {/* Confirmation Dialog for Warnings */}
      <Modal show={showConfirmDialog} onHide={handleCancelSubmit} backdrop="static" centered>
        <Modal.Header closeButton>
          <Modal.Title>Warning: Scheduling Conflicts</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {warnings.length > 0 ? (
            <>
              <p className="text-danger">The following issues were detected with your schedule change:</p>
              <ul className="list-group mb-3">
                {warnings.map((warning, index) => (
                  <li key={index} className="list-group-item list-group-item-warning">
                    <i className="bi bi-exclamation-triangle-fill me-2"></i>
                    {warning.message}
                  </li>
                ))}
              </ul>
              <p>Do you still want to proceed with these changes?</p>
            </>
          ) : (
            <p>There may be conflicts with your schedule change. Do you want to proceed anyway?</p>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCancelSubmit}>
            Cancel
          </Button>
          <Button variant="warning" onClick={handleConfirmSubmit}>
            Proceed Anyway
          </Button>
        </Modal.Footer>
      </Modal>
    </Modal>
  );
}

export default TaskEditModal;