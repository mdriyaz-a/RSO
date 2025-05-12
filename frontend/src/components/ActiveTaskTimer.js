import React, { useState, useEffect } from 'react';
import { Card, Badge } from 'react-bootstrap';

// Ensure the global taskTimers object exists
if (!window.taskTimers) {
  window.taskTimers = {};
}

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
      const taskId = activeTask.task_id;
      console.log('ActiveTaskTimer - Found active task:', activeTask.task_name, taskId);
      
      // Initialize this task's timer if it doesn't exist
      if (!window.taskTimers[taskId]) {
        window.taskTimers[taskId] = {
          accumulatedTime: 0,
          lastClockInTime: null,
          isRunning: false
        };
      }
      
      // If task is active but timer isn't running, start it
      if (!window.taskTimers[taskId].isRunning) {
        console.log(`ActiveTaskTimer - Starting timer for task ${taskId}`);
        window.taskTimers[taskId].lastClockInTime = new Date();
        window.taskTimers[taskId].isRunning = true;
      }
      
      // Set up timer to update every second
      const timerId = setInterval(() => {
        if (window.taskTimers[taskId] && window.taskTimers[taskId].lastClockInTime) {
          const currentSessionTime = Math.floor((new Date() - window.taskTimers[taskId].lastClockInTime) / 1000);
          const totalTime = (window.taskTimers[taskId].accumulatedTime || 0) + currentSessionTime;
          setElapsedTime(totalTime);
        }
      }, 1000);
      
      // Initial calculation
      if (window.taskTimers[taskId].lastClockInTime) {
        const currentSessionTime = Math.floor((new Date() - window.taskTimers[taskId].lastClockInTime) / 1000);
        const totalTime = (window.taskTimers[taskId].accumulatedTime || 0) + currentSessionTime;
        console.log(`ActiveTaskTimer - Task ${taskId} accumulated time:`, window.taskTimers[taskId].accumulatedTime);
        console.log(`ActiveTaskTimer - Task ${taskId} current session:`, currentSessionTime);
        console.log(`ActiveTaskTimer - Task ${taskId} total time:`, totalTime);
        setElapsedTime(totalTime);
      } else {
        setElapsedTime(window.taskTimers[taskId].accumulatedTime || 0);
      }
      
      return () => clearInterval(timerId);
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