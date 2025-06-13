import React, { useState, useEffect, useCallback } from 'react';
import apiService, { ScheduleInfo, ScheduleCreateRequest } from '../services/apiService';
import { useAuth } from '../contexts/AuthContext';

interface TestSuiteLite {
  id: string;
  name: string;
}

const SchedulesPage: React.FC = () => {
  const { token, logout } = useAuth();
  const [schedules, setSchedules] = useState<ScheduleInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  const [testSuites, setTestSuites] = useState<TestSuiteLite[]>([]);

  // Form state for creating new schedule
  const [newScheduleId, setNewScheduleId] = useState('');
  const [newScheduleName, setNewScheduleName] = useState('');
  const [newCronString, setNewCronString] = useState('');
  const [newSuiteId, setNewSuiteId] = useState('');
  const [newInputs, setNewInputs] = useState('{}');

  const fetchSchedules = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiService.listSchedules(token);
      setSchedules(data);
    } catch (err: any) {
      console.error("Failed to fetch schedules:", err);
      setError(err.response?.data?.detail || "Failed to fetch schedules.");
      if (err.response?.status === 401) logout();
    } finally {
      setIsLoading(false);
    }
  }, [token, logout]);

  const fetchTestSuites = useCallback(async () => {
    if (!token) return;
    try {
      const response = await apiService.getConfigData('test_suites', token);
      if (Array.isArray(response.data)) {
        setTestSuites(response.data.map((suite: any) => ({ id: suite.id, name: suite.name })));
      }
    } catch (err) {
      console.error("Failed to fetch test suites for dropdown:", err);
    }
  }, [token]);


  useEffect(() => {
    fetchSchedules();
    fetchTestSuites();
  }, [fetchSchedules, fetchTestSuites]);

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setSubmitError(null);
    setSubmitSuccess(null);

    let parsedInputs: Record<string, any>;
    try {
      parsedInputs = JSON.parse(newInputs);
    } catch (jsonError) {
      setSubmitError("Invalid JSON format for inputs.");
      return;
    }

    const scheduleData: ScheduleCreateRequest = {
      schedule_id: newScheduleId,
      schedule_name: newScheduleName,
      cron_string: newCronString,
      suite_id: newSuiteId,
      inputs: parsedInputs
    };

    setIsLoading(true); // Indicate loading for submit
    try {
      await apiService.createSchedule(token, scheduleData);
      setSubmitSuccess(`Schedule '${newScheduleName}' created successfully!`);
      fetchSchedules();
      setNewScheduleId(''); setNewScheduleName(''); setNewCronString(''); setNewSuiteId(''); setNewInputs('{}');
    } catch (err: any) {
      console.error("Failed to create schedule:", err);
      setSubmitError(err.response?.data?.detail || "Failed to create schedule.");
      if (err.response?.status === 401) logout();
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteSchedule = async (scheduleId: string) => {
    if (!token || !window.confirm(`Are you sure you want to delete schedule '${scheduleId}'?`)) return;
    setSubmitError(null);
    setSubmitSuccess(null);
    setIsLoading(true); // Indicate loading for delete
    try {
      await apiService.deleteSchedule(token, scheduleId);
      setSubmitSuccess(`Schedule '${scheduleId}' deleted successfully!`);
      fetchSchedules();
    } catch (err: any) {
      console.error("Failed to delete schedule:", err);
      setSubmitError(err.response?.data?.detail || "Failed to delete schedule.");
      if (err.response?.status === 401) logout();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <h2>Manage Schedules</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}

      <h3>Create New Schedule</h3>
      <form onSubmit={handleCreateSchedule} style={{ marginBottom: '30px', border: '1px solid #ccc', padding: '20px', borderRadius: '5px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: '10px', alignItems: 'center' }}>
          <label htmlFor="newScheduleId">Schedule ID:</label>
          <input type="text" id="newScheduleId" value={newScheduleId} onChange={e => setNewScheduleId(e.target.value)} required />

          <label htmlFor="newScheduleName">Schedule Name:</label>
          <input type="text" id="newScheduleName" value={newScheduleName} onChange={e => setNewScheduleName(e.target.value)} required />

          <label htmlFor="newCronString">Cron String:</label>
          <input type="text" id="newCronString" value={newCronString} onChange={e => setNewCronString(e.target.value)} required placeholder="e.g., 0 5 * * *" />

          <label htmlFor="newSuiteId">Test Suite:</label>
          <select id="newSuiteId" value={newSuiteId} onChange={e => setNewSuiteId(e.target.value)} required>
            <option value="">-- Select Test Suite --</option>
            {testSuites.map(suite => (
              <option key={suite.id} value={suite.id}>{suite.name} ({suite.id})</option>
            ))}
          </select>

          <label htmlFor="newInputs">Inputs (JSON):</label>
          <textarea
            id="newInputs"
            value={newInputs}
            onChange={e => setNewInputs(e.target.value)}
            rows={3}
            placeholder='e.g., {"username": "test"}'
            style={{ fontFamily: 'monospace', width: '100%' }} // Ensure textarea takes full width
          />
        </div>
        <button type="submit" style={{ marginTop: '15px', padding: '10px 15px' }} disabled={isLoading}>
            {isLoading && submitError === null && submitSuccess === null ? 'Submitting...' : 'Create Schedule'}
        </button>
        {submitError && <p style={{ color: 'red', marginTop: '10px' }}>{submitError}</p>}
        {submitSuccess && <p style={{ color: 'green', marginTop: '10px' }}>{submitSuccess}</p>}
      </form>

      <h3>Existing Schedules</h3>
      {isLoading && schedules.length === 0 && <p>Loading schedules...</p>}
      {schedules.length > 0 ? (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={tableHeaderStyle}>Schedule ID</th>
              <th style={tableHeaderStyle}>Name</th>
              <th style={tableHeaderStyle}>Cron String</th>
              <th style={tableHeaderStyle}>Suite ID</th>
              <th style={tableHeaderStyle}>Status</th>
              <th style={tableHeaderStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {schedules.map(sch => (
              <tr key={sch.schedule_id}>
                <td style={tableCellStyle}>{sch.schedule_id}</td>
                <td style={tableCellStyle}>{sch.schedule_name || 'N/A'}</td>
                <td style={tableCellStyle}>{sch.cron_string || 'N/A'}</td>
                <td style={tableCellStyle}>{sch.suite_id || 'N/A'}</td>
                <td style={tableCellStyle}>{sch.status}</td>
                <td style={tableCellStyle}>
                  <button onClick={() => handleDeleteSchedule(sch.schedule_id)} style={{backgroundColor: '#dc3545', padding: '5px 10px'}} disabled={isLoading}>
                    {isLoading && (submitError === null && submitSuccess === null) ? 'Deleting...' : 'Delete'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        !isLoading && <p>No schedules found.</p>
      )}
    </div>
  );
};

const tableHeaderStyle: React.CSSProperties = { border: '1px solid #ddd', padding: '10px 8px', textAlign: 'left', backgroundColor: '#f2f2f2', fontWeight: 'bold' };
const tableCellStyle: React.CSSProperties = { border: '1px solid #ddd', padding: '10px 8px', textAlign: 'left', wordBreak: 'break-word' };

export default SchedulesPage;
