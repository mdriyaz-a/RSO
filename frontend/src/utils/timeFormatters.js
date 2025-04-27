/**
 * Utility functions for formatting dates and times in a user-friendly way
 */

// Define work hours
const WORK_HOURS = {
  start: 9, // 9:00 AM
  end: 17   // 5:00 PM
};

/**
 * Format a date in a user-friendly way
 * @param {Date|string} date - The date to format
 * @param {boolean} includeDay - Whether to include the day of week
 * @returns {string} Formatted date
 */
export const formatDate = (date, includeDay = true) => {
  if (!date) return 'None';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  const options = {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  };
  
  if (includeDay) {
    options.weekday = 'short';
  }
  
  return dateObj.toLocaleDateString('en-US', options);
};

/**
 * Format a time in a user-friendly way (12-hour format with AM/PM)
 * @param {Date|string} date - The date containing the time to format
 * @returns {string} Formatted time
 */
export const formatTime = (date) => {
  if (!date) return 'None';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  return dateObj.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
};

/**
 * Check if a date is within work hours
 * @param {Date} date - The date to check
 * @returns {boolean} True if the date is within work hours
 */
const isWithinWorkHours = (date) => {
  const hours = date.getHours();
  return hours >= WORK_HOURS.start && hours < WORK_HOURS.end;
};

/**
 * Check if two dates are on the same day
 * @param {Date} date1 - First date
 * @param {Date} date2 - Second date
 * @returns {boolean} True if both dates are on the same day
 */
const isSameDay = (date1, date2) => {
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  );
};

/**
 * Format a task's time range in a user-friendly, shift-aware manner
 * @param {Date|string} startDate - The start date/time
 * @param {Date|string} endDate - The end date/time
 * @returns {string} Formatted time range
 */
export const formatTaskTimeRange = (startDate, endDate) => {
  if (!startDate || !endDate) return 'Time not specified';
  
  const start = typeof startDate === 'string' ? new Date(startDate) : startDate;
  const end = typeof endDate === 'string' ? new Date(endDate) : endDate;
  
  // If start and end are on the same day
  if (isSameDay(start, end)) {
    const startTime = formatTime(start);
    const endTime = formatTime(end);
    const dateStr = formatDate(start);
    return `<span class="clock-emoji" role="img" aria-label="clock">🕓</span> ${startTime} – ${endTime} (${dateStr})`;
  }
  
  // For multi-day tasks, we need to handle shift boundaries
  let formattedRange = '';
  
  // Calculate the number of calendar days between start and end
  const startDay = new Date(start);
  startDay.setHours(0, 0, 0, 0);
  
  const endDay = new Date(end);
  endDay.setHours(0, 0, 0, 0);
  
  const dayDiff = Math.round((endDay - startDay) / (1000 * 60 * 60 * 24));
  
  // First day
  const day1 = new Date(start);
  const day1End = new Date(day1);
  day1End.setHours(WORK_HOURS.end, 0, 0, 0);
  
  // If start time is after work hours end, adjust to show actual time
  if (day1.getHours() >= WORK_HOURS.end) {
    formattedRange += `<span class="clock-emoji" role="img" aria-label="clock">🕓</span> Day 1: ${formatTime(day1)} – ${formatTime(day1)} (${day1.toLocaleDateString('en-US', { weekday: 'short' })})`;
  } 
  // If start time is before work hours start, adjust to show work hours start
  else if (day1.getHours() < WORK_HOURS.start) {
    const adjustedStart = new Date(day1);
    adjustedStart.setHours(WORK_HOURS.start, 0, 0, 0);
    formattedRange += `<span class="clock-emoji" role="img" aria-label="clock">🕓</span> Day 1: ${formatTime(adjustedStart)} – ${formatTime(day1End)} (${day1.toLocaleDateString('en-US', { weekday: 'short' })})`;
  }
  // Normal case within work hours
  else {
    formattedRange += `<span class="clock-emoji" role="img" aria-label="clock">🕓</span> Day 1: ${formatTime(day1)} – ${formatTime(day1End)} (${day1.toLocaleDateString('en-US', { weekday: 'short' })})`;
  }
  
  // Middle days (if any)
  for (let i = 1; i < dayDiff; i++) {
    const currentDay = new Date(startDay);
    currentDay.setDate(startDay.getDate() + i);
    
    const dayStart = new Date(currentDay);
    dayStart.setHours(WORK_HOURS.start, 0, 0, 0);
    
    const dayEnd = new Date(currentDay);
    dayEnd.setHours(WORK_HOURS.end, 0, 0, 0);
    
    formattedRange += `\n<span class="clock-emoji" role="img" aria-label="clock">🕓</span> Day ${i + 1}: ${formatTime(dayStart)} – ${formatTime(dayEnd)} (${dayStart.toLocaleDateString('en-US', { weekday: 'short' })})`;
  }
  
  // Last day
  if (dayDiff > 0) {
    const lastDay = new Date(end);
    const lastDayStart = new Date(lastDay);
    lastDayStart.setHours(WORK_HOURS.start, 0, 0, 0);
    
    // If end time is before work hours start, adjust to show actual time
    if (lastDay.getHours() < WORK_HOURS.start) {
      formattedRange += `\n<span class="clock-emoji" role="img" aria-label="clock">🕓</span> Day ${dayDiff + 1}: ${formatTime(lastDay)} – ${formatTime(lastDay)} (${lastDay.toLocaleDateString('en-US', { weekday: 'short' })})`;
    }
    // If end time is after work hours end, adjust to show work hours end
    else if (lastDay.getHours() >= WORK_HOURS.end) {
      const adjustedEnd = new Date(lastDay);
      adjustedEnd.setHours(WORK_HOURS.end, 0, 0, 0);
      formattedRange += `\n<span class="clock-emoji" role="img" aria-label="clock">🕓</span> Day ${dayDiff + 1}: ${formatTime(lastDayStart)} – ${formatTime(adjustedEnd)} (${lastDay.toLocaleDateString('en-US', { weekday: 'short' })})`;
    }
    // Normal case within work hours
    else {
      formattedRange += `\n<span class="clock-emoji" role="img" aria-label="clock">🕓</span> Day ${dayDiff + 1}: ${formatTime(lastDayStart)} – ${formatTime(lastDay)} (${lastDay.toLocaleDateString('en-US', { weekday: 'short' })})`;
    }
  }
  
  return formattedRange;
};

/**
 * Get a note about work hours
 * @returns {string} Work hours note
 */
export const getWorkHoursNote = () => {
  const startTime = formatTime(new Date().setHours(WORK_HOURS.start, 0, 0, 0));
  const endTime = formatTime(new Date().setHours(WORK_HOURS.end, 0, 0, 0));
  return `<span class="work-hours-icon" role="img" aria-label="info">ℹ️</span> Work Hours: ${startTime} – ${endTime}`;
};