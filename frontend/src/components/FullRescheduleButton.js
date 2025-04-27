import React, { useState } from 'react';
import { Button, Modal, Alert, Spinner } from 'react-bootstrap';
import axios from 'axios';

/**
 * A button component that triggers a full reschedule of all incomplete tasks
 * while preserving completed and in-progress tasks.
 */
function FullRescheduleButton({ onRescheduleComplete }) {
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleReschedule = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await axios.post('/api/assignments/reschedule', {
        full_reschedule: true
      });
      
      console.log('Reschedule response:', response.data);
      
      setResult({
        success: true,
        message: response.data.message,
        preservedTasks: response.data.preserved_tasks,
        rescheduledTasks: response.data.rescheduled_tasks
      });
      
      // Notify parent component to refresh data
      if (onRescheduleComplete) {
        onRescheduleComplete(response.data);
      }
    } catch (error) {
      console.error('Error during reschedule:', error);
      setError(error.response?.data?.error || 'An error occurred during rescheduling');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button 
        variant="warning" 
        onClick={() => setShowConfirmModal(true)}
        className="me-2"
      >
        <i className="bi bi-calendar-check me-1"></i>
        Full Reschedule
      </Button>
      
      <Modal show={showConfirmModal} onHide={() => setShowConfirmModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Confirm Full Reschedule</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {loading ? (
            <div className="text-center p-4">
              <Spinner animation="border" role="status" className="mb-3">
                <span className="visually-hidden">Loading...</span>
              </Spinner>
              <p>Rescheduling in progress...</p>
              <p className="text-muted small">This may take a moment. Please wait.</p>
            </div>
          ) : (
            <>
              {error && (
                <Alert variant="danger" className="mb-3">
                  {error}
                </Alert>
              )}
              
              {result ? (
                <Alert variant="success" className="mb-3">
                  <Alert.Heading>Reschedule Complete</Alert.Heading>
                  <p>{result.message}</p>
                  <hr />
                  <p className="mb-0">
                    <strong>Preserved tasks:</strong> {result.preservedTasks}<br />
                    <strong>Rescheduled tasks:</strong> {result.rescheduledTasks}
                  </p>
                </Alert>
              ) : (
                <>
                  <p>
                    This will reschedule all incomplete tasks while preserving:
                  </p>
                  <ul>
                    <li>Completed tasks</li>
                    <li>In-progress tasks</li>
                    <li>Tasks that are currently clocked in</li>
                  </ul>
                  <p>
                    The scheduler will optimize the remaining tasks based on:
                  </p>
                  <ul>
                    <li>Task priorities</li>
                    <li>Dependencies</li>
                    <li>Resource availability</li>
                    <li>Phase ordering</li>
                  </ul>
                  <p className="text-danger">
                    <strong>Warning:</strong> This operation cannot be undone. All incomplete tasks will be rescheduled.
                  </p>
                </>
              )}
            </>
          )}
        </Modal.Body>
        <Modal.Footer>
          {result ? (
            <Button variant="primary" onClick={() => setShowConfirmModal(false)}>
              Close
            </Button>
          ) : (
            <>
              <Button 
                variant="secondary" 
                onClick={() => setShowConfirmModal(false)}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button 
                variant="warning" 
                onClick={handleReschedule}
                disabled={loading}
              >
                {loading ? 'Processing...' : 'Proceed with Reschedule'}
              </Button>
            </>
          )}
        </Modal.Footer>
      </Modal>
    </>
  );
}

export default FullRescheduleButton;