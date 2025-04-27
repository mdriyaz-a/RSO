import React, { useState, useEffect } from 'react';
import { Card, Badge } from 'react-bootstrap';

function ActiveTaskTimer({ tasks }) {
  const [activeTask, setActiveTask] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  // Find active task and set up timer
  useEffect(() => {
    // Find the first task that is actively being worked on
    const activeTask = tasks.find(task => 
      task.status === 'In Progress' && 
      (task.actual_start || task.actual_start_iso) && 
      !(task.actual_end || task.actual_end_iso)
    );
    
    setActiveTask(activeTask);
    
    if (activeTask) {
      console.log('ActiveTaskTimer - Found active task:', activeTask);
      
      // Get start time
      let startTime;
      if (activeTask.actual_start_iso) {
        startTime = new Date(activeTask.actual_start_iso);
      } else if (activeTask.actual_start) {
        if (activeTask.actual_start instanceof Date) {
          startTime = activeTask.actual_start;
        } else if (typeof activeTask.actual_start === 'string') {
          startTime = new Date(activeTask.actual_start);
        }
      }
      
      if (startTime && !isNaN(startTime.getTime())) {
        // Calculate initial elapsed time from the original start time
        const now = new Date();
        const initialElapsed = Math.floor((now - startTime) / 1000);
        console.log('ActiveTaskTimer - Initial elapsed time:', initialElapsed, 'seconds');
        
        // Ensure we don't have negative elapsed time
        setElapsedTime(initialElapsed > 0 ? initialElapsed : 0);
        
        // Set up timer to update every second
        const timerId = setInterval(() => {
          setElapsedTime(prev => prev + 1);
        }, 1000);
        
        return () => clearInterval(timerId);
      } else {
        // If we can't determine the start time, just start the timer from now
        console.log('ActiveTaskTimer - Starting timer from now');
        setElapsedTime(0);
        
        const timerId = setInterval(() => {
          setElapsedTime(prev => prev + 1);
        }, 1000);
        
        return () => clearInterval(timerId);
      }
    } else {
      setElapsedTime(0);
    }
  }, [tasks]);
  
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
  
  if (!activeTask) {
    return null;
  }
  
  return (
    <Card className="mb-3 active-task-card">
      <Card.Body className="p-3">
        <div className="d-flex flex-wrap align-items-center">
          <div className="me-4 mb-2 mb-md-0">
            <Badge bg="danger" className="timer-badge large-timer" style={{ minWidth: '140px', textAlign: 'center' }}>
              <i className="bi bi-stopwatch-fill me-2"></i>
              {formatTime(elapsedTime)}
            </Badge>
          </div>
          <div>
            <h6 className="mb-1">Currently working on:</h6>
            <p className="mb-0 fw-bold">{activeTask.task_name} <span className="text-muted">(Task #{activeTask.task_id})</span></p>
          </div>
        </div>
      </Card.Body>
    </Card>
  );
}

export default ActiveTaskTimer;