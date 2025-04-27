import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, ListGroup, Badge, Alert } from 'react-bootstrap';
import axios from 'axios';

function ResourceAssignmentManager({ 
  show, 
  onHide, 
  task, 
  employees, 
  resources, 
  currentAssignments, 
  onAssignmentsUpdated 
}) {
  // Check if task is completed
  const isTaskCompleted = task?.status === 'Completed' || task?.status === 'Skipped';
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [lastResponse, setLastResponse] = useState(null);
  
  // Selected entities to assign
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('');
  const [selectedResourceId, setSelectedResourceId] = useState('');
  
  // Reset state when modal is closed
  useEffect(() => {
    if (!show) {
      setSelectedEmployeeId('');
      setSelectedResourceId('');
      setError(null);
      setSuccess(null);
      setLastResponse(null);
    }
  }, [show]);
  
  // Debug assignments
  useEffect(() => {
    if (show && task) {
      console.log('Task:', task);
      console.log('Current assignments:', currentAssignments);
    }
  }, [show, task, currentAssignments]);
  
  // Get current assignments for this task
  const taskEmployeeAssignments = currentAssignments?.employee_assignments?.filter(
    a => parseInt(a.task_id) === parseInt(task?.task_id)
  ) || [];
  
  const taskResourceAssignments = currentAssignments?.resource_assignments?.filter(
    a => parseInt(a.task_id) === parseInt(task?.task_id)
  ) || [];
  
  // Debug filtered assignments
  useEffect(() => {
    if (show && task) {
      console.log('Task employee assignments:', taskEmployeeAssignments);
      console.log('Task resource assignments:', taskResourceAssignments);
    }
  }, [show, task, taskEmployeeAssignments, taskResourceAssignments]);
  

  
  // Get available employees (not assigned to other tasks at the same time)
  const getAvailableEmployees = () => {
    if (!task || !employees || !currentAssignments?.employee_assignments) {
      return [];
    }
    
    // Get all employee assignments that overlap with this task's time
    const overlappingAssignments = currentAssignments.employee_assignments.filter(a => {
      // Skip assignments for this task
      if (parseInt(a.task_id) === parseInt(task.task_id)) return false;
      
      // Skip completed or skipped tasks
      if (a.status === 'Completed' || a.status === 'Skipped') return false;
      
      // Check for time overlap
      const taskStart = new Date(task.planned_start_iso || task.start_iso);
      const taskEnd = new Date(task.planned_end_iso || task.end_iso);
      const assignmentStart = new Date(a.planned_start_iso);
      const assignmentEnd = new Date(a.planned_end_iso);
      
      return (
        (taskStart <= assignmentEnd && taskEnd >= assignmentStart)
      );
    });
    
    // Get IDs of employees with overlapping assignments
    const unavailableEmployeeIds = overlappingAssignments.map(a => parseInt(a.employee_id));
    
    // Return all employees, but mark which ones are available
    return employees.map(employee => ({
      ...employee,
      isAvailable: !unavailableEmployeeIds.includes(parseInt(employee.employee_id))
    }));
  };
  
  // Get available resources (not assigned to other tasks at the same time)
  const getAvailableResources = () => {
    if (!task || !resources || !currentAssignments?.resource_assignments) {
      return [];
    }
    
    // Get all resource assignments that overlap with this task's time
    const overlappingAssignments = currentAssignments.resource_assignments.filter(a => {
      // Skip assignments for this task
      if (parseInt(a.task_id) === parseInt(task.task_id)) return false;
      
      // Skip completed or skipped tasks
      if (a.status === 'Completed' || a.status === 'Skipped') return false;
      
      // Check for time overlap
      const taskStart = new Date(task.planned_start_iso || task.start_iso);
      const taskEnd = new Date(task.planned_end_iso || task.end_iso);
      const assignmentStart = new Date(a.planned_start_iso);
      const assignmentEnd = new Date(a.planned_end_iso);
      
      return (
        (taskStart <= assignmentEnd && taskEnd >= assignmentStart)
      );
    });
    
    // Get IDs of resources with overlapping assignments
    const unavailableResourceIds = overlappingAssignments.map(a => parseInt(a.resource_id));
    
    // Return all resources, but mark which ones are available
    return resources.map(resource => ({
      ...resource,
      isAvailable: !unavailableResourceIds.includes(parseInt(resource.resource_id))
    }));
  };
  
  // Get available employees and resources
  const availableEmployees = getAvailableEmployees();
  const availableResources = getAvailableResources();
  
  // Debug assignments
  useEffect(() => {
    if (show && task) {
      console.log('Task:', task);
      console.log('Current assignments:', currentAssignments);
      console.log('Task employee assignments:', taskEmployeeAssignments);
      console.log('Task resource assignments:', taskResourceAssignments);
      console.log('Available employees:', availableEmployees);
      console.log('Available resources:', availableResources);
    }
  }, [show, task, currentAssignments, taskEmployeeAssignments, taskResourceAssignments, availableEmployees, availableResources]);
  
  // Handle assignment creation
  const handleCreateAssignment = async (type, entityId) => {
    if (!entityId) {
      setError(`Please select a ${type} to assign`);
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      
      const response = await axios.post('/api/assignments/create', {
        type,
        task_id: task.task_id,
        entity_id: parseInt(entityId),
        is_initial: false, // This is a user modification, not an initial assignment
        is_modified: true
      });
      
      // Store the response for use in the UI
      setLastResponse(response);
      
      console.log('Assignment created:', response.data);
      
      // Check if there's a warning about unavailable resources
      if (response.data.warning) {
        // Format a more detailed warning message with conflict details
        let warningMessage = response.data.warning;
        
        if (response.data.conflicts && response.data.conflicts.length > 0) {
          warningMessage += "\n\nConflicting tasks:";
          response.data.conflicts.forEach((conflict, index) => {
            warningMessage += `\n${index + 1}. Task ${conflict.task_id} (${conflict.task_name})`;
            warningMessage += `\n   Time: ${new Date(conflict.start_time).toLocaleString()} - ${new Date(conflict.end_time).toLocaleString()}`;
            warningMessage += `\n   Status: ${conflict.status}`;
          });
          
          warningMessage += "\n\nYou may want to reschedule these tasks to resolve the conflicts.";
        }
        
        setError(warningMessage);
        setSuccess(`${type === 'employee' ? 'Employee' : 'Resource'} assigned successfully, but with conflicts.`);
      } else {
        setSuccess(`${type === 'employee' ? 'Employee' : 'Resource'} assigned successfully`);
      }
      
      // Reset selection
      if (type === 'employee') {
        setSelectedEmployeeId('');
      } else {
        setSelectedResourceId('');
      }
      
      // Trigger a reschedule
      try {
        const rescheduleResponse = await axios.post('/api/assignments/reschedule', {
          task_id: task.task_id
        });
        console.log('Reschedule response:', rescheduleResponse.data);
      } catch (rescheduleError) {
        console.error('Error triggering reschedule:', rescheduleError);
      }
      
      // Notify parent component to refresh assignments
      if (onAssignmentsUpdated) {
        onAssignmentsUpdated();
      }
    } catch (error) {
      console.error(`Error creating ${type} assignment:`, error);
      setError(error.response?.data?.error || `Failed to assign ${type}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Handle assignment deletion
  const handleDeleteAssignment = async (type, assignmentId) => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      
      const response = await axios.post('/api/assignments/delete', {
        type,
        assignment_id: assignmentId
      });
      
      console.log('Assignment deleted:', response.data);
      
      setSuccess(`${type === 'employee' ? 'Employee' : 'Resource'} unassigned successfully`);
      
      // Trigger a reschedule
      try {
        const rescheduleResponse = await axios.post('/api/assignments/reschedule', {
          task_id: task.task_id
        });
        console.log('Reschedule response:', rescheduleResponse.data);
      } catch (rescheduleError) {
        console.error('Error triggering reschedule:', rescheduleError);
      }
      
      // Notify parent component to refresh assignments
      if (onAssignmentsUpdated) {
        onAssignmentsUpdated();
      }
    } catch (error) {
      console.error(`Error deleting ${type} assignment:`, error);
      setError(error.response?.data?.error || `Failed to unassign ${type}`);
    } finally {
      setLoading(false);
    }
  };
  
  if (!task) return null;
  
  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>Manage Resource Assignments</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {/* Regular error message */}
        {error && !lastResponse?.data?.conflicts && (
          <Alert variant="danger" onClose={() => setError(null)} dismissible>
            <div style={{ whiteSpace: 'pre-line' }}>{error}</div>
          </Alert>
        )}
        
        {/* Conflict warning with more user-friendly UI */}
        {lastResponse?.data?.conflicts && lastResponse.data.conflicts.length > 0 && (
          <Alert variant="warning" onClose={() => setLastResponse(null)} dismissible>
            <Alert.Heading>
              <i className="bi bi-exclamation-triangle-fill me-2"></i>
              Resource Scheduling Conflict
            </Alert.Heading>
            
            <p>
              The {lastResponse.data.type || 'resource'} you're trying to assign is already scheduled for other tasks during this time period.
              You have two options:
            </p>
            <ul>
              <li><strong>Reschedule</strong> - Automatically reschedule the conflicting tasks with available resources</li>
              <li><strong>Skip and Continue</strong> - Keep the assignment with conflicts (conflicts will be shown in the UI)</li>
            </ul>
            
            <div className="mt-3 mb-3">
              <strong>Conflicting Tasks:</strong>
              <div className="mt-2">
                {lastResponse.data.conflicts.map((conflict, index) => (
                  <div key={`conflict-${conflict.task_id}`} className="card mb-2">
                    <div className="card-body py-2">
                      <div className="d-flex justify-content-between align-items-center">
                        <div>
                          <strong>Task {conflict.task_id}:</strong> {conflict.task_name}
                          <div className="small text-muted">
                            Time: {new Date(conflict.start_time).toLocaleString()} - {new Date(conflict.end_time).toLocaleString()}
                          </div>
                          <div className="small text-muted">
                            Status: <Badge bg={
                              conflict.status === 'Completed' ? 'success' :
                              conflict.status === 'In Progress' ? 'primary' :
                              conflict.status === 'Paused' ? 'warning' :
                              conflict.status === 'On Hold' ? 'danger' :
                              conflict.status === 'Skipped' ? 'secondary' : 'info'
                            }>
                              {conflict.status}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="d-flex justify-content-between">
              <Button 
                variant="primary"
                size="sm"
                onClick={() => {
                  setLoading(true);
                  // First, close the warning message
                  setLastResponse(null);
                  
                  // Show a message that we're rescheduling
                  setSuccess('Rescheduling conflicting tasks with available resources... This may take a moment.');
                  
                  // Get all conflicting task IDs
                  const conflictingTaskIds = lastResponse.data.conflicts.map(conflict => conflict.task_id);
                  
                  // Create a series of promises to reschedule each conflicting task
                  const reschedulePromises = conflictingTaskIds.map(taskId => 
                    axios.post('/api/assignments/reschedule', { task_id: taskId })
                  );
                  
                  // Execute all reschedule operations
                  Promise.all(reschedulePromises)
                    .then(responses => {
                      console.log('Reschedule responses:', responses);
                      setSuccess('Conflicting tasks have been rescheduled with available resources successfully.');
                      
                      // Notify parent component to refresh assignments
                      if (onAssignmentsUpdated) {
                        onAssignmentsUpdated();
                      }
                    })
                    .catch(error => {
                      console.error('Error rescheduling tasks:', error);
                      setError('There was an error rescheduling tasks. Please try again or contact support.');
                    })
                    .finally(() => {
                      setLoading(false);
                    });
                }}
                disabled={loading}
              >
                {loading ? 'Rescheduling...' : 'Reschedule'}
              </Button>
              
              <Button 
                variant="warning"
                size="sm"
                onClick={() => {
                  // Dismiss the warning and keep the assignment
                  setLastResponse(null);
                  setSuccess('Assignment created with conflicts. The conflicts will be shown in the UI.');
                }}
              >
                <i className="bi bi-exclamation-triangle me-1"></i>
                Skip and Continue
              </Button>
            </div>
          </Alert>
        )}
        
        {success && (
          <Alert variant="success" onClose={() => setSuccess(null)} dismissible>
            {success}
          </Alert>
        )}
        
        {isTaskCompleted && (
          <Alert variant="warning">
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            This task is marked as {task.status}. Resource assignments cannot be modified.
          </Alert>
        )}
        
        <h5 className="mb-3">
          Task: {task.task_name} (ID: {task.task_id})
          <Badge bg={
            task.status === 'Completed' ? 'success' :
            task.status === 'In Progress' ? 'primary' :
            task.status === 'Paused' ? 'warning' :
            task.status === 'On Hold' ? 'danger' :
            task.status === 'Skipped' ? 'secondary' :
            'info'
          } className="ms-2">
            {task.status}
          </Badge>
        </h5>
        
        <div className="row">
          {/* Employee Assignments */}
          <div className="col-md-6">
            <div className="mb-4">
              <h6 className="border-bottom pb-2">Assigned Employees</h6>
              
              {taskEmployeeAssignments.length > 0 ? (
                <ListGroup variant="flush" className="mb-3">
                  {taskEmployeeAssignments.map(assignment => {
                    // Find the employee details
                    const employee = employees.find(e => parseInt(e.employee_id) === parseInt(assignment.employee_id));
                    const roleName = employee?.role_name || 'No role assigned';
                    
                    return (
                      <ListGroup.Item 
                        key={`emp-${assignment.assignment_id}`}
                        className="d-flex justify-content-between align-items-center py-2"
                      >
                        <div>
                          <Badge bg="primary" className="me-2">ID: {assignment.employee_id}</Badge>
                          {assignment.employee_name}
                          <Badge bg="info" className="ms-2">{roleName}</Badge>
                          {assignment.is_initial && (
                            <Badge bg="secondary" className="ms-2">Initial Assignment</Badge>
                          )}
                          {assignment.is_modified && (
                            <Badge bg="warning" className="ms-2">Modified</Badge>
                          )}
                        </div>
                        <Button 
                          variant="outline-danger" 
                          size="sm"
                          onClick={() => handleDeleteAssignment('employee', assignment.assignment_id)}
                          disabled={loading || isTaskCompleted}
                        >
                          <i className="bi bi-x-lg"></i>
                        </Button>
                      </ListGroup.Item>
                    );
                  })}
                </ListGroup>
              ) : (
                <p className="text-muted">No employees assigned</p>
              )}
              
              <Form className="mt-3">
                <Form.Group className="mb-3">
                  <Form.Label>Assign Employee</Form.Label>
                  <div className="d-flex">
                    <Form.Select 
                      value={selectedEmployeeId}
                      onChange={e => setSelectedEmployeeId(e.target.value)}
                      className="me-2"
                      disabled={loading || isTaskCompleted}
                    >
                      <option value="">Select Employee</option>
                      {employees.map(employee => {
                        // Check if employee is already assigned to this task
                        const isAssigned = taskEmployeeAssignments.some(
                          a => parseInt(a.employee_id) === parseInt(employee.employee_id)
                        );
                        
                        // Check if employee is available based on schedule
                        const matchingEmployee = availableEmployees.find(
                          e => parseInt(e.employee_id) === parseInt(employee.employee_id)
                        );
                        const isScheduleAvailable = matchingEmployee ? matchingEmployee.isAvailable : true;
                        
                        // Check if employee is marked as available in the database
                        const isMarkedAvailable = employee.availability !== false;
                        
                        // Determine status text
                        let statusText = '';
                        if (isAssigned) {
                          const assignment = taskEmployeeAssignments.find(
                            a => parseInt(a.employee_id) === parseInt(employee.employee_id)
                          );
                          statusText = assignment?.is_initial ? ' (Initial Assignment)' : ' (User Assigned)';
                        } else if (!isScheduleAvailable) {
                          statusText = ' (Unavailable - Schedule Conflict)';
                        } else if (!isMarkedAvailable) {
                          statusText = ' (Marked Unavailable)';
                        }
                        
                        return (
                          <option 
                            key={`select-emp-${employee.employee_id}`} 
                            value={employee.employee_id}
                            disabled={isAssigned}
                            style={{
                              color: (!isMarkedAvailable && !isAssigned) ? 'red' : 
                                    (!isScheduleAvailable && !isAssigned) ? 'orange' : 
                                    'inherit'
                            }}
                          >
                            {employee.name} ({employee.role_name || 'No role assigned'})
                            {statusText}
                          </option>
                        );
                      })}
                      {employees.length === 0 && (
                        <option disabled>No employees found</option>
                      )}
                    </Form.Select>
                    <Button 
                      variant="primary"
                      onClick={() => handleCreateAssignment('employee', selectedEmployeeId)}
                      disabled={loading || !selectedEmployeeId || isTaskCompleted}
                    >
                      Assign
                    </Button>
                  </div>
                </Form.Group>
              </Form>
            </div>
          </div>
          
          {/* Resource Assignments */}
          <div className="col-md-6">
            <div className="mb-4">
              <h6 className="border-bottom pb-2">Assigned Resources</h6>
              
              {taskResourceAssignments.length > 0 ? (
                <ListGroup variant="flush" className="mb-3">
                  {taskResourceAssignments.map(assignment => {
                    // Find the resource details
                    const resource = resources.find(r => parseInt(r.resource_id) === parseInt(assignment.resource_id));
                    const resourceType = resource?.type || 'No type specified';
                    
                    return (
                      <ListGroup.Item 
                        key={`res-${assignment.assignment_id}`}
                        className="d-flex justify-content-between align-items-center py-2"
                      >
                        <div>
                          <Badge bg="info" className="me-2">ID: {assignment.resource_id}</Badge>
                          {assignment.resource_name}
                          <Badge bg="success" className="ms-2">{resourceType}</Badge>
                          {assignment.is_initial && (
                            <Badge bg="secondary" className="ms-2">Initial Assignment</Badge>
                          )}
                          {assignment.is_modified && (
                            <Badge bg="warning" className="ms-2">Modified</Badge>
                          )}
                        </div>
                        <Button 
                          variant="outline-danger" 
                          size="sm"
                          onClick={() => handleDeleteAssignment('resource', assignment.assignment_id)}
                          disabled={loading || isTaskCompleted}
                        >
                          <i className="bi bi-x-lg"></i>
                        </Button>
                      </ListGroup.Item>
                    );
                  })}
                </ListGroup>
              ) : (
                <p className="text-muted">No resources assigned</p>
              )}
              
              <Form className="mt-3">
                <Form.Group className="mb-3">
                  <Form.Label>Assign Resource</Form.Label>
                  <div className="d-flex">
                    <Form.Select 
                      value={selectedResourceId}
                      onChange={e => setSelectedResourceId(e.target.value)}
                      className="me-2"
                      disabled={loading || isTaskCompleted}
                    >
                      <option value="">Select Resource</option>
                      {resources.map(resource => {
                        // Check if resource is already assigned to this task
                        const isAssigned = taskResourceAssignments.some(
                          a => parseInt(a.resource_id) === parseInt(resource.resource_id)
                        );
                        
                        // Check if resource is available based on schedule
                        const matchingResource = availableResources.find(
                          r => parseInt(r.resource_id) === parseInt(resource.resource_id)
                        );
                        const isScheduleAvailable = matchingResource ? matchingResource.isAvailable : true;
                        
                        // Check if resource is marked as available in the database
                        const isMarkedAvailable = resource.availability !== false;
                        
                        // Determine status text
                        let statusText = '';
                        if (isAssigned) {
                          const assignment = taskResourceAssignments.find(
                            a => parseInt(a.resource_id) === parseInt(resource.resource_id)
                          );
                          statusText = assignment?.is_initial ? ' (Initial Assignment)' : ' (User Assigned)';
                        } else if (!isScheduleAvailable) {
                          statusText = ' (Unavailable - Schedule Conflict)';
                        } else if (!isMarkedAvailable) {
                          statusText = ' (Marked Unavailable)';
                        }
                        
                        return (
                          <option 
                            key={`select-res-${resource.resource_id}`} 
                            value={resource.resource_id}
                            disabled={isAssigned}
                            style={{
                              color: (!isMarkedAvailable && !isAssigned) ? 'red' : 
                                    (!isScheduleAvailable && !isAssigned) ? 'orange' : 
                                    'inherit'
                            }}
                          >
                            {resource.name} ({resource.type || 'No type specified'})
                            {statusText}
                          </option>
                        );
                      })}
                      {resources.length === 0 && (
                        <option disabled>No resources found</option>
                      )}
                    </Form.Select>
                    <Button 
                      variant="primary"
                      onClick={() => handleCreateAssignment('resource', selectedResourceId)}
                      disabled={loading || !selectedResourceId || isTaskCompleted}
                    >
                      Assign
                    </Button>
                  </div>
                </Form.Group>
              </Form>
            </div>
          </div>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide} disabled={loading}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

export default ResourceAssignmentManager;