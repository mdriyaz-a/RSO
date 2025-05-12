import React, { useState, useEffect } from 'react';
import { Button, Card, Table, Form, Modal, Nav, Tab, Badge, Tooltip, OverlayTrigger } from 'react-bootstrap';
import axios from 'axios';
import TaskProgressBar from '../components/TaskProgressBar';
import ActiveTaskTimer from '../components/ActiveTaskTimer';
import ResourceAssignmentManager from '../components/ResourceAssignmentManager';
import FullRescheduleButton from '../components/FullRescheduleButton';
import TaskEditModal from '../components/TaskEditModal';

function Dashboard() {
  const [schedules, setSchedules] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  // Removed viewMode dropdown
  const [phases, setPhases] = useState([]);
  const [activePhase, setActivePhase] = useState('all');
  const [taskDependencies, setTaskDependencies] = useState({});
  const [showDependencies, setShowDependencies] = useState(true);
  const [resourceAssignments, setResourceAssignments] = useState({
    employee_assignments: [],
    resource_assignments: [],
    employee_conflicts: [],
    resource_conflicts: []
  });
  const [employees, setEmployees] = useState([]);
  const [resources, setResources] = useState([]);
  const [showResourceConflicts, setShowResourceConflicts] = useState(true);
  const [showResourceAssignmentsModal, setShowResourceAssignmentsModal] = useState(false);
  const [selectedTaskForAssignments, setSelectedTaskForAssignments] = useState(null);
  
  // Modal states
  const [showPauseModal, setShowPauseModal] = useState(false);
  const [showSkipModal, setShowSkipModal] = useState(false);
  const [showDependencyModal, setShowDependencyModal] = useState(false);
  const [showClockOutModal, setShowClockOutModal] = useState(false);
  const [showEditTaskModal, setShowEditTaskModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [pauseDetails, setPauseDetails] = useState({
    reason: '',
    duration_minutes: 15,
    pauseType: 'short_break'
  });
  const [skipReason, setSkipReason] = useState('');
  const [clockOutDetails, setClockOutDetails] = useState({
    reason: '',
    completed_percentage: 0,
    carry_over: true
  });

  // State to control auto-refresh
  const [autoRefresh, setAutoRefresh] = useState(false);
  
  // Function to fetch all data
  const fetchData = async () => {
    setLoading(true);
    try {
      await fetchSchedules(false);
      await fetchTaskDependencies(false);
      await fetchResourceAssignments(false);
      await fetchTasks();
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch tasks
  const fetchTasks = async () => {
    try {
      const response = await axios.get('/api/tasks');
      console.log('Fetched tasks:', response.data);
      setTasks(response.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  useEffect(() => {
    // Initial data fetch
    fetchSchedules(true);
    fetchTaskDependencies(true);
    fetchResourceAssignments(true);
    fetchEmployees();
    fetchResources();
    fetchTasks();
    
    // Set up polling only if autoRefresh is enabled
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        console.log('Auto-refreshing data...');
        fetchSchedules(false); // Pass false to avoid setting loading state
        fetchTaskDependencies(false);
        fetchResourceAssignments(false);
        fetchTasks();
      }, 30000); // Increased to 30 seconds to reduce server load
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]); // Re-run effect when autoRefresh changes
  
  // Fetch employees
  const fetchEmployees = async () => {
    try {
      const response = await axios.get('/api/employees');
      console.log('Fetched employees:', response.data);
      setEmployees(response.data);
    } catch (error) {
      console.error('Error fetching employees:', error);
    }
  };
  
  // Fetch resources
  const fetchResources = async () => {
    try {
      const response = await axios.get('/api/resources');
      console.log('Fetched resources:', response.data);
      setResources(response.data);
    } catch (error) {
      console.error('Error fetching resources:', error);
    }
  };
  
  const fetchResourceAssignments = async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      
      const response = await axios.get('/api/assignments');
      console.log('Fetched resource assignments:', response.data);
      setResourceAssignments(response.data);
      
      if (showLoading) setLoading(false);
    } catch (error) {
      console.error('Error fetching resource assignments:', error);
      if (showLoading) setLoading(false);
    }
  };

  const fetchSchedules = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      
      const response = await axios.get('/api/schedules');
      console.log('Fetched schedules:', response.data);
      setSchedules(response.data);
      
      // Extract unique phases
      const uniquePhases = [...new Set(response.data.map(task => task.phase))].filter(Boolean);
      setPhases(uniquePhases);
    } catch (error) {
      console.error('Error fetching schedules:', error);
    } finally {
      if (showLoading) setLoading(false);
    }
  };
  
  const fetchTaskDependencies = async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      
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
      if (showLoading) setLoading(false);
    } catch (error) {
      console.error('Error fetching task dependencies:', error);
      if (showLoading) setLoading(false);
    }
  };
  


  const runInitialSchedule = async () => {
    try {
      setLoading(true);
      // Show a message to the user that the scheduler is running
      alert('Running initial scheduler. This may take a few moments...');
      
      // Call the API to run the initial scheduler with proper content type
      await axios.post('/api/schedule', {}, {
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      // Fetch the updated schedules and dependencies
      await fetchSchedules();
      await fetchTaskDependencies();
      
      // Show success message
      alert('Initial schedule completed successfully!');
    } catch (error) {
      console.error('Error running initial schedule:', error);
      
      // Get a more detailed error message if available
      let errorMessage = 'Error running initial schedule.';
      if (error.response && error.response.data && error.response.data.error) {
        errorMessage += ' ' + error.response.data.error;
      }
      
      alert(errorMessage + ' Please check the console for details.');
      setLoading(false);
    }
  };
  
  // Get task name by ID
  const getTaskNameById = (taskId) => {
    const task = schedules.find(t => t.task_id === taskId);
    return task ? task.task_name : `Task ${taskId}`;
  };
  
  // Get task status by ID
  const getTaskStatusById = (taskId) => {
    const task = schedules.find(t => t.task_id === taskId);
    return task ? task.status : 'Unknown';
  };
  
  // Check if all dependencies for a task are met
  const areDependenciesMet = (task) => {
    // If task has no dependencies, return true
    if (!taskDependencies[task.task_id]) {
      return true;
    }
    
    // Check each dependency
    for (const dep of taskDependencies[task.task_id]) {
      const dependencyStatus = getTaskStatusById(dep.taskId);
      
      // If any dependency is not completed or skipped, return false
      if (dependencyStatus !== 'Completed' && dependencyStatus !== 'Skipped') {
        console.log(`Task ${task.task_id} has unmet dependency: Task ${dep.taskId} with status ${dependencyStatus}`);
        return false;
      }
    }
    
    // All dependencies are met
    return true;
  };
  
  // Show dependency details modal
  const showDependencyDetails = (task) => {
    setSelectedTask(task);
    setShowDependencyModal(true);
  };

  // Function to handle conflict resolution by rescheduling a task
  const handleRescheduleTask = async (taskId, taskName) => {
    try {
      setLoading(true);
      console.log('Rescheduling task:', taskId);
      
      // Call the API to reschedule the task
      const response = await axios.post('/api/assignments/reschedule', {
        task_id: taskId
      });
      
      console.log('Reschedule response:', response.data);
      
      // Explicitly fetch resource assignments to update conflicts
      await fetchResourceAssignments(true);
      
      // Then fetch all other data
      await fetchSchedules(false);
      await fetchTaskDependencies(false);
      await fetchTasks();
      
      // Show success message with details
      const oldStart = new Date(response.data.old_start).toLocaleString();
      const newStart = new Date(response.data.new_start).toLocaleString();
      alert(`Task ${taskName} has been rescheduled from ${oldStart} to ${newStart}.`);
    } catch (error) {
      console.error('Error rescheduling task:', error);
      alert(`Error rescheduling task: ${error.response?.data?.error || error.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Function to handle conflict resolution by reassigning an employee
  const handleReassignEmployee = async (employeeId, employeeName, taskId, taskName) => {
    try {
      setLoading(true);
      console.log('Reassigning employee:', employeeId, 'from task:', taskId);
      
      // First, delete the current assignment
      const deleteResponse = await axios.post('/api/assignments/delete', {
        type: 'employee',
        assignment_id: null, // We don't have the assignment ID directly
        task_id: taskId,
        employee_id: employeeId
      });
      
      console.log('Delete assignment response:', deleteResponse.data);
      
      // Explicitly fetch resource assignments to update conflicts
      await fetchResourceAssignments(true);
      
      // Then fetch all other data
      await fetchSchedules(false);
      await fetchTaskDependencies(false);
      await fetchTasks();
      
      // Show success message
      alert(`Employee ${employeeName} has been unassigned from task ${taskName}. You can now assign a different employee.`);
      
      // Open the resource assignments modal for this task
      const task = tasks.find(t => t.task_id === taskId);
      if (task) {
        setSelectedTask(task);
        setShowResourceAssignmentsModal(true);
      }
    } catch (error) {
      console.error('Error reassigning employee:', error);
      alert(`Error reassigning employee: ${error.response?.data?.error || error.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Function to handle conflict resolution by reassigning a resource
  const handleReassignResource = async (resourceId, resourceName, taskId, taskName) => {
    try {
      setLoading(true);
      console.log('Reassigning resource:', resourceId, 'from task:', taskId);
      
      // First, delete the current assignment
      const deleteResponse = await axios.post('/api/assignments/delete', {
        type: 'resource',
        assignment_id: null, // We don't have the assignment ID directly
        task_id: taskId,
        resource_id: resourceId
      });
      
      console.log('Delete assignment response:', deleteResponse.data);
      
      // Explicitly fetch resource assignments to update conflicts
      await fetchResourceAssignments(true);
      
      // Then fetch all other data
      await fetchSchedules(false);
      await fetchTaskDependencies(false);
      await fetchTasks();
      
      // Show success message
      alert(`Resource ${resourceName} has been unassigned from task ${taskName}. You can now assign a different resource.`);
      
      // Open the resource assignments modal for this task
      const task = tasks.find(t => t.task_id === taskId);
      if (task) {
        setSelectedTask(task);
        setShowResourceAssignmentsModal(true);
      }
    } catch (error) {
      console.error('Error reassigning resource:', error);
      alert(`Error reassigning resource: ${error.response?.data?.error || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Handle edit task button click
  const handleEditTask = (task) => {
    // Find the full task data from the tasks array
    const fullTaskData = tasks.find(t => t.task_id === task.task_id);
    
    if (fullTaskData) {
      // Merge the schedule data with the task data
      const mergedTask = {
        ...fullTaskData,
        planned_start: task.planned_start || task.planned_start_iso,
        planned_end: task.planned_end || task.planned_end_iso,
        status: task.status
      };
      
      console.log("Full task data for editing:", mergedTask);
      setSelectedTask(mergedTask);
    } else {
      console.log("Using original task data for editing:", task);
      setSelectedTask(task);
    }
    
    setShowEditTaskModal(true);
  };

  // Handle pause button click
  const handlePause = (task) => {
    setSelectedTask(task);
    setShowPauseModal(true);
  };

  // Handle complete button click
  const handleComplete = async (task) => {
    try {
      setLoading(true);
      console.log('Completing task:', task);
      
      const response = await axios.post('/api/reschedule/event', {
        task_id: task.task_id,
        event_type: 'complete',
        timestamp: new Date().toISOString(),
        details: {
          completed_percentage: 100,
          reason: 'Task completed'
        }
      });
      
      console.log('Complete task response:', response.data);
      
      // Immediately fetch updated schedules
      await fetchSchedules();
      
      // Also fetch task dependencies to update the UI
      await fetchTaskDependencies();
      
      // Log refresh is handled automatically
      
      // Show a success message with rescheduling information
      let message = `Task ${task.task_name} has been marked as completed!`;
      
      // Check if any tasks were rescheduled
      if (response.data.rescheduled_tasks && response.data.rescheduled_tasks.length > 0) {
        const rescheduledCount = response.data.rescheduled_tasks.length;
        message += `\n\n${rescheduledCount} dependent task(s) have been rescheduled:`;
        
        // Add details for the first few rescheduled tasks
        const tasksToShow = response.data.rescheduled_tasks.slice(0, 3);
        tasksToShow.forEach(task => {
          const oldStart = new Date(task.original_start).toLocaleTimeString();
          const newStart = new Date(task.new_start).toLocaleTimeString();
          message += `\n- Task ${task.task_id} (${task.name}): ${oldStart} → ${newStart}`;
        });
        
        // If there are more tasks, add a note
        if (rescheduledCount > 3) {
          message += `\n- ... and ${rescheduledCount - 3} more tasks`;
        }
      }
      
      alert(message);
    } catch (error) {
      console.error('Error completing task:', error);
      alert(`Error completing task: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Handle skip button click
  const handleSkip = (task) => {
    setSelectedTask(task);
    setShowSkipModal(true);
  };
  
  // Handle clock-in button click
  const handleClockIn = async (task) => {
    try {
      setLoading(true);
      console.log('Clocking in task:', task.task_id);
      
      // Initialize the timer for this task if it doesn't exist
      if (!window.taskTimers) {
        window.taskTimers = {};
      }
      
      if (!window.taskTimers[task.task_id]) {
        window.taskTimers[task.task_id] = {
          accumulatedTime: 0,
          lastClockInTime: null,
          isRunning: false
        };
      }
      
      // Set the clock-in time and mark as running
      window.taskTimers[task.task_id].lastClockInTime = new Date();
      window.taskTimers[task.task_id].isRunning = true;
      
      console.log(`Dashboard - Clocking in task ${task.task_id}`);
      console.log(`Dashboard - Accumulated time: ${window.taskTimers[task.task_id].accumulatedTime} seconds`);
      
      const response = await axios.post('/api/reschedule/event', {
        task_id: task.task_id,
        event_type: 'clock_in',
        timestamp: new Date().toISOString(),
        details: {
          reason: 'Starting work'
        }
      });
      
      console.log('Clock-in response:', response.data);
      
      // Check if the response contains schedules
      if (response.data && response.data.schedules) {
        console.log('Using schedules from response');
        setSchedules(response.data.schedules);
        
        // Extract unique phases
        const uniquePhases = [...new Set(response.data.schedules.map(task => task.phase))].filter(Boolean);
        setPhases(uniquePhases);
      } else {
        // Immediately fetch updated schedules to get the actual_start time
        console.log('Fetching schedules separately');
        await fetchSchedules();
      }
    } catch (error) {
      console.error('Error clocking in task:', error);
    } finally {
      setLoading(false);
    }
  };
  
  // Handle clock-out button click
  const handleClockOut = (task) => {
    setSelectedTask(task);
    
    // Calculate estimated completion percentage
    const now = new Date();
    const start = task.actual_start ? new Date(task.actual_start_iso) : new Date(task.planned_start_iso);
    const end = new Date(task.planned_end_iso);
    const totalDuration = end - start;
    const elapsed = now - start;
    const completionPercentage = Math.min(100, Math.round((elapsed / totalDuration) * 100));
    
    // Check if it's end of day (after 5 PM)
    const isEndOfDay = now.getHours() >= 17;
    
    setClockOutDetails({
      reason: isEndOfDay ? 'End of day' : 'Work completed for now',
      completed_percentage: completionPercentage,
      carry_over: isEndOfDay && completionPercentage < 100
    });
    
    setShowClockOutModal(true);
  };
  
  // Submit clock-out
  const submitClockOut = async () => {
    try {
      setLoading(true);
      setShowClockOutModal(false);
      
      console.log('Clocking out task:', selectedTask.task_id);
      
      // Ensure we properly handle the timer state when clocking out
      if (window.taskTimers && window.taskTimers[selectedTask.task_id]) {
        const taskTimer = window.taskTimers[selectedTask.task_id];
        
        // If the timer is running, calculate and store the accumulated time
        if (taskTimer.isRunning && taskTimer.lastClockInTime) {
          const sessionTime = Math.floor((new Date() - taskTimer.lastClockInTime) / 1000);
          taskTimer.accumulatedTime = (taskTimer.accumulatedTime || 0) + sessionTime;
          taskTimer.isRunning = false;
          taskTimer.lastClockInTime = null;
          
          console.log(`Dashboard - Clocking out task ${selectedTask.task_id}`);
          console.log(`Dashboard - Final accumulated time: ${taskTimer.accumulatedTime} seconds`);
        }
      }
      
      const response = await axios.post('/api/reschedule/event', {
        task_id: selectedTask.task_id,
        event_type: 'clock_out',
        timestamp: new Date().toISOString(),
        details: {
          reason: clockOutDetails.reason,
          completed_percentage: clockOutDetails.completed_percentage,
          carry_over: clockOutDetails.carry_over
        }
      });
      
      console.log('Clock-out response:', response.data);
      
      // Check if the response contains schedules
      if (response.data && response.data.schedules) {
        console.log('Using schedules from response');
        setSchedules(response.data.schedules);
        
        // Extract unique phases
        const uniquePhases = [...new Set(response.data.schedules.map(task => task.phase))].filter(Boolean);
        setPhases(uniquePhases);
      } else {
        // Immediately fetch updated schedules
        console.log('Fetching schedules separately');
        await fetchSchedules();
      }
    } catch (error) {
      console.error('Error clocking out task:', error);
    } finally {
      setLoading(false);
    }
  };

  // Submit pause (take a break while staying clocked in)
  const submitPause = async () => {
    try {
      setLoading(true);
      setShowPauseModal(false);
      
      // Calculate break end time
      let durationMinutes = parseInt(pauseDetails.duration_minutes, 10);
      
      // For predefined break types, set appropriate durations
      if (pauseDetails.pauseType === 'short_break') {
        durationMinutes = 15;
      } else if (pauseDetails.pauseType === 'long_break') {
        durationMinutes = 45;
      } else if (pauseDetails.pauseType === 'lunch') {
        durationMinutes = 60;
      }
      
      const details = {
        reason: pauseDetails.reason || `Taking a ${pauseDetails.pauseType.replace('_', ' ')}`,
        duration_minutes: durationMinutes,
        is_on_hold: false
      };
      
      console.log('Taking a break:', details);
      
      const response = await axios.post('/api/reschedule/event', {
        task_id: selectedTask.task_id,
        event_type: 'pause',
        timestamp: new Date().toISOString(),
        details: details
      });
      
      console.log('Break response:', response.data);
      
      // Show a toast or notification that the break has been logged
      alert(`Break logged: ${details.reason} for ${details.duration_minutes} minutes`);
    } catch (error) {
      console.error('Error logging break:', error);
      alert(`Error logging break: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };
  
  // Open resource assignments modal
  const openResourceAssignmentsModal = (task) => {
    // Close the main assignments modal if it's open
    setShowResourceAssignmentsModal(false);
    // Set the selected task for the assignment manager
    setSelectedTaskForAssignments(task);
  };
  
  // Handle resource assignments updated
  const handleResourceAssignmentsUpdated = async () => {
    // Refresh resource assignments, employees, and resources
    await Promise.all([
      fetchResourceAssignments(),
      fetchEmployees(),
      fetchResources()
    ]);
  };

  // Submit skip
  const submitSkip = async () => {
    try {
      setLoading(true);
      setShowSkipModal(false);
      
      console.log('Skipping task:', selectedTask.task_id);
      
      const response = await axios.post('/api/reschedule/event', {
        task_id: selectedTask.task_id,
        event_type: 'skip',
        timestamp: new Date().toISOString(),
        details: {
          reason: skipReason || 'Task skipped'
        }
      });
      
      console.log('Skip task response:', response.data);
      
      // Immediately fetch updated schedules
      await fetchSchedules();
      
      // Also fetch task dependencies to update the UI
      await fetchTaskDependencies();
      
      // Log refresh is handled automatically
      
      // Show a success message with rescheduling information
      let message = `Task ${selectedTask.task_name} has been skipped!`;
      
      // Check if any tasks were rescheduled
      if (response.data.rescheduled_tasks && response.data.rescheduled_tasks.length > 0) {
        const rescheduledCount = response.data.rescheduled_tasks.length;
        message += `\n\n${rescheduledCount} dependent task(s) have been rescheduled:`;
        
        // Add details for the first few rescheduled tasks
        const tasksToShow = response.data.rescheduled_tasks.slice(0, 3);
        tasksToShow.forEach(task => {
          const oldStart = new Date(task.original_start).toLocaleTimeString();
          const newStart = new Date(task.new_start).toLocaleTimeString();
          message += `\n- Task ${task.task_id} (${task.name}): ${oldStart} → ${newStart}`;
        });
        
        // If there are more tasks, add a note
        if (rescheduledCount > 3) {
          message += `\n- ... and ${rescheduledCount - 3} more tasks`;
        }
      }
      
      alert(message);
    } catch (error) {
      console.error('Error skipping task:', error);
      alert(`Error skipping task: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Filter tasks based on active phase
  const getFilteredTasks = () => {
    if (activePhase === 'all') {
      return schedules;
    }
    return schedules.filter(task => task.phase === activePhase);
  };
  
  // Get phase statistics
  const getPhaseStats = (phase) => {
    const phaseTasks = schedules.filter(task => task.phase === phase);
    return {
      total: phaseTasks.length,
      completed: phaseTasks.filter(t => t.status === 'Completed').length,
      inProgress: phaseTasks.filter(t => t.status === 'In Progress').length,
      onHold: phaseTasks.filter(t => t.status === 'On Hold' || t.status === 'Paused').length,
      skipped: phaseTasks.filter(t => t.status === 'Skipped').length
    };
  };
  
  // Get phase completion percentage
  const getPhaseCompletion = (phase) => {
    const stats = getPhaseStats(phase);
    return stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;
  };
  
  // Get phase color based on completion
  const getPhaseColor = (phase) => {
    const completion = getPhaseCompletion(phase);
    if (completion >= 80) return 'success';
    if (completion >= 50) return 'info';
    if (completion >= 20) return 'warning';
    return 'danger';
  };
  
  // Calculate overall project statistics
  // Calculate makespan (total schedule duration)
  let earliestStart = null;
  let latestEnd = null;
  
  schedules.forEach(task => {
    const startDate = task.planned_start ? new Date(task.planned_start) : 
                     (task.planned_start_iso ? new Date(task.planned_start_iso) : null);
    const endDate = task.planned_end ? new Date(task.planned_end) : 
                   (task.planned_end_iso ? new Date(task.planned_end_iso) : null);
    
    if (startDate && (!earliestStart || startDate < earliestStart)) {
      earliestStart = startDate;
    }
    
    if (endDate && (!latestEnd || endDate > latestEnd)) {
      latestEnd = endDate;
    }
  });
  
  // Calculate makespan in days
  const makespan = earliestStart && latestEnd ? 
    Math.ceil((latestEnd - earliestStart) / (1000 * 60 * 60 * 24)) : 0;
  
  const projectStats = {
    total: schedules.length,
    completed: schedules.filter(t => t.status === 'Completed').length,
    inProgress: schedules.filter(t => t.status === 'In Progress').length,
    onHold: schedules.filter(t => t.status === 'On Hold' || t.status === 'Paused').length,
    skipped: schedules.filter(t => t.status === 'Skipped').length,
    completionPercentage: schedules.length > 0 
      ? Math.round((schedules.filter(t => t.status === 'Completed').length / schedules.length) * 100) 
      : 0,
    makespan,
    earliestStart,
    latestEnd
  };

  return (
    <div className="dashboard-container">
      {/* Auto-refresh notification */}
      {autoRefresh && (
        <div className="alert alert-info mb-3">
          <div className="d-flex align-items-center">
            <span className="spinner-grow spinner-grow-sm me-2" role="status" aria-hidden="true"></span>
            <div>
              <strong>Auto-refresh enabled:</strong> Data will refresh automatically every 30 seconds.
              <Button 
                variant="link" 
                size="sm" 
                className="p-0 ms-2"
                onClick={() => setAutoRefresh(false)}
              >
                Disable
              </Button>
            </div>
          </div>
        </div>
      )}
      
      {/* Resource Conflicts Card */}
      {(resourceAssignments.employee_conflicts.length > 0 || resourceAssignments.resource_conflicts.length > 0) && (
        showResourceConflicts ? (
        <Card className="mb-4 border-danger">
          <Card.Header className="bg-danger text-white">
            <div className="d-flex justify-content-between align-items-center">
              <h5 className="mb-0">
                <i className="bi bi-exclamation-triangle-fill me-2"></i>
                Resource Conflicts Detected
              </h5>
              <Button 
                variant="outline-light" 
                size="sm"
                onClick={() => setShowResourceConflicts(false)}
              >
                Hide
              </Button>
            </div>
          </Card.Header>
          <Card.Body>
            <Tab.Container defaultActiveKey="employee">
              <Nav variant="tabs" className="mb-3">
                <Nav.Item>
                  <Nav.Link eventKey="employee">
                    Employee Conflicts 
                    <Badge bg="danger" className="ms-2">{resourceAssignments.employee_conflicts.length}</Badge>
                  </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                  <Nav.Link eventKey="resource">
                    Resource Conflicts 
                    <Badge bg="danger" className="ms-2">{resourceAssignments.resource_conflicts.length}</Badge>
                  </Nav.Link>
                </Nav.Item>
              </Nav>
              <Tab.Content>
                <Tab.Pane eventKey="employee">
                  {resourceAssignments.employee_conflicts.length > 0 ? (
                    <div className="table-responsive" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                      <Table striped bordered hover>
                        <thead style={{ position: 'sticky', top: 0, background: 'white', zIndex: 1 }}>
                          <tr>
                            <th>Employee</th>
                            <th>Task 1</th>
                            <th>Task 2</th>
                            <th>Time Conflict</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {resourceAssignments.employee_conflicts.map((conflict, index) => (
                            <tr key={index}>
                              <td>
                                <strong>{conflict.employee_name}</strong>
                              </td>
                              <td>
                                <div>
                                  <strong>Task {conflict.task1_id}:</strong> {conflict.task1_name}
                                </div>
                                <div className="small text-muted">
                                  Status: <Badge bg={
                                    conflict.task1_status === 'Completed' ? 'success' :
                                    conflict.task1_status === 'In Progress' ? 'primary' :
                                    conflict.task1_status === 'Paused' ? 'warning' :
                                    conflict.task1_status === 'On Hold' ? 'danger' :
                                    conflict.task1_status === 'Skipped' ? 'secondary' : 'info'
                                  }>
                                    {conflict.task1_status}
                                  </Badge>
                                </div>
                                <div className="small text-muted">
                                  Priority: <Badge bg={
                                    conflict.task1_priority >= 8 ? 'danger' :
                                    conflict.task1_priority >= 5 ? 'warning' :
                                    conflict.task1_priority >= 3 ? 'info' : 'secondary'
                                  }>
                                    {conflict.task1_priority}
                                  </Badge>
                                </div>
                              </td>
                              <td>
                                <div>
                                  <strong>Task {conflict.task2_id}:</strong> {conflict.task2_name}
                                </div>
                                <div className="small text-muted">
                                  Status: <Badge bg={
                                    conflict.task2_status === 'Completed' ? 'success' :
                                    conflict.task2_status === 'In Progress' ? 'primary' :
                                    conflict.task2_status === 'Paused' ? 'warning' :
                                    conflict.task2_status === 'On Hold' ? 'danger' :
                                    conflict.task2_status === 'Skipped' ? 'secondary' : 'info'
                                  }>
                                    {conflict.task2_status}
                                  </Badge>
                                </div>
                                <div className="small text-muted">
                                  Priority: <Badge bg={
                                    conflict.task2_priority >= 8 ? 'danger' :
                                    conflict.task2_priority >= 5 ? 'warning' :
                                    conflict.task2_priority >= 3 ? 'info' : 'secondary'
                                  }>
                                    {conflict.task2_priority}
                                  </Badge>
                                </div>
                              </td>
                              <td>
                                <div>
                                  <strong>Task 1 Time:</strong>
                                  <div className="small">
                                    {new Date(conflict.task1_start_iso).toLocaleString()} - {new Date(conflict.task1_end_iso).toLocaleString()}
                                  </div>
                                </div>
                                <div className="mt-2">
                                  <strong>Task 2 Time:</strong>
                                  <div className="small">
                                    {new Date(conflict.task2_start_iso).toLocaleString()} - {new Date(conflict.task2_end_iso).toLocaleString()}
                                  </div>
                                </div>
                              </td>
                              <td>
                                <div className="d-grid gap-2">
                                  <Button 
                                    variant="outline-primary" 
                                    size="sm"
                                    onClick={() => handleRescheduleTask(conflict.task1_id, conflict.task1_name)}
                                  >
                                    Reschedule Task 1
                                  </Button>
                                  <Button 
                                    variant="outline-primary" 
                                    size="sm"
                                    onClick={() => handleRescheduleTask(conflict.task2_id, conflict.task2_name)}
                                  >
                                    Reschedule Task 2
                                  </Button>
                                  <Button 
                                    variant="outline-warning" 
                                    size="sm"
                                    onClick={() => handleReassignEmployee(
                                      conflict.employee_id, 
                                      conflict.employee_name, 
                                      conflict.task1_id, 
                                      conflict.task1_name
                                    )}
                                  >
                                    Reassign Employee
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                  ) : (
                    <div className="alert alert-success">
                      <i className="bi bi-check-circle-fill me-2"></i>
                      No employee conflicts detected.
                    </div>
                  )}
                </Tab.Pane>
                <Tab.Pane eventKey="resource">
                  {resourceAssignments.resource_conflicts.length > 0 ? (
                    <div className="table-responsive" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                      <Table striped bordered hover>
                        <thead style={{ position: 'sticky', top: 0, background: 'white', zIndex: 1 }}>
                          <tr>
                            <th>Resource</th>
                            <th>Task 1</th>
                            <th>Task 2</th>
                            <th>Time Conflict</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {resourceAssignments.resource_conflicts.map((conflict, index) => (
                            <tr key={index}>
                              <td>
                                <strong>{conflict.resource_name}</strong>
                              </td>
                              <td>
                                <div>
                                  <strong>Task {conflict.task1_id}:</strong> {conflict.task1_name}
                                </div>
                                <div className="small text-muted">
                                  Status: <Badge bg={
                                    conflict.task1_status === 'Completed' ? 'success' :
                                    conflict.task1_status === 'In Progress' ? 'primary' :
                                    conflict.task1_status === 'Paused' ? 'warning' :
                                    conflict.task1_status === 'On Hold' ? 'danger' :
                                    conflict.task1_status === 'Skipped' ? 'secondary' : 'info'
                                  }>
                                    {conflict.task1_status}
                                  </Badge>
                                </div>
                                <div className="small text-muted">
                                  Priority: <Badge bg={
                                    conflict.task1_priority >= 8 ? 'danger' :
                                    conflict.task1_priority >= 5 ? 'warning' :
                                    conflict.task1_priority >= 3 ? 'info' : 'secondary'
                                  }>
                                    {conflict.task1_priority}
                                  </Badge>
                                </div>
                              </td>
                              <td>
                                <div>
                                  <strong>Task {conflict.task2_id}:</strong> {conflict.task2_name}
                                </div>
                                <div className="small text-muted">
                                  Status: <Badge bg={
                                    conflict.task2_status === 'Completed' ? 'success' :
                                    conflict.task2_status === 'In Progress' ? 'primary' :
                                    conflict.task2_status === 'Paused' ? 'warning' :
                                    conflict.task2_status === 'On Hold' ? 'danger' :
                                    conflict.task2_status === 'Skipped' ? 'secondary' : 'info'
                                  }>
                                    {conflict.task2_status}
                                  </Badge>
                                </div>
                                <div className="small text-muted">
                                  Priority: <Badge bg={
                                    conflict.task2_priority >= 8 ? 'danger' :
                                    conflict.task2_priority >= 5 ? 'warning' :
                                    conflict.task2_priority >= 3 ? 'info' : 'secondary'
                                  }>
                                    {conflict.task2_priority}
                                  </Badge>
                                </div>
                              </td>
                              <td>
                                <div>
                                  <strong>Task 1 Time:</strong>
                                  <div className="small">
                                    {new Date(conflict.task1_start_iso).toLocaleString()} - {new Date(conflict.task1_end_iso).toLocaleString()}
                                  </div>
                                </div>
                                <div className="mt-2">
                                  <strong>Task 2 Time:</strong>
                                  <div className="small">
                                    {new Date(conflict.task2_start_iso).toLocaleString()} - {new Date(conflict.task2_end_iso).toLocaleString()}
                                  </div>
                                </div>
                              </td>
                              <td>
                                <div className="d-grid gap-2">
                                  <Button 
                                    variant="outline-primary" 
                                    size="sm"
                                    onClick={() => handleRescheduleTask(conflict.task1_id, conflict.task1_name)}
                                  >
                                    Reschedule Task 1
                                  </Button>
                                  <Button 
                                    variant="outline-primary" 
                                    size="sm"
                                    onClick={() => handleRescheduleTask(conflict.task2_id, conflict.task2_name)}
                                  >
                                    Reschedule Task 2
                                  </Button>
                                  <Button 
                                    variant="outline-warning" 
                                    size="sm"
                                    onClick={() => handleReassignResource(
                                      conflict.resource_id, 
                                      conflict.resource_name, 
                                      conflict.task1_id, 
                                      conflict.task1_name
                                    )}
                                  >
                                    Reassign Resource
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                  ) : (
                    <div className="alert alert-success">
                      <i className="bi bi-check-circle-fill me-2"></i>
                      No resource conflicts detected.
                    </div>
                  )}
                </Tab.Pane>
              </Tab.Content>
            </Tab.Container>
          </Card.Body>
        </Card>
      ) : (
        <div className="mb-4">
          <Button 
            variant="danger" 
            onClick={() => setShowResourceConflicts(true)}
            className="w-100"
          >
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            Show Resource Conflicts 
            <Badge bg="light" text="danger" className="ms-2">
              {resourceAssignments.employee_conflicts.length + resourceAssignments.resource_conflicts.length}
            </Badge>
          </Button>
        </div>
      )
      )}
      
      {/* Main Dashboard Card */}
      <Card className="mb-4">
        <Card.Header>
          <div className="d-flex justify-content-between align-items-center">
            <h5 className="mb-0">Schedule Dashboard</h5>
            <div>
              <div className="d-flex align-items-center">
                <div className="d-flex align-items-center me-3">
                  <Form.Check 
                    type="switch"
                    id="auto-refresh-switch"
                    label="Auto-refresh"
                    checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                    className="me-3"
                  />
                  {(resourceAssignments.employee_conflicts.length > 0 || resourceAssignments.resource_conflicts.length > 0) && !showResourceConflicts && (
                    <Button 
                      variant="outline-danger" 
                      size="sm"
                      onClick={() => setShowResourceConflicts(true)}
                      className="me-2"
                    >
                      <i className="bi bi-exclamation-triangle-fill me-1"></i>
                      Conflicts 
                      <Badge bg="danger" className="ms-1">
                        {resourceAssignments.employee_conflicts.length + resourceAssignments.resource_conflicts.length}
                      </Badge>
                    </Button>
                  )}
                  <Button 
                    variant="outline-info" 
                    size="sm"
                    onClick={() => setShowResourceAssignmentsModal(true)}
                    className="me-2"
                  >
                    <i className="bi bi-people-fill me-1"></i>
                    Resource Assignments
                  </Button>
                </div>
                <Button 
                  variant="outline-secondary" 
                  size="sm"
                  onClick={() => {
                    fetchSchedules(true);
                    fetchTaskDependencies(true);
                    fetchResourceAssignments(true);
                  }}
                  title="Refresh data"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                      Loading...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-arrow-repeat"></i> Refresh
                    </>
                  )}
                </Button>
                  
                  {/* Full Reschedule Button */}
                  <FullRescheduleButton 
                    onRescheduleComplete={() => {
                      fetchSchedules(true);
                      fetchTaskDependencies(true);
                      fetchResourceAssignments(true);
                    }}
                  />
              </div>
            </div>
          </div>
          <div className="row">
            <div className="col-md-8">
              <div className="d-flex justify-content-between align-items-center">
                <h4>Project Progress</h4>
                <div className="makespan-info">
                  <span className="badge bg-info p-2">
                    <i className="bi bi-calendar-range me-1"></i>
                    Makespan: {projectStats.makespan} days
                  </span>
                  {projectStats.earliestStart && projectStats.latestEnd && (
                    <span className="ms-2 text-muted small">
                      ({new Date(projectStats.earliestStart).toLocaleDateString()} - {new Date(projectStats.latestEnd).toLocaleDateString()})
                    </span>
                  )}
                </div>
              </div>
              <div className="progress mb-3" style={{ height: '25px' }}>
                <div 
                  className="progress-bar bg-success" 
                  role="progressbar" 
                  style={{ width: `${projectStats.completionPercentage}%` }}
                  aria-valuenow={projectStats.completionPercentage} 
                  aria-valuemin="0" 
                  aria-valuemax="100"
                >
                  {projectStats.completionPercentage}% Complete
                </div>
              </div>
              <div className="d-flex justify-content-between">
                <div className="text-center">
                  <h5>{projectStats.total}</h5>
                  <small>Total Tasks</small>
                </div>
                <div className="text-center">
                  <h5 className="text-success">{projectStats.completed}</h5>
                  <small>Completed</small>
                </div>
                <div className="text-center">
                  <h5 className="text-primary">{projectStats.inProgress}</h5>
                  <small>In Progress</small>
                </div>
                <div className="text-center">
                  <h5 className="text-warning">{projectStats.onHold}</h5>
                  <small>On Hold/Paused</small>
                </div>
                <div className="text-center">
                  <h5 className="text-secondary">{projectStats.skipped}</h5>
                  <small>Skipped</small>
                </div>
              </div>
            </div>
            <div className="col-md-4 d-flex align-items-center justify-content-end">
              <div>
                {/* Dropdown removed */}
                <Button 
                  variant="primary" 
                  onClick={runInitialSchedule}
                  disabled={loading}
                  className="w-100"
                >
                  {loading ? 'Running Scheduler...' : 'Run Initial Schedule'}
                </Button>
              </div>
            </div>
          </div>
        </Card.Header>
        <Card.Body>
          {loading ? (
            <p>Loading schedules...</p>
          ) : (
            <>
              {/* Active Task Timer */}
              <ActiveTaskTimer tasks={schedules} />
              
              {/* Full-width layout */}
              <div className="row">
                {/* Full-width column - Task Table */}
                <div className="col-12">
                  {/* Phase Overview Cards */}
                  <div className="row mb-4">
                    <div className="col-md-3">
                      <Card 
                        className={`text-center ${activePhase === 'all' ? 'bg-light border-primary' : ''}`}
                        onClick={() => setActivePhase('all')}
                        style={{ cursor: 'pointer' }}
                      >
                        <Card.Body>
                          <h5>All Phases</h5>
                          <div className="d-flex justify-content-around">
                            <div>
                              <h3>{schedules.length}</h3>
                              <small>Tasks</small>
                            </div>
                            <div>
                              <h3>{schedules.filter(t => t.status === 'Completed').length}</h3>
                              <small>Completed</small>
                            </div>
                          </div>
                        </Card.Body>
                      </Card>
                    </div>
                    
                    {phases.map(phase => {
                      const stats = getPhaseStats(phase);
                      const completion = getPhaseCompletion(phase);
                      const color = getPhaseColor(phase);
                      
                      return (
                        <div className="col-md-3" key={phase}>
                          <Card 
                            className={`text-center ${activePhase === phase ? 'bg-light border-primary' : ''}`}
                            onClick={() => setActivePhase(phase)}
                            style={{ cursor: 'pointer' }}
                          >
                            <Card.Body>
                              <h5>
                                {phase} 
                                <Badge bg={color} className="ms-2">{completion}%</Badge>
                              </h5>
                              <div className="d-flex justify-content-around">
                                <div>
                                  <h3>{stats.total}</h3>
                                  <small>Tasks</small>
                                </div>
                                <div>
                                  <h3>{stats.completed}</h3>
                                  <small>Completed</small>
                                </div>
                              </div>
                            </Card.Body>
                          </Card>
                        </div>
                      );
                    })}
                  </div>
                  
                  {/* Tasks Table */}
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h5>
                      {activePhase === 'all' ? 'All Tasks' : `Phase: ${activePhase}`}
                      <span className="ms-2 text-muted">({getFilteredTasks().length} tasks)</span>
                    </h5>
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
                        variant="outline-secondary" 
                        size="sm"
                        onClick={() => fetchTaskDependencies()}
                        title="Refresh dependencies"
                      >
                        <i className="bi bi-arrow-repeat"></i>
                      </Button>
                    </div>
                  </div>
                  <div className="table-responsive">
                    <Table striped bordered hover className="task-table w-100" style={{ minWidth: '100%' }}>
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Task Name</th>
                          <th>Phase</th>
                          {showDependencies && <th>Dependencies</th>}
                          <th>Planned Start</th>
                          <th>Planned End</th>
                          <th>Actual Start</th>
                          <th>Actual End</th>
                          <th>Status</th>
                          <th>Priority</th>
                          <th>Progress</th>
                        </tr>
                      </thead>
                      <tbody>
                        {getFilteredTasks().map(task => (
                          <tr key={task.task_id}>
                            <td>{task.task_id}</td>
                            <td>
                              <div className="d-flex align-items-center">
                                <div>
                                  {task.task_name}
                                  <div className="mt-1">
                                    {showDependencies && taskDependencies[task.task_id] && taskDependencies[task.task_id].length > 0 && (
                                      <Button 
                                        variant="link" 
                                        size="sm" 
                                        className="p-0 me-2"
                                        onClick={() => showDependencyDetails(task)}
                                        title="View dependency details"
                                      >
                                        <i className="bi bi-diagram-3"></i>
                                      </Button>
                                    )}
                                    <Button
                                      variant="link"
                                      size="sm"
                                      className="p-0"
                                      onClick={() => openResourceAssignmentsModal(task)}
                                      title="Manage resource assignments"
                                    >
                                      <i className="bi bi-people"></i>
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td>{task.phase || 'N/A'}</td>
                            {showDependencies && (
                              <td>
                                {taskDependencies[task.task_id] && taskDependencies[task.task_id].length > 0 ? (
                                  <div>
                                    {taskDependencies[task.task_id].map((dep, index) => (
                                      <Badge 
                                        key={index} 
                                        bg={
                                          getTaskStatusById(dep.taskId) === 'Completed' ? 'success' : 
                                          getTaskStatusById(dep.taskId) === 'Skipped' ? 'secondary' : 
                                          'warning'
                                        }
                                        className="me-1"
                                        title={`Depends on Task ${dep.taskId}: ${getTaskNameById(dep.taskId)}`}
                                      >
                                        {dep.taskId}
                                      </Badge>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="text-muted">None</span>
                                )}
                              </td>
                            )}
                            <td>
                              {task.planned_start}
                              {task.planned_start_iso && (
                                <div className="text-muted small">
                                  {new Date(task.planned_start_iso).toLocaleTimeString()}
                                </div>
                              )}
                            </td>
                            <td>
                              {task.planned_end}
                              {task.planned_end_iso && (
                                <div className="text-muted small">
                                  {new Date(task.planned_end_iso).toLocaleTimeString()}
                                </div>
                              )}
                            </td>
                            <td>
                              {task.actual_start ? (
                                <div>
                                  <span className="text-primary">
                                    {task.actual_start}
                                  </span>
                                  {task.actual_start_iso && (
                                    <div className="text-muted small">
                                      {new Date(task.actual_start_iso).toLocaleTimeString()}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <span className="text-muted">Not started</span>
                              )}
                            </td>
                            <td>
                              {task.actual_end ? (
                                <div>
                                  <span className="text-success">
                                    {task.actual_end}
                                  </span>
                                  {task.actual_end_iso && (
                                    <div className="text-muted small">
                                      {new Date(task.actual_end_iso).toLocaleTimeString()}
                                    </div>
                                  )}
                                  {task.delay_or_ahead && (
                                    <OverlayTrigger
                                      placement="top"
                                      overlay={
                                        <Tooltip>
                                          {task.delay_or_ahead.startsWith('+') 
                                            ? `Completed ${task.delay_or_ahead.substring(1)} later than planned` 
                                            : `Completed ${task.delay_or_ahead.substring(1)} earlier than planned`}
                                        </Tooltip>
                                      }
                                    >
                                      <Badge 
                                        bg={task.delay_or_ahead.startsWith('+') ? 'warning' : 'info'} 
                                        className="ms-2"
                                      >
                                        {task.delay_or_ahead}
                                      </Badge>
                                    </OverlayTrigger>
                                  )}
                                </div>
                              ) : (
                                <span className="text-muted">Not completed</span>
                              )}
                            </td>
                            <td>
                              <Badge bg={
                                task.status === 'Completed' ? 'success' :
                                task.status === 'In Progress' ? 'primary' :
                                task.status === 'Paused' ? 'warning' :
                                task.status === 'On Hold' ? 'danger' :
                                task.status === 'Skipped' ? 'secondary' : 'info'
                              }>
                                {task.status}
                              </Badge>
                            </td>
                            <td>
                              <Badge bg={
                                task.priority >= 8 ? 'danger' :
                                task.priority >= 5 ? 'warning' :
                                task.priority >= 3 ? 'info' : 'secondary'
                              }>
                                {task.priority}
                              </Badge>
                            </td>
                            <td>
                              <TaskProgressBar 
                                task={task} 
                                onPause={handlePause}
                                onComplete={handleComplete}
                                onSkip={handleSkip}
                                onClockIn={handleClockIn}
                                onClockOut={handleClockOut}
                                onEdit={handleEditTask}
                                dependenciesMet={areDependenciesMet(task)}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </div>
                </div>
              </div>
              

            </>
          )}
        </Card.Body>
      </Card>

      {/* Pause Modal */}
      <Modal show={showPauseModal} onHide={() => setShowPauseModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Take a Break (Stay Clocked In)</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedTask && (
            <Form>
              <div className="alert alert-info mb-3">
                <i className="bi bi-info-circle me-2"></i>
                Taking a break keeps you clocked in but logs your break time. The timer will continue running.
              </div>
              
              <Form.Group className="mb-3">
                <Form.Label>Task</Form.Label>
                <Form.Control type="text" value={selectedTask.task_name} disabled />
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Label>Break Type</Form.Label>
                <Form.Select 
                  value={pauseDetails.pauseType}
                  onChange={(e) => setPauseDetails({...pauseDetails, pauseType: e.target.value})}
                >
                  <option value="short_break">Short Break (15 min)</option>
                  <option value="long_break">Long Break (45 min)</option>
                  <option value="lunch">Lunch (60 min)</option>
                  <option value="custom">Custom Duration</option>
                </Form.Select>
              </Form.Group>
              
              {pauseDetails.pauseType === 'custom' && (
                <Form.Group className="mb-3">
                  <Form.Label>Duration (minutes)</Form.Label>
                  <Form.Control 
                    type="number" 
                    min="1" 
                    max="480"
                    value={pauseDetails.duration_minutes}
                    onChange={(e) => setPauseDetails({...pauseDetails, duration_minutes: e.target.value})}
                  />
                </Form.Group>
              )}
              
              <Form.Group className="mb-3">
                <Form.Label>Reason (optional)</Form.Label>
                <Form.Control 
                  as="textarea" 
                  rows={2}
                  placeholder="Why are you taking a break?"
                  value={pauseDetails.reason}
                  onChange={(e) => setPauseDetails({...pauseDetails, reason: e.target.value})}
                />
              </Form.Group>
            </Form>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowPauseModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submitPause}>
            Log Break
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Skip Modal */}
      <Modal show={showSkipModal} onHide={() => setShowSkipModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Skip Task</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedTask && (
            <Form>
              <div className="alert alert-warning mb-3">
                <i className="bi bi-exclamation-triangle-fill me-2"></i>
                Skipping a task will mark it as skipped and reschedule any dependent tasks.
              </div>
              
              <Form.Group className="mb-3">
                <Form.Label>Task</Form.Label>
                <Form.Control type="text" value={selectedTask.task_name} disabled />
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Label>Reason for Skipping</Form.Label>
                <Form.Control 
                  as="textarea" 
                  rows={3}
                  placeholder="Why is this task being skipped?"
                  value={skipReason}
                  onChange={(e) => setSkipReason(e.target.value)}
                  required
                />
              </Form.Group>
            </Form>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowSkipModal(false)}>
            Cancel
          </Button>
          <Button variant="warning" onClick={submitSkip}>
            Skip Task
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Clock Out Modal */}
      <Modal show={showClockOutModal} onHide={() => setShowClockOutModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Clock Out</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedTask && (
            <Form>
              <div className="alert alert-info mb-3">
                <i className="bi bi-info-circle me-2"></i>
                Clocking out will stop the timer for this task.
              </div>
              
              <Form.Group className="mb-3">
                <Form.Label>Task</Form.Label>
                <Form.Control type="text" value={selectedTask.task_name} disabled />
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Label>Completion Percentage</Form.Label>
                <div className="d-flex align-items-center">
                  <Form.Range
                    min="0"
                    max="100"
                    step="5"
                    value={clockOutDetails.completed_percentage}
                    onChange={(e) => setClockOutDetails({
                      ...clockOutDetails, 
                      completed_percentage: parseInt(e.target.value, 10)
                    })}
                    className="me-2 flex-grow-1"
                  />
                  <span className="badge bg-primary">{clockOutDetails.completed_percentage}%</span>
                </div>
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Label>Reason</Form.Label>
                <Form.Control 
                  as="textarea" 
                  rows={2}
                  placeholder="Why are you clocking out?"
                  value={clockOutDetails.reason}
                  onChange={(e) => setClockOutDetails({...clockOutDetails, reason: e.target.value})}
                />
              </Form.Group>
              
              <Form.Group className="mb-3">
                <Form.Check 
                  type="checkbox"
                  id="carry-over-check"
                  label="Carry over remaining work to next day"
                  checked={clockOutDetails.carry_over}
                  onChange={(e) => setClockOutDetails({...clockOutDetails, carry_over: e.target.checked})}
                />
              </Form.Group>
            </Form>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowClockOutModal(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submitClockOut}>
            Clock Out
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Dependency Modal */}
      <Modal 
        show={showDependencyModal} 
        onHide={() => setShowDependencyModal(false)}
        size="lg"
      >
        <Modal.Header closeButton>
          <Modal.Title>Task Dependencies</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {selectedTask && (
            <div>
              <h5>Task: {selectedTask.task_id} - {selectedTask.task_name}</h5>
              
              <div className="row mt-4">
                <div className="col-md-6">
                  <h6>This task depends on:</h6>
                  {taskDependencies[selectedTask.task_id] && taskDependencies[selectedTask.task_id].length > 0 ? (
                    <ul className="list-group">
                      {taskDependencies[selectedTask.task_id].map((dep, index) => (
                        <li key={index} className="list-group-item">
                          <div className="d-flex justify-content-between align-items-center">
                            <div>
                              <strong>Task {dep.taskId}:</strong> {getTaskNameById(dep.taskId)}
                            </div>
                            <Badge bg={
                              getTaskStatusById(dep.taskId) === 'Completed' ? 'success' :
                              getTaskStatusById(dep.taskId) === 'In Progress' ? 'primary' :
                              getTaskStatusById(dep.taskId) === 'Paused' ? 'warning' :
                              getTaskStatusById(dep.taskId) === 'On Hold' ? 'danger' :
                              getTaskStatusById(dep.taskId) === 'Skipped' ? 'secondary' : 'info'
                            }>
                              {getTaskStatusById(dep.taskId)}
                            </Badge>
                          </div>
                          <div className="small text-muted mt-1">
                            <strong>Type:</strong> {dep.type || 'Finish-to-Start'} 
                            {dep.lagHours > 0 && ` (Lag: ${dep.lagHours} hours)`}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted">This task has no dependencies.</p>
                  )}
                </div>
                
                <div className="col-md-6">
                  <h6>Tasks that depend on this task:</h6>
                  {Object.entries(taskDependencies).some(([taskId, deps]) => 
                    deps.some(dep => dep.taskId === selectedTask.task_id)
                  ) ? (
                    <ul className="list-group">
                      {Object.entries(taskDependencies)
                        .filter(([taskId, deps]) => deps.some(dep => dep.taskId === selectedTask.task_id))
                        .map(([taskId, deps]) => {
                          const task = schedules.find(t => t.task_id === parseInt(taskId));
                          if (!task) return null;
                          
                          const relevantDep = deps.find(dep => dep.taskId === selectedTask.task_id);
                          
                          return (
                            <li key={taskId} className="list-group-item">
                              <div className="d-flex justify-content-between align-items-center">
                                <div>
                                  <strong>Task {taskId}:</strong> {task.task_name}
                                </div>
                                <Badge bg={
                                  task.status === 'Completed' ? 'success' :
                                  task.status === 'In Progress' ? 'primary' :
                                  task.status === 'Paused' ? 'warning' :
                                  task.status === 'On Hold' ? 'danger' :
                                  task.status === 'Skipped' ? 'secondary' : 'info'
                                }>
                                  {task.status}
                                </Badge>
                              </div>
                              <div className="small text-muted mt-1">
                                <strong>Type:</strong> {relevantDep.type || 'Finish-to-Start'} 
                                {relevantDep.lagHours > 0 && ` (Lag: ${relevantDep.lagHours} hours)`}
                              </div>
                            </li>
                          );
                        })}
                    </ul>
                  ) : (
                    <p className="text-muted">No tasks depend on this task.</p>
                  )}
                </div>
              </div>
              
              <div className="mt-4">
                <h6>Dependency Status:</h6>
                <ul className="list-group">
                  {!areDependenciesMet(selectedTask) && (
                    <li className="list-group-item list-group-item-danger">
                      <i className="bi bi-x-circle-fill me-2"></i>
                      This task has unmet dependencies. It cannot be started until all dependencies are completed or skipped.
                    </li>
                  )}
                  {areDependenciesMet(selectedTask) && (
                    <li className="list-group-item list-group-item-success">
                      <i className="bi bi-check-circle-fill me-2"></i>
                      All dependencies for this task are completed or skipped. The task can be started.
                    </li>
                  )}
                  {taskDependencies[selectedTask.task_id] && taskDependencies[selectedTask.task_id].some(dep => 
                    getTaskStatusById(dep.taskId) === 'On Hold' || 
                    getTaskStatusById(dep.taskId) === 'Paused' || 
                    getTaskStatusById(dep.taskId) === 'Delayed'
                  ) && (
                    <li className="list-group-item list-group-item-warning">
                      <i className="bi bi-arrow-up-circle-fill me-2"></i>
                      This task depends on tasks that are delayed or on hold.
                    </li>
                  )}
                  {Object.entries(taskDependencies).some(([taskId, deps]) => 
                    deps.some(dep => dep.taskId === selectedTask.task_id) &&
                    schedules.find(t => t.task_id === parseInt(taskId))?.priority >= 8
                  ) && (
                    <li className="list-group-item list-group-item-danger">
                      <i className="bi bi-arrow-down-circle-fill me-2"></i>
                      High-priority tasks depend on this task.
                    </li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDependencyModal(false)}>
            Close
          </Button>
        </Modal.Footer>
      </Modal>

      {/* Resource Assignments Modal */}
      <Modal 
        show={showResourceAssignmentsModal} 
        onHide={() => setShowResourceAssignmentsModal(false)}
        size="xl"
      >
        <Modal.Header closeButton>
          <Modal.Title>Resource Assignments</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Tab.Container defaultActiveKey="employee">
            <Nav variant="tabs" className="mb-3">
              <Nav.Item>
                <Nav.Link eventKey="employee">
                  Employee Assignments 
                  <Badge bg="primary" className="ms-2">{resourceAssignments.employee_assignments.length}</Badge>
                </Nav.Link>
              </Nav.Item>
              <Nav.Item>
                <Nav.Link eventKey="resource">
                  Resource Assignments 
                  <Badge bg="info" className="ms-2">{resourceAssignments.resource_assignments.length}</Badge>
                </Nav.Link>
              </Nav.Item>
            </Nav>
            <Tab.Content>
              <Tab.Pane eventKey="employee">
                {resourceAssignments.employee_assignments.length > 0 ? (
                  <div className="table-responsive">
                    <Table striped bordered hover>
                      <thead>
                        <tr>
                          <th>Employee</th>
                          <th>Task</th>
                          <th>Planned Time</th>
                          <th>Actual Time</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {resourceAssignments.employee_assignments.map((assignment, index) => (
                          <tr key={index}>
                            <td>
                              <strong>{assignment.employee_name}</strong>
                              <div className="small text-muted">ID: {assignment.employee_id}</div>
                            </td>
                            <td>
                              <div>
                                <strong>Task {assignment.task_id}:</strong> {assignment.task_name}
                              </div>
                              <div className="small text-muted">
                                Phase: {assignment.phase || 'N/A'}
                              </div>
                              <div className="small text-muted">
                                Priority: <Badge bg={
                                  assignment.priority >= 8 ? 'danger' :
                                  assignment.priority >= 5 ? 'warning' :
                                  assignment.priority >= 3 ? 'info' : 'secondary'
                                }>
                                  {assignment.priority}
                                </Badge>
                              </div>
                            </td>
                            <td>
                              <div>
                                <strong>Start:</strong> {new Date(assignment.planned_start_iso).toLocaleString()}
                              </div>
                              <div>
                                <strong>End:</strong> {new Date(assignment.planned_end_iso).toLocaleString()}
                              </div>
                            </td>
                            <td>
                              {assignment.actual_start ? (
                                <div>
                                  <strong>Start:</strong> {new Date(assignment.actual_start_iso).toLocaleString()}
                                </div>
                              ) : (
                                <div className="text-muted">Not started</div>
                              )}
                              {assignment.actual_end ? (
                                <div>
                                  <strong>End:</strong> {new Date(assignment.actual_end_iso).toLocaleString()}
                                </div>
                              ) : (
                                <div className="text-muted">Not completed</div>
                              )}
                            </td>
                            <td>
                              <Badge bg={
                                assignment.status === 'Completed' ? 'success' :
                                assignment.status === 'In Progress' ? 'primary' :
                                assignment.status === 'Paused' ? 'warning' :
                                assignment.status === 'On Hold' ? 'danger' :
                                assignment.status === 'Skipped' ? 'secondary' : 'info'
                              }>
                                {assignment.status}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </div>
                ) : (
                  <div className="alert alert-info">
                    <i className="bi bi-info-circle-fill me-2"></i>
                    No employee assignments found.
                  </div>
                )}
              </Tab.Pane>
              <Tab.Pane eventKey="resource">
                {resourceAssignments.resource_assignments.length > 0 ? (
                  <div className="table-responsive">
                    <Table striped bordered hover>
                      <thead>
                        <tr>
                          <th>Resource</th>
                          <th>Task</th>
                          <th>Planned Time</th>
                          <th>Actual Time</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {resourceAssignments.resource_assignments.map((assignment, index) => (
                          <tr key={index}>
                            <td>
                              <strong>{assignment.resource_name}</strong>
                              <div className="small text-muted">ID: {assignment.resource_id}</div>
                            </td>
                            <td>
                              <div>
                                <strong>Task {assignment.task_id}:</strong> {assignment.task_name}
                              </div>
                              <div className="small text-muted">
                                Phase: {assignment.phase || 'N/A'}
                              </div>
                              <div className="small text-muted">
                                Priority: <Badge bg={
                                  assignment.priority >= 8 ? 'danger' :
                                  assignment.priority >= 5 ? 'warning' :
                                  assignment.priority >= 3 ? 'info' : 'secondary'
                                }>
                                  {assignment.priority}
                                </Badge>
                              </div>
                            </td>
                            <td>
                              <div>
                                <strong>Start:</strong> {new Date(assignment.planned_start_iso).toLocaleString()}
                              </div>
                              <div>
                                <strong>End:</strong> {new Date(assignment.planned_end_iso).toLocaleString()}
                              </div>
                            </td>
                            <td>
                              {assignment.actual_start ? (
                                <div>
                                  <strong>Start:</strong> {new Date(assignment.actual_start_iso).toLocaleString()}
                                </div>
                              ) : (
                                <div className="text-muted">Not started</div>
                              )}
                              {assignment.actual_end ? (
                                <div>
                                  <strong>End:</strong> {new Date(assignment.actual_end_iso).toLocaleString()}
                                </div>
                              ) : (
                                <div className="text-muted">Not completed</div>
                              )}
                            </td>
                            <td>
                              <Badge bg={
                                assignment.status === 'Completed' ? 'success' :
                                assignment.status === 'In Progress' ? 'primary' :
                                assignment.status === 'Paused' ? 'warning' :
                                assignment.status === 'On Hold' ? 'danger' :
                                assignment.status === 'Skipped' ? 'secondary' : 'info'
                              }>
                                {assignment.status}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </div>
                ) : (
                  <div className="alert alert-info">
                    <i className="bi bi-info-circle-fill me-2"></i>
                    No resource assignments found.
                  </div>
                )}
              </Tab.Pane>
            </Tab.Content>
          </Tab.Container>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowResourceAssignmentsModal(false)}>
            Close
          </Button>
          <Button variant="primary" onClick={() => fetchResourceAssignments(true)}>
            Refresh Data
          </Button>
        </Modal.Footer>
      </Modal>
      
      {/* Resource Assignment Manager */}
      <ResourceAssignmentManager
        show={selectedTaskForAssignments !== null}
        onHide={() => {
          setSelectedTaskForAssignments(null);
        }}
        task={selectedTaskForAssignments}
        employees={employees}
        resources={resources}
        currentAssignments={resourceAssignments}
        onAssignmentsUpdated={handleResourceAssignmentsUpdated}
      />
      
      {/* Task Edit Modal */}
      <TaskEditModal
        show={showEditTaskModal}
        onHide={() => setShowEditTaskModal(false)}
        task={selectedTask}
        allTasks={tasks}
        onTaskUpdated={() => {
          fetchData();
          setShowEditTaskModal(false);
        }}
      />
    </div>
  );
}

export default Dashboard;