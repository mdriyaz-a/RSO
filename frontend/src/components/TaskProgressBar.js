import React from 'react';
import { OverlayTrigger, Tooltip } from 'react-bootstrap';
import TaskTimer from './TaskTimer';

function TaskProgressBar({ task, onPause, onComplete, onSkip, onClockIn, onClockOut, onEdit, dependenciesMet = true }) {
  // Calculate progress based on task status and times
  const calculateProgress = () => {
    if (task.status === 'Completed') {
      return 100;
    }
    
    if (task.status === 'Skipped') {
      return 0;
    }
    
    const now = new Date();
    const start = task.planned_start ? new Date(task.planned_start) : null;
    const end = task.planned_end ? new Date(task.planned_end) : null;
    
    if (!start || !end) {
      return 0;
    }
    
    if (now < start) {
      return 0;
    }
    
    if (now > end) {
      return 100;
    }
    
    const totalDuration = end - start;
    const elapsed = now - start;
    return Math.min(100, Math.round((elapsed / totalDuration) * 100));
  };

  const progress = calculateProgress();
  
  // Determine color based on status
  // Get progress bar CSS class based on status
  const getStatusClass = () => {
    switch (task.status) {
      case 'Completed':
        return 'status-completed';
      case 'In Progress':
        return 'status-in-progress';
      case 'Paused':
        return 'status-paused';
      case 'On Hold':
        return 'status-on-hold';
      case 'Skipped':
        return 'status-skipped';
      default:
        return 'status-in-progress';
    }
  };

  // Check if task is currently clocked in
  const isActivelyWorking = task.status === 'In Progress' && (task.actual_start || task.actual_start_iso) && !(task.actual_end || task.actual_end_iso);
  
  // Force re-render every second to update the timer
  const [, forceUpdate] = React.useState(0);
  React.useEffect(() => {
    if (isActivelyWorking) {
      const interval = setInterval(() => {
        forceUpdate(prev => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [isActivelyWorking]);
  
  // Debug information
  console.log(`Task ${task.task_id} (${task.task_name}) status:`, {
    status: task.status,
    actual_start: task.actual_start,
    actual_start_iso: task.actual_start_iso,
    actual_end: task.actual_end,
    actual_end_iso: task.actual_end_iso,
    isActivelyWorking
  });

  return (
    <div className="d-flex align-items-center">
      <div className="task-progress-bar me-2" style={{ flex: 1 }}>
        {/* Background text (always visible) */}
        <div className="task-progress-text d-flex align-items-center justify-content-between">
          <div className="d-flex align-items-center flex-wrap" style={{ maxWidth: '85%' }}>
            <span className="fw-bold">{task.status}</span>
            <span className="ms-1">- {task.task_name}</span>
          </div>
          <span className="task-progress-percentage">{progress}%</span>
        </div>
        
        {/* Progress fill */}
        <div 
          className={`task-progress-fill ${getStatusClass()}`}
          style={{ width: `${progress}%` }}
        >
        </div>
        
        {/* Dependency warning badge */}
        {!dependenciesMet && (
          <span className="ms-2 badge bg-warning text-dark" style={{ 
            position: 'absolute',
            right: '50px',
            top: '50%',
            transform: 'translateY(-50%)',
            whiteSpace: 'nowrap', 
            display: 'inline-block',
            padding: '0.4em 0.6em',
            fontSize: '0.85rem',
            fontWeight: 'normal',
            zIndex: 5
          }}>
            <i className="bi bi-lock me-1"></i> Waiting for dependencies
          </span>
        )}
        
        {/* Active timer */}
        {isActivelyWorking && (
          <div style={{ 
            position: 'absolute', 
            right: '16px', 
            top: '50%', 
            transform: 'translateY(-50%)',
            zIndex: 5
          }}>
            <TaskTimer task={task} />
          </div>
        )}
      </div>
      
      <div className="d-flex task-action-buttons">
        {/* Clock In Button */}
        <OverlayTrigger
          placement="top"
          overlay={<Tooltip>Clock In</Tooltip>}
        >
          <button 
            className="btn btn-sm btn-outline-primary task-action-btn" 
            onClick={() => onClockIn(task)}
            disabled={
              task.status === 'Completed' || 
              task.status === 'Skipped' || 
              isActivelyWorking ||
              !dependenciesMet
            }
          >
            <i className="bi bi-box-arrow-in-right"></i>
          </button>
        </OverlayTrigger>
        
        {/* Clock Out Button */}
        <OverlayTrigger
          placement="top"
          overlay={<Tooltip>Clock Out</Tooltip>}
        >
          <button 
            className="btn btn-sm btn-outline-secondary task-action-btn" 
            onClick={() => onClockOut(task)}
            disabled={
              task.status === 'Completed' || 
              task.status === 'Skipped' || 
              !isActivelyWorking
            }
          >
            <i className="bi bi-box-arrow-right"></i>
          </button>
        </OverlayTrigger>
        
        {/* Pause Button */}
        <OverlayTrigger
          placement="top"
          overlay={<Tooltip>Take a Break (Stay Clocked In)</Tooltip>}
        >
          <button 
            className="btn btn-sm btn-outline-warning task-action-btn" 
            onClick={() => onPause(task)}
            disabled={
              task.status === 'Completed' || 
              task.status === 'Skipped' || 
              !isActivelyWorking
            }
          >
            <i className="bi bi-cup-hot"></i>
          </button>
        </OverlayTrigger>
        
        {/* Complete Button */}
        <OverlayTrigger
          placement="top"
          overlay={<Tooltip>
            {!dependenciesMet ? 'Cannot complete: Dependencies not met' : 'Complete'}
          </Tooltip>}
        >
          <button 
            className="btn btn-sm btn-outline-success task-action-btn" 
            onClick={() => onComplete(task)}
            disabled={
              task.status === 'Completed' || 
              task.status === 'Skipped' || 
              !dependenciesMet
            }
          >
            <i className="bi bi-check-lg"></i>
          </button>
        </OverlayTrigger>
        
        {/* Skip Button */}
        <OverlayTrigger
          placement="top"
          overlay={<Tooltip>Skip</Tooltip>}
        >
          <button 
            className="btn btn-sm btn-outline-danger task-action-btn" 
            onClick={() => onSkip(task)}
            disabled={task.status === 'Completed' || task.status === 'Skipped'}
          >
            <i className="bi bi-x-lg"></i>
          </button>
        </OverlayTrigger>
        
        {/* Edit Button */}
        <OverlayTrigger
          placement="top"
          overlay={<Tooltip>
            {task.status === 'Completed' || task.status === 'Skipped' 
              ? 'Cannot edit: Task is already completed or skipped' 
              : 'Edit Task'}
          </Tooltip>}
        >
          <button 
            className="btn btn-sm btn-outline-info task-action-btn" 
            onClick={() => onEdit(task)}
            disabled={task.status === 'Completed' || task.status === 'Skipped'}
          >
            <i className="bi bi-pencil"></i>
          </button>
        </OverlayTrigger>
      </div>
    </div>
  );
}

export default TaskProgressBar;