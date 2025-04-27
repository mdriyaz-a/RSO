import React from 'react';
import { formatTaskTimeRange, getWorkHoursNote } from '../utils/timeFormatters';
import './TaskTimeDisplay.css';

/**
 * Component for displaying task time ranges in a user-friendly, shift-aware manner
 */
const TaskTimeDisplay = ({ startDate, endDate, showDuration = true, showWorkHours = true }) => {
  if (!startDate || !endDate) {
    return <span>Time not specified</span>;
  }
  
  // Convert string dates to Date objects if needed
  const start = typeof startDate === 'string' ? new Date(startDate) : startDate;
  const end = typeof endDate === 'string' ? new Date(endDate) : endDate;
  
  // Format the time range
  const timeRange = formatTaskTimeRange(start, end);
  
  // Calculate duration if needed
  let durationText = '';
  if (showDuration) {
    const durationMs = end - start;
    const durationHours = Math.floor(durationMs / (1000 * 60 * 60));
    const durationMinutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    durationText = ` (Duration: ${durationHours}h ${durationMinutes}m)`;
  }
  
  // Add work hours note if needed
  const workHoursNote = showWorkHours ? getWorkHoursNote() : '';
  
  // Split the time range by newlines to create separate elements
  const timeRangeParts = timeRange.split('\n');
  
  return (
    <div className="task-time-display">
      {timeRangeParts.map((part, index) => (
        <div 
          key={index} 
          className={`time-range-line ${index === 0 ? 'first-day' : ''}`}
          dangerouslySetInnerHTML={{ __html: part }}
        />
      ))}
      {showDuration && (
        <div className="duration-line">
          {durationText}
        </div>
      )}
      {showWorkHours && (
        <div className="work-hours-note">
          <small className="text-muted">{workHoursNote}</small>
        </div>
      )}
    </div>
  );
};

export default TaskTimeDisplay;