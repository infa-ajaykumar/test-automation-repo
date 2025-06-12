import React, { useState, useEffect } from 'react';
import apiService from './services/apiService';
import './App.css';

function App() {
  const [configTypes, setConfigTypes] = useState<string[]>([]);
  const [selectedConfigType, setSelectedConfigType] = useState<string | null>(null);
  const [configData, setConfigData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('authToken')); // Or use context

  // Dummy login for now
  const handleLogin = async () => {
    try {
      const obtainedToken = await apiService.login('testuser', 'password');
      localStorage.setItem('authToken', obtainedToken);
      setToken(obtainedToken);
      setError(null);
    } catch (err) {
      setError('Login failed. Check credentials.');
      localStorage.removeItem('authToken');
      setToken(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    setToken(null);
    setConfigTypes([]);
    setSelectedConfigType(null);
    setConfigData(null);
  };

  useEffect(() => {
    if (token) {
      apiService.getConfigTypes(token)
        .then(response => {
          setConfigTypes(response.data);
          setError(null);
        })
        .catch(err => {
          console.error("Error fetching config types:", err);
          if (err.response && err.response.status === 401) {
            setError("Unauthorized. Please login again.");
            handleLogout();
          } else {
            setError("Failed to fetch config types.");
          }
        });
    }
  }, [token]);

  const fetchConfigData = (configType: string) => {
    if (token) {
      setSelectedConfigType(configType);
      apiService.getConfigData(configType, token)
        .then(response => {
          setConfigData(response.data);
          setError(null);
        })
        .catch(err => {
          console.error(`Error fetching ${configType}:`, err);
           if (err.response && err.response.status === 401) {
            setError("Unauthorized. Please login again.");
            handleLogout();
          } else {
            setError(`Failed to fetch ${configType}.`);
          }
          setConfigData(null);
        });
    }
  };

  if (!token) {
    return (
      <div className="App">
        <header className="App-header">
          <h1>Test Orchestrator</h1>
          <p>Please login to continue.</p>
          <button onClick={handleLogin}>Login (testuser/password)</button>
          {error && <p style={{ color: 'red' }}>{error}</p>}
        </header>
      </div>
    );
  }

  return (
    <div className="App">
      <header className="App-header">
        <h1>Test Orchestrator Dashboard</h1>
        <button onClick={handleLogout} style={{float: 'right'}}>Logout</button>
      </header>
      <nav>
        <h2>Available Configurations</h2>
        {error && <p style={{ color: 'red' }}>{error}</p>}
        <ul>
          {configTypes.map(type => (
            <li key={type} onClick={() => fetchConfigData(type)} style={{ cursor: 'pointer', textDecoration: selectedConfigType === type ? 'underline' : 'none' }}>
              {type}
            </li>
          ))}
        </ul>
      </nav>
      <main>
        {selectedConfigType && (
          <>
            <h2>{selectedConfigType} Data</h2>
            {configData ? (
              <pre>{JSON.stringify(configData, null, 2)}</pre>
            ) : (
              <p>Loading {selectedConfigType}...</p>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
