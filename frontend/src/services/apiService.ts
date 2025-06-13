import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// UserPublic interface
interface UserPublic {
  id: number;
  username: string;
  email?: string;
  full_name?: string;
  roles: string[];
}

// Workflow execution interfaces
export interface WorkflowExecutionInfo {
  workflow_id: string;
  run_id?: string;
  task_queue: string;
  status: string;
  start_time: string;
  close_time?: string;
}
export interface PaginatedWorkflowExecutions {
  executions: WorkflowExecutionInfo[];
  next_page_token?: string;
  total_count?: number;
}
export interface WorkflowEvent {
  event_id: string;
  event_time: string;
  event_type: string;
  attributes?: Record<string, any>;
}
export interface WorkflowExecutionHistory {
  workflow_id: string;
  run_id: string;
  events: WorkflowEvent[];
  next_page_token?: string;
}

// Schedule interfaces
export interface ScheduleInfo {
  schedule_id: string;
  schedule_name?: string;
  cron_string?: string;
  suite_id?: string;
  inputs?: Record<string, any>;
  status: string;
  start_time: string;
}
export interface ScheduleCreateRequest {
  schedule_id: string;
  schedule_name: string;
  cron_string: string;
  suite_id: string;
  inputs: Record<string, any>;
}


const apiService = {
  login: async (username: string, password: string): Promise<string> => {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    const response = await axios.post(`${API_BASE_URL}/token`, params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    if (response.data.access_token) return response.data.access_token;
    throw new Error("Token not found in response");
  },

  register: async (username: string, email: string, password: string, fullName?: string): Promise<any> => {
    const payload = { username, email, password, full_name: fullName || undefined, roles: ["viewer"] };
    const response = await axios.post(`${API_BASE_URL}/users/register`, payload);
    return response.data;
  },

  getCurrentUser: (token: string) => {
    return axios.get<UserPublic>(`${API_BASE_URL}/users/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  },

  getConfigTypes: (token: string) => {
    return axios.get(`${API_BASE_URL}/api/v1/configs`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  },

  getConfigData: (configType: string, token: string) => {
    return axios.get(`${API_BASE_URL}/api/v1/configs/${configType}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  },

  startWorkflow: (suiteId: string, inputs: Record<string, any>, token: string) => {
    return axios.post(`${API_BASE_URL}/api/v1/workflows/test-suites/start`,
      { suite_id: suiteId, inputs: inputs },
      { headers: { Authorization: `Bearer ${token}` } }
    );
  },

  listWorkflowExecutions: async (
    token: string, pageSize: number = 20, nextPageToken?: string,
    workflowIdFilter?: string, workflowTypeFilter?: string, statusFilter?: string
  ): Promise<PaginatedWorkflowExecutions> => {
    const params = new URLSearchParams();
    params.append('page_size', String(pageSize));
    if (nextPageToken) params.append('next_page_token', nextPageToken);
    if (workflowIdFilter) params.append('workflow_id_filter', workflowIdFilter);
    if (workflowTypeFilter) params.append('workflow_type_filter', workflowTypeFilter);
    if (statusFilter) params.append('status_filter', statusFilter);
    const response = await axios.get<PaginatedWorkflowExecutions>(`${API_BASE_URL}/api/v1/workflows/executions`, {
      headers: { Authorization: `Bearer ${token}` }, params
    });
    return response.data;
  },

  getWorkflowExecutionDetails: async (token: string, workflowId: string, runId?: string): Promise<WorkflowExecutionInfo> => {
    const params = new URLSearchParams();
    if (runId) params.append('run_id', runId);
    const response = await axios.get<WorkflowExecutionInfo>(`${API_BASE_URL}/api/v1/workflows/executions/${workflowId}`, {
      headers: { Authorization: `Bearer ${token}` }, params
    });
    return response.data;
  },

  getWorkflowExecutionHistory: async (
    token: string, workflowId: string, runId?: string, nextPageToken?: string
  ): Promise<WorkflowExecutionHistory> => {
    const params = new URLSearchParams();
    if (runId) params.append('run_id', runId);
    if (nextPageToken) params.append('next_page_token', nextPageToken);
    const response = await axios.get<WorkflowExecutionHistory>(`${API_BASE_URL}/api/v1/workflows/executions/${workflowId}/history`, {
      headers: { Authorization: `Bearer ${token}` }, params
    });
    return response.data;
  },

  // Schedule methods
  listSchedules: async (token: string): Promise<ScheduleInfo[]> => {
    const response = await axios.get<ScheduleInfo[]>(`${API_BASE_URL}/api/v1/schedules`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  createSchedule: async (token: string, scheduleData: ScheduleCreateRequest): Promise<ScheduleInfo> => {
    const response = await axios.post<ScheduleInfo>(`${API_BASE_URL}/api/v1/schedules`, scheduleData, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  deleteSchedule: async (token: string, scheduleId: string): Promise<void> => {
    await axios.delete(`${API_BASE_URL}/api/v1/schedules/${scheduleId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
  }
};

export default apiService;
