import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'; // Backend API URL

const apiService = {
  login: async (username: string, password: string):Promise<string> => {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);

    const response = await axios.post(`${API_BASE_URL}/token`, params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });
    if (response.data.access_token) {
      return response.data.access_token;
    }
    throw new Error("Token not found in response");
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
  }
  // Later: add methods to start workflows, get execution history, etc.
};

export default apiService;
