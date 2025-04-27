import React, { useState, useEffect } from 'react';
import { Badge } from 'react-bootstrap';

function TaskTimer({ task }) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    // Check if the task is currently active (clocked in)
    const isActivelyWorking = task.status === 'In Progress' && (task.actual_start || task.actual_start_iso) && !(task.actual_end || task.actual_end_iso);
    
    console.log('TaskTimer - Task:', task.task_id, task.task_name);
    console.log('TaskTimer - Status:', task.status);
    console.log('TaskTimer - actual_start:', task.actual_start);
    console.log('TaskTimer - actual_start_iso:', task.actual_start_iso);
    console.log('TaskTimer - isActivelyWorking:', isActivelyWorking);
    
    setIsRunning(isActivelyWorking);

    if (isActivelyWorking) {
      let startTime;
      
      // Try to get the start time from the ISO string or the actual_start field
      if (task.actual_start_iso) {
        startTime = new Date(task.actual_start_iso);
      } else if (task.actual_start) {
        // If actual_start is a Date object
        if (task.actual_start instanceof Date) {
          startTime = task.actual_start;
        } 
        // If actual_start is a string
        else if (typeof task.actual_start === 'string') {
          startTime = new Date(task.actual_start);
        }
      }
      
      if (startTime && !isNaN(startTime.getTime())) {
        console.log('TaskTimer - Using start time:', startTime);
        
        // Calculate total elapsed time including any previous work sessions
        // We need to account for breaks by looking at task_progress entries
        
        // For now, we'll use a simple approach: calculate from actual_start to now
        const now = new Date();
        let initialElapsed = Math.floor((now - startTime) / 1000);
        
        // If there were breaks, we should subtract them, but we don't have that data in the frontend
        // This is a simplification - a more accurate approach would be to sum up all work sessions
        console.log('TaskTimer - initialElapsed:', initialElapsed, 'seconds');
        
        // Ensure we don't have negative elapsed time
        setElapsedTime(initialElapsed > 0 ? initialElapsed : 0);

        // Set up timer to update every second
        const timerId = setInterval(() => {
          setElapsedTime(prev => prev + 1);
        }, 1000);

        // Clean up timer on unmount or when task is no longer active
        return () => clearInterval(timerId);
      } else {
        console.error('TaskTimer - Invalid start time:', task.actual_start_iso || task.actual_start);
        
        // If we can't determine the start time, just start the timer from now
        console.log('TaskTimer - Starting timer from now');
        setElapsedTime(0);
        
        const timerId = setInterval(() => {
          setElapsedTime(prev => prev + 1);
        }, 1000);
        
        return () => clearInterval(timerId);
      }
    } else {
      // Reset timer if not actively working
      setElapsedTime(0);
    }
  }, [task]);

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