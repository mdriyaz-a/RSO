import React, { useState, useEffect, useRef } from 'react';
import { Button, Card, Form, Modal, Badge } from 'react-bootstrap';
import axios from 'axios';
import 'dhtmlx-gantt/codebase/dhtmlxgantt.css';

function GanttChart() {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [taskDependencies, setTaskDependencies] = useState({});
  const [resourceAssignments, setResourceAssignments] = useState(null);
  const [showDependencies, setShowDependencies] = useState(true);
  const ganttContainer = useRef(null);
  const ganttInstance = useRef(null);
  
  // Modal states
  const [showRescheduleModal, setShowRescheduleModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [rescheduleDetails, setRescheduleDetails] = useState({
    new_start: '',
    new_end: '',
    reason: ''
  });

  useEffect(() => {
    fetchSchedules();
    fetchTaskDependencies();
    fetchResourceAssignments();
    
    // Initialize Gantt chart
    import('dhtmlx-gantt').then(gantt => {
      ganttInstance.current = gantt.default;
      
      ganttInstance.current.config.date_format = "%Y-%m-%d %H:%i";
      ganttInstance.current.config.columns = [
        {name: "text", label: "Task name", width: 200, tree: true},
        {name: "start_date", label: "Start time", width: 130, align: "center"},
        {name: "duration", label: "Duration", width: 60, align: "center"},
        {name: "status", label: "Status", width: 100, align: "center"}
      ];
      
      ganttInstance.current.config.scale_unit = "day";
      ganttInstance.current.config.step = 1;
      ganttInstance.current.config.date_scale = "%d %M";
      ganttInstance.current.config.subscales = [
        {unit: "hour", step: 6, date: "%H:%i"}
      ];
      
      // Configure links (dependencies)
      ganttInstance.current.config.links = {
        "finish_to_start": "0",
        "start_to_start": "1",
        "finish_to_finish": "2",
        "start_to_finish": "3"
      };
      
      // Link styling
      ganttInstance.current.templates.link_class = function(link) {
        if (link.type === "1") return "start-to-start";
        if (link.type === "2") return "finish-to-finish";
        if (link.type === "3") return "start-to-finish";
        return ""; // default finish-to-start
      };
      
      ganttInstance.current.templates.task_class = function(start, end, task) {
        if (task.status === 'Completed') return 'task-completed';
        if (task.status === 'Paused') return 'task-paused';
        if (task.status === 'On Hold') return 'task-on-hold';
        if (task.status === 'Skipped') return 'task-skipped';
        
        if (task.delay_or_ahead) {
          const delay = parseFloat(task.delay_or_ahead);
          if (delay > 0) return 'task-delayed';
          if (delay < 0) return 'task-early';
        }
        
        return 'task-on-time';
      };
      
      ganttInstance.current.templates.tooltip_text = function(start, end, task) {
        let tooltip = `<b>${task.text}</b><br/>`;
        tooltip += `Planned: ${task.planned_start} - ${task.planned_end}<br/>`;
        
        if (task.actual_start || task.actual_end) {
          tooltip += `Actual: ${task.actual_start || 'Not started'} - ${task.actual_end || 'Not completed'}<br/>`;
        }
        
        if (task.delay_or_ahead) {
          tooltip += `Delay/Ahead: ${task.delay_or_ahead}`;
        }
        
        if (task.dependencies && task.dependencies.length > 0) {
          tooltip += `<br/><b>Dependencies:</b> ${task.dependencies.map(d => d.taskId).join(', ')}`;
        }
        
        // Display assigned resources
        if (task.assigned_resources && task.assigned_resources.length > 0) {
          tooltip += `<br/><b>Resources:</b> `;
          task.assigned_resources.forEach((resource, index) => {
            tooltip += `${resource.name}${resource.is_initial ? ' (Original)' : ''}`;
            if (index < task.assigned_resources.length - 1) {
              tooltip += ', ';
            }
          });
        }
        
        // Display assigned employees
        if (task.assigned_employees && task.assigned_employees.length > 0) {
          tooltip += `<br/><b>Employees:</b> `;
          task.assigned_employees.forEach((employee, index) => {
            tooltip += `${employee.name}${employee.is_initial ? ' (Original)' : ''}`;
            if (index < task.assigned_employees.length - 1) {
              tooltip += ', ';
            }
          });
        }
        
        return tooltip;
      };
      
      ganttInstance.current.attachEvent("onTaskClick", function(id, e) {
        const task = ganttInstance.current.getTask(id);
        handleTaskClick(task);
        return true;
      });
      
      ganttInstance.current.init(ganttContainer.current);
    });
    
    return () => {
      if (ganttInstance.current && ganttInstance.current.destructor) {
        ganttInstance.current.destructor();
      }
    };
  }, []);

  useEffect(() => {
    if (ganttInstance.current && schedules.length > 0) {
      // Group tasks by phase
      const phases = [...new Set(schedules.map(task => task.phase))].filter(Boolean);
      
      // Create parent tasks for each phase
      const phaseParents = phases.map((phase, index) => ({
        id: `phase_${index}`,
        text: `Phase: ${phase}`,
        type: 'project',
        open: true,
        render: 'split',
        phase: phase
      }));
      
      // Get assignments for each task
      const taskAssignments = {};
      
      // If resourceAssignments is available, process it
      if (resourceAssignments && resourceAssignments.employee_assignments) {
        // Group employee assignments by task
        resourceAssignments.employee_assignments.forEach(assignment => {
          if (!taskAssignments[assignment.task_id]) {
            taskAssignments[assignment.task_id] = {
              assigned_employees: [],
              assigned_resources: []
            };
          }
          
          taskAssignments[assignment.task_id].assigned_employees.push({
            id: assignment.employee_id,
            name: assignment.employee_name,
            is_initial: assignment.is_initial,
            is_modified: assignment.is_modified
          });
        });
        
        // Group resource assignments by task
        resourceAssignments.resource_assignments.forEach(assignment => {
          if (!taskAssignments[assignment.task_id]) {
            taskAssignments[assignment.task_id] = {
              assigned_employees: [],
              assigned_resources: []
            };
          }
          
          taskAssignments[assignment.task_id].assigned_resources.push({
            id: assignment.resource_id,
            name: assignment.resource_name,
            is_initial: assignment.is_initial,
            is_modified: assignment.is_modified
          });
        });
      }
      
      // Assign tasks to their respective phases
      const taskData = schedules.map(task => {
        const phaseIndex = phases.indexOf(task.phase);
        
        // Get assignments for this task
        const assignments = taskAssignments[task.task_id] || {
          assigned_employees: [],
          assigned_resources: []
        };
        
        return {
          id: task.task_id,
          text: task.task_name,
          start_date: new Date(task.planned_start_iso || task.planned_start),
          end_date: new Date(task.planned_end_iso || task.planned_end),
          planned_start: new Date(task.planned_start_iso || task.planned_start).toLocaleString(),
          planned_end: new Date(task.planned_end_iso || task.planned_end).toLocaleString(),
          actual_start: task.actual_start_iso ? new Date(task.actual_start_iso).toLocaleString() : null,
          actual_end: task.actual_end_iso ? new Date(task.actual_end_iso).toLocaleString() : null,
          status: task.status,
          delay_or_ahead: task.delay_or_ahead,
          priority: task.priority,
          phase: task.phase,
          parent: task.phase ? `phase_${phaseIndex}` : 0,
          dependencies: taskDependencies[task.task_id] || [],
          assigned_employees: assignments.assigned_employees,
          assigned_resources: assignments.assigned_resources
        };
      });
      
      // Create dependency links
      const links = [];
      if (showDependencies) {
        Object.entries(taskDependencies).forEach(([taskId, dependencies]) => {
          dependencies.forEach((dep, index) => {
            // Map dependency types to Gantt link types
            let linkType = "0"; // Default: Finish-to-Start
            if (dep.type === "start_to_start") linkType = "1";
            if (dep.type === "finish_to_finish") linkType = "2";
            if (dep.type === "start_to_finish") linkType = "3";
            
            links.push({
              id: `${taskId}_${dep.taskId}_${index}`,
              source: dep.taskId,
              target: taskId,
              type: linkType,
              lag: dep.lagHours || 0
            });
          });
        });
      }
      
      // Combine phase parents and tasks
      const ganttData = {
        data: [...phaseParents, ...taskData],
        links: links
      };
      
      ganttInstance.current.clearAll();
      ganttInstance.current.parse(ganttData);
    }
  }, [schedules, taskDependencies, resourceAssignments, showDependencies]);

  const fetchSchedules = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/schedules');
      setSchedules(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching schedules:', error);
      setLoading(false);
    }
  };
  
  const fetchTaskDependencies = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/tasks');
      
      // Create a dependency map
      const dependencyMap = {};
      
      response.data.forEach(task => {
        if (task.dependencies && task.dependencies.length > 0) {
          dependencyMap[task.task_id] = task.dependencies.map(dep => ({
            taskId: dep.depends_on_task_id,
            lagHours: dep.lag_hours,
            type: dep.dependency_type
          }));
        }
      });
      
      setTaskDependencies(dependencyMap);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching task dependencies:', error);
      setLoading(false);
    }
  };
  
  const fetchResourceAssignments = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/assignments');
      setResourceAssignments(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching resource assignments:', error);
      setLoading(false);
    }
  };

  const handleTaskClick = (task) => {
    // Find the original task data
    const originalTask = schedules.find(t => t.task_id === parseInt(task.id));
    if (!originalTask) return;
    
    setSelectedTask(originalTask);
    
    // Format dates for the form
    const startDate = new Date(originalTask.planned_start_iso || originalTask.planned_start);
    const endDate = new Date(originalTask.planned_end_iso || originalTask.planned_end);
    
    const formatDateForInput = (date) => {
      return date.toISOString().slice(0, 16); // Format as YYYY-MM-DDTHH:MM
    };
    
    setRescheduleDetails({
      new_start: formatDateForInput(startDate),
      new_end: formatDateForInput(endDate),
      reason: ''
    });
    
    setShowRescheduleModal(true);
  };

  const submitReschedule = async () => {
    try {
      setLoading(true);
      setShowRescheduleModal(false);
      
      await axios.post('/api/reschedule/event', {
        task_id: selectedTask.task_id,
        event_type: 'manual_reschedule',
        timestamp: new Date().toISOString(),
        details: {
          new_start: new Date(rescheduleDetails.new_start).toISOString(),
          new_end: new Date(rescheduleDetails.new_end).toISOString(),
          reason: rescheduleDetails.reason
        }
      });
      
      await fetchSchedules();
    } catch (error) {
      console.error('Error rescheduling task:', error);
      setLoading(false);
    }
  };

  return (
    <div>
      <Card className="mb-4">
        <Card.Header>
          <div className="d-flex justify-content-between align-items-center">
            <h5 className="mb-0">Gantt Chart</h5>
            <div>
              <Form.Check 
                type="switch"
                id="dependency-switch"
                label="Show Dependencies"
                checked={showDependencies}
                onChange={(e) => setShowDependencies(e.target.checked)}
                className="d-inline-block me-3"
              />
              <Button 
                variant="primary" 
                onClick={() => {
                  fetchSchedules();
                  fetchTaskDependencies();
                  fetchResourceAssignments();
                }}
                disabled={loading}
              >
                {loading ? 'Loading...' : 'Refresh'}
              </Button>
            </div>
          </div>
        </Card.Header>
        <Card.Body>
          <div 
            ref={ganttContainer} 
            className="gantt-container"
            style={{ height: '600px', width: '100%' }}
          ></div>
          
          <div className="mt-3">
            <div className="d-flex flex-wrap">
              <div className="me-3 mb-2">
                <span className="badge bg-success me-1">&nbsp;</span>
                <small>On Time</small>
              </div>
              <div className="me-3 mb-2">
                <span className="badge bg-danger me-1">&nbsp;</span>
                <small>Delayed</small>
              </div>
              <div className="me-3 mb-2">
                <span className="badge bg-primary me-1">&nbsp;</span>
                <small>Early</small>
              </div>
              <div className="me-3 mb-2">
                <span className="badge bg-warning me-1">&nbsp;</span>
                <small>Paused</small>
              </div>
              <div className="me-3 mb-2">
                <span className="badge bg-secondary me-1">&nbsp;</span>
                <small>Skipped</small>
              </div>
              
              {showDependencies && (
                <>
                  <div className="ms-4 me-3 mb-2">
                    <span className="badge bg-dark me-1">&nbsp;</span>
                    <small>Finish-to-Start</small>
                  </div>
                  <div className="me-3 mb-2">
                    <span className="badge bg-info me-1">&nbsp;</span>
                    <small>Start-to-Start</small>
                  </div>
                  <div className="me-3 mb-2">
                    <span className="badge bg-warning me-1">&nbsp;</span>
                    <small>Finish-to-Finish</small>
                  </div>
                </>
              )}
            </div>
            <small className="text-muted">
              Click on any task bar to manually reschedule it. 
              {showDependencies && ' Lines between tasks represent dependencies.'}
            </small>
          </div>
        </Card.Body>
      </Card>

      {/* Reschedule Modal */}
      <Modal show={showRescheduleModal} onHide={() => setShowRescheduleModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Reschedule Task</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedTask && (
            <Form>
              <Form.Group className="mb-3">
                <Form.Label>Task</Form.Label>
                <Form.Control type="text" value={selectedTask.task_name} disabled />
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Label>New Start Time</Form.Label>
                <Form.Control 
                  type="datetime-local" 
                  value={rescheduleDetails.new_start}
                  onChange={(e) => setRescheduleDetails({...rescheduleDetails, new_start: e.target.value})}
                />
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Label>New End Time</Form.Label>
                <Form.Control 
                  type="datetime-local" 
                  value={rescheduleDetails.new_end}
                  onChange={(e) => setRescheduleDetails({...rescheduleDetails, new_end: e.target.value})}
                />
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Label>Reason</Form.Label>
                <Form.Control 
                  as="textarea" 
                  rows={3} 
                  value={rescheduleDetails.reason}
                  onChange={(e) => setRescheduleDetails({...rescheduleDetails, reason: e.target.value})}
                  placeholder="Why is this task being rescheduled?"
                />
              </Form.Group>
            </Form>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowRescheduleModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submitReschedule}>
            Reschedule
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
}

export default GanttChart;