import React, { useState, useEffect } from 'react';
import { Card, ListGroup } from 'react-bootstrap';
import axios from 'axios';

function LogsPanel() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
    
    // Set up polling to refresh logs every 10 seconds
    const interval = setInterval(fetchLogs, 10000);
    
    return () => clearInterval(interval);
  }, []);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/schedules/log');
      setLogs(response.data.combined_logs || []);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching logs:', error);
      setLoading(false);
    }
  };

  return (
    <Card>
      <Card.Header>Recent Activity</Card.Header>
      <Card.Body className="log-panel">
        {loading ? (
          <p>Loading logs...</p>
        ) : logs.length === 0 ? (
          <p>No recent activity</p>
        ) : (
          <ListGroup variant="flush">
            {logs.map((log, index) => (
              <ListGroup.Item 
                key={index} 
                className={`log-entry log-entry-${log.type}`}
              >
                <small className="text-muted">
                  {new Date(log.time_iso).toLocaleString()}
                </small>
                <div>{log.message}</div>
              </ListGroup.Item>
            ))}
          </ListGroup>
        )}
      </Card.Body>
    </Card>
  );
}

export default LogsPanel;