import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import apiService, { PaginatedWorkflowExecutions, WorkflowExecutionInfo } from '../services/apiService';
import { useAuth } from '../contexts/AuthContext';

const ExecutionsListPage: React.FC = () => {
  const { token, logout } = useAuth();
  const [executionsData, setExecutionsData] = useState<PaginatedWorkflowExecutions | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [workflowIdFilter, setWorkflowIdFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState(''); // e.g., RUNNING, COMPLETED, FAILED

  const fetchExecutions = useCallback(async (pageToken?: string) => {
    if (!token) return;
    setIsLoading(true);
    if (!pageToken) { // Reset error only on initial load or filter change, not on "load more"
        setError(null);
    }
    try {
      const data = await apiService.listWorkflowExecutions(
        token,
        20, // Page size
        pageToken,
        workflowIdFilter || undefined,
        undefined,
        statusFilter || undefined
      );
      setExecutionsData(prev => {
        if (pageToken && prev) {
          return {
            executions: [...prev.executions, ...data.executions],
            next_page_token: data.next_page_token,
            total_count: data.total_count || prev.total_count // Retain total if available
          };
        }
        return data;
      });
    } catch (err: any) {
      console.error("Failed to fetch executions:", err);
      setError(err.response?.data?.detail || "Failed to fetch executions.");
      if (err.response?.status === 401) logout();
    } finally {
      setIsLoading(false);
    }
  }, [token, logout, workflowIdFilter, statusFilter]);

  useEffect(() => {
    fetchExecutions();
  }, [fetchExecutions]); // fetchExecutions is memoized and includes filter dependencies

  const handleFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setExecutionsData(null); // Reset data before new filter fetch
    fetchExecutions(); // This will use the new filter values from state
  };

  const handleLoadMore = () => {
    if (executionsData?.next_page_token) {
        fetchExecutions(executionsData.next_page_token);
    }
  };

  return (
    <div>
      <h2>Workflow Executions</h2>
      <form onSubmit={handleFilterSubmit} style={{ marginBottom: '20px', display: 'flex', gap: '10px', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Filter by Workflow ID"
          value={workflowIdFilter}
          onChange={e => setWorkflowIdFilter(e.target.value)}
          style={{ padding: '8px', flexGrow: 1 }}
        />
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{ padding: '8px' }}
        >
          <option value="">All Statuses</option>
          <option value="RUNNING">Running</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
          <option value="TIMED_OUT">Timed Out</option>
          <option value="TERMINATED">Terminated</option>
          <option value="CANCELED">Canceled</option>
          {/* Add other statuses as needed */}
        </select>
        <button type="submit" style={{ padding: '8px 12px' }}>Apply Filters</button>
      </form>

      {isLoading && !executionsData?.executions.length && <p>Loading executions...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {executionsData && (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
            <thead>
              <tr>
                <th style={{...tableHeaderStyle, width: '35%'}}>Workflow ID</th>
                <th style={{...tableHeaderStyle, width: '12%'}}>Status</th>
                <th style={{...tableHeaderStyle, width: '15%'}}>Task Queue</th>
                <th style={{...tableHeaderStyle, width: '20%'}}>Start Time</th>
                <th style={{...tableHeaderStyle, width: '18%'}}>Close Time</th>
              </tr>
            </thead>
            <tbody>
              {executionsData.executions.map(exec => (
                <tr key={exec.workflow_id + (exec.run_id || '')}>
                  <td style={tableCellStyle}>
                    <Link to={`/executions/${exec.workflow_id}${exec.run_id ? '?run_id=' + exec.run_id : ''}`}>
                      {exec.workflow_id}
                    </Link>
                    {exec.run_id && <small style={{display: 'block', color: '#555'}}>Run ID: {exec.run_id.substring(0,8)}...</small>}
                  </td>
                  <td style={tableCellStyle}>{exec.status}</td>
                  <td style={tableCellStyle}>{exec.task_queue}</td>
                  <td style={tableCellStyle}>{new Date(exec.start_time).toLocaleString()}</td>
                  <td style={tableCellStyle}>{exec.close_time ? new Date(exec.close_time).toLocaleString() : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {executionsData.executions.length === 0 && !isLoading && <p>No executions found matching your criteria.</p>}
          {executionsData.next_page_token && (
            <button onClick={handleLoadMore} disabled={isLoading} style={{ marginTop: '20px', padding: '10px 15px' }}>
              {isLoading ? 'Loading more...' : 'Load More'}
            </button>
          )}
        </>
      )}
    </div>
  );
};

// Basic styles (can be moved to CSS file)
const tableHeaderStyle: React.CSSProperties = { border: '1px solid #ddd', padding: '10px 8px', textAlign: 'left', backgroundColor: '#f2f2f2', fontWeight: 'bold' };
const tableCellStyle: React.CSSProperties = { border: '1px solid #ddd', padding: '10px 8px', textAlign: 'left', wordBreak: 'break-all' };

export default ExecutionsListPage;
