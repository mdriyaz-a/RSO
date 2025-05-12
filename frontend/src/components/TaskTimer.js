import React, { useState, useEffect } from 'react';
import { Badge } from 'react-bootstrap';

// Create a global object to store task timers
if (!window.taskTimers) {
  window.taskTimers = {};
}

function TaskTimer({ task }) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const taskId = task.task_id;

  // Check if the task is currently active (clocked in)
  const isActivelyWorking = task.status === 'In Progress' && 
                           (task.actual_start || task.actual_start_iso) && 
                           !(task.actual_end || task.actual_end_iso);

  // Initialize this task's timer if it doesn't exist
  useEffect(() => {
    if (!window.taskTimers[taskId]) {
      window.taskTimers[taskId] = {
        accumulatedTime: 0,
        lastClockInTime: null,
        isRunning: false
      };
    }
    
    console.log(`TaskTimer - Initial state for task ${taskId}:`, window.taskTimers[taskId]);
    
    // Set initial elapsed time from stored value
    setElapsedTime(window.taskTimers[taskId].accumulatedTime || 0);
  }, [taskId]);

  // Handle clock in/out transitions
  useEffect(() => {
    console.log(`TaskTimer - Task ${taskId} status:`, task.status);
    console.log(`TaskTimer - Task ${taskId} isActivelyWorking:`, isActivelyWorking);
    console.log(`TaskTimer - Task ${taskId} stored isRunning:`, window.taskTimers[taskId].isRunning);
    
    // Detect clock in
    if (isActivelyWorking && !window.taskTimers[taskId].isRunning) {
      console.log(`TaskTimer - Task ${taskId} clocking in`);
      window.taskTimers[taskId].lastClockInTime = new Date();
      window.taskTimers[taskId].isRunning = true;
    }
    
    // Detect clock out
    if (!isActivelyWorking && window.taskTimers[taskId].isRunning) {
      console.log(`TaskTimer - Task ${taskId} clocking out`);
      
      // Calculate time spent in this session
      if (window.taskTimers[taskId].lastClockInTime) {
        const sessionTime = Math.floor((new Date() - window.taskTimers[taskId].lastClockInTime) / 1000);
        window.taskTimers[taskId].accumulatedTime += sessionTime;
        console.log(`TaskTimer - Task ${taskId} accumulated time:`, window.taskTimers[taskId].accumulatedTime);
      }
      
      window.taskTimers[taskId].isRunning = false;
      window.taskTimers[taskId].lastClockInTime = null;
    }
    
    setIsRunning(isActivelyWorking);
  }, [isActivelyWorking, taskId, task.status]);

  // Update timer when running
  useEffect(() => {
    if (isActivelyWorking) {
      // Set up timer to update every second
      const timerId = setInterval(() => {
        if (window.taskTimers[taskId].lastClockInTime) {
          const currentSessionTime = Math.floor((new Date() - window.taskTimers[taskId].lastClockInTime) / 1000);
          const totalTime = window.taskTimers[taskId].accumulatedTime + currentSessionTime;
          setElapsedTime(totalTime);
        }
      }, 1000);
      
      // Initial calculation
      if (window.taskTimers[taskId].lastClockInTime) {
        const currentSessionTime = Math.floor((new Date() - window.taskTimers[taskId].lastClockInTime) / 1000);
        const totalTime = window.taskTimers[taskId].accumulatedTime + currentSessionTime;
        setElapsedTime(totalTime);
      }
      
      return () => clearInterval(timerId);
    } else {
      // When not actively working, just show accumulated time
      setElapsedTime(window.taskTimers[taskId].accumulatedTime || 0);
    }
  }, [isActivelyWorking, taskId]);

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

  if (!isRunning) {
    return null;
  }

  return (
    <div className="task-timer">
      <Badge bg="danger" className="timer-badge">
        <i className="bi bi-stopwatch-fill me-1"></i>
        {formatTime(elapsedTime)}
        <span className="ms-1 small">(Active)</span>
      </Badge>
    </div>
  );
}

export default TaskTimer;