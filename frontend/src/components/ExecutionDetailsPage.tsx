import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useLocation, Link }  from 'react-router-dom';
import apiService, { WorkflowExecutionInfo, WorkflowExecutionHistory, WorkflowEvent } from '../services/apiService';
import { useAuth } from '../contexts/AuthContext';

const ExecutionDetailsPage: React.FC = () => {
  const { workflowId } = useParams<{ workflowId: string }>();
  const location = useLocation();
  const { token, logout } = useAuth();

  const [details, setDetails] = useState<WorkflowExecutionInfo | null>(null);
  const [history, setHistory] = useState<WorkflowExecutionHistory | null>(null);
  const [isLoading, setIsLoading] = useState(true); // Start true for initial load
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Memoize runId extraction
  const runId = React.useMemo(() => new URLSearchParams(location.search).get('run_id') || undefined, [location.search]);

  const fetchDetailsAndHistory = useCallback(async () => {
    if (!token || !workflowId) return;
    setIsLoading(true);
    setError(null);
    try {
      const detailsData = await apiService.getWorkflowExecutionDetails(token, workflowId, runId);
      setDetails(detailsData);
      // Use the run_id from detailsData for fetching history, as it's the definitive one if not specified in URL
      const currentRunId = detailsData.run_id || runId;
      if (currentRunId) { // Only fetch history if a run_id is available
        const historyData = await apiService.getWorkflowExecutionHistory(token, workflowId, currentRunId);
        setHistory(historyData);
      } else {
        // This case might happen if Temporal somehow doesn't return a run_id for a workflow_id,
        // or if the workflow hasn't started a run yet (less likely for a details page).
        setHistory(null);
        setError("Run ID is not available, cannot fetch history.");
      }
    } catch (err: any) {
      console.error("Failed to fetch execution details or history:", err);
      setError(err.response?.data?.detail || "Failed to fetch execution data.");
      if (err.response?.status === 401) logout();
    } finally {
      setIsLoading(false);
    }
  }, [token, workflowId, runId, logout]);

  useEffect(() => {
    fetchDetailsAndHistory();
  }, [fetchDetailsAndHistory]);

  const fetchMoreHistory = async () => {
    if (!token || !workflowId || !history || !history.next_page_token || !details?.run_id) return;
    setIsLoadingHistory(true);
    try {
      // Use details.run_id as it's the definitive one for the current view
      const moreHistoryData = await apiService.getWorkflowExecutionHistory(token, workflowId, details.run_id, history.next_page_token);
      setHistory(prev => ({
        ...moreHistoryData, // new workflow_id, run_id, next_page_token
        events: prev ? [...prev.events, ...moreHistoryData.events] : moreHistoryData.events, // append events
      }));
    } catch (err: any) {
      console.error("Failed to fetch more history:", err);
      setError(err.response?.data?.detail || "Failed to fetch more history.");
       if (err.response?.status === 401) logout();
    } finally {
      setIsLoadingHistory(false);
    }
  };

  if (isLoading) return <p>Loading execution details...</p>;
  if (error) return <p style={{ color: 'red' }}>{error}</p>;
  if (!details) return <p>No execution details found for Workflow ID: {workflowId}.</p>;

  return (
    <div>
      <p><Link to="/executions">&larr; Back to Executions List</Link></p>
      <h2>Execution: {details.workflow_id}</h2>
      <div style={{ marginBottom: '20px', padding: '10px', border: '1px solid #eee', background: '#f9f9f9' }}>
        <p><strong>Run ID:</strong> {details.run_id || 'N/A'}</p>
        <p><strong>Status:</strong> <span style={{fontWeight: 'bold', color: details.status === 'COMPLETED' ? 'green' : (details.status === 'FAILED' || details.status === 'TIMED_OUT' ? 'red' : 'orange')}}>{details.status}</span></p>
        <p><strong>Task Queue:</strong> {details.task_queue}</p>
        <p><strong>Start Time:</strong> {new Date(details.start_time).toLocaleString()}</p>
        <p><strong>Close Time:</strong> {details.close_time ? new Date(details.close_time).toLocaleString() : 'N/A'}</p>
      </div>

      <h3>Event History</h3>
      {history && history.events.length > 0 ? (
        <div style={{ border: '1px solid #ccc', borderRadius: '4px' }}>
          <ul style={{ listStyleType: 'none', padding: '0', margin: '0', maxHeight: '600px', overflowY: 'auto' }}>
            {history.events.map(event => (
              <li key={event.event_id} style={{ borderBottom: '1px solid #eee', padding: '10px' }}>
                <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.9em', color: '#555'}}>
                  <span>ID: {event.event_id}</span>
                  <span>{new Date(event.event_time).toLocaleString()}</span>
                </div>
                <strong style={{fontSize: '1.1em'}}>{event.event_type.replace(/([A-Z])/g, ' $1').trim()}</strong> {/* Add spaces to event type */}
                {event.attributes && Object.keys(event.attributes).length > 0 && (
                  <pre style={{ fontSize: '0.85em', backgroundColor: '#f0f0f0', padding: '8px', marginTop: '5px', whiteSpace: 'pre-wrap', wordBreak: 'break-all', borderRadius: '3px' }}>
                    {JSON.stringify(event.attributes, null, 2)}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : <p>{isLoadingHistory ? 'Loading history...' : (details.run_id ? 'No history events found.' : 'Run ID not available to fetch history.')}</p>}
      {history && history.next_page_token && (
        <button onClick={fetchMoreHistory} disabled={isLoadingHistory} style={{marginTop: '15px', padding: '10px 15px'}}>
          {isLoadingHistory ? 'Loading More...' : 'Load More History'}
        </button>
      )}
    </div>
  );
};

export default ExecutionDetailsPage;
