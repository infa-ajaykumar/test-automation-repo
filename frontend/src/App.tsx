import React from 'react';
import { Routes, Route, Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import './App.css';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import TestSuiteSelector from './components/TestSuiteSelector';
import ExecutionsListPage from './components/ExecutionsListPage';
import ExecutionDetailsPage from './components/ExecutionDetailsPage';
import SchedulesPage from './components/SchedulesPage';

// Dashboard component
const DashboardPage = () => {
  const { user, logout, hasRole } = useAuth(); // logout is already available in App header, but if needed here too

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <h1>Dashboard</h1>
        {/* User info and logout are now primarily in the main App header */}
        {/* Can add specific dashboard welcome or keep it clean */}
      </div>
      {/* Link to Admin section if user has admin role, already in main App header but can be here too if desired */}
      {/* {hasRole('admin') && <p><Link to="/admin">Admin Section</Link></p>} */}

      {/* Test Execution Section */}
      <div style={{marginBottom: '30px', padding: '20px', border: '1px solid #e0e0e0', borderRadius: '5px', background: '#fff' }}>
        <h2 style={{marginTop: '0'}}>Execute Test Suite</h2>
        <TestSuiteSelector />
      </div>

      {/* Placeholder for Visualizations */}
      <div>
        <h2>Execution Trends & Visualizations</h2>
        <div style={{
          border: '2px dashed #ccc',
          padding: '20px',
          textAlign: 'center',
          minHeight: '200px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: '#f9f9f9',
          borderRadius: '5px'
        }}>
          <p style={{color: '#777', lineHeight: '1.6'}}>
            Charts and visualization widgets for execution history and trends will be displayed here in a future update.
            <br /> (e.g., Success/Failure Rate Over Time, Most Frequent Failing Tests, Execution Duration Analysis, etc.)
          </p>
        </div>
      </div>
    </div>
  );
};

// AdminPage component
const AdminPage = () => {
    return (
        <div>
            <h2>Admin Area</h2>
            <p>This area is restricted to users with the 'admin' role.</p>
        </div>
    );
};

// ProtectedRoute component
const ProtectedRoute: React.FC<{ allowedRoles?: string[] }> = ({ allowedRoles }) => {
  const { user, isLoading, hasRole } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div style={{textAlign: 'center', padding: '50px'}}>Loading session...</div>;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.some(role => hasRole(role))) {
    return (
        <div style={{textAlign: 'center', padding: '50px'}}>
            <h1>Access Denied</h1>
            <p>You do not have the required permissions to view this page.</p>
            <Link to="/">Go to Dashboard</Link>
        </div>
    );
  }
  return <Outlet />;
};

// Main App component
function App() {
  const { user, isLoading, logout, hasRole } = useAuth();

  if (isLoading) {
    return (
      <div className="App">
        <header className="App-header">
           <h1>Test Orchestrator</h1>
        </header>
        <div style={{textAlign: 'center', padding: '50px', flexGrow: 1}}><h1>Loading Application...</h1></div>
      </div>
    );
  }

  return (
    <div className="App">
      <header className="App-header">
        <Link to="/" style={{color: 'white', textDecoration: 'none', fontSize: '1.5em', marginRight: 'auto'}}>Test Orchestrator</Link>
        {user && (
          <nav style={{display: 'flex', alignItems: 'center'}}>
            <Link to="/" className="nav-link">Dashboard</Link>
            <Link to="/executions" className="nav-link">Executions</Link>
            {(hasRole('editor') || hasRole('admin')) &&
              <Link to="/schedules" className="nav-link">Schedules</Link>
            }
            {hasRole('admin') && <Link to="/admin" className="nav-link admin-link">Admin</Link>}
            <span style={{color: '#ccc', marginRight: '15px', marginLeft: '15px'}}>Welcome, {user.username}!</span>
            <button onClick={logout} className="logout-button">Logout</button>
          </nav>
        )}
      </header>
      <main className="App-content">
        <Routes>
          <Route path="/login" element={!user ? <LoginPage /> : <Navigate to="/" />} />
          <Route path="/register" element={!user ? <RegisterPage /> : <Navigate to="/" />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/executions" element={<ExecutionsListPage />} />
            <Route path="/executions/:workflowId" element={<ExecutionDetailsPage />} />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={['editor', 'admin']} />}>
            <Route path="/schedules" element={<SchedulesPage />} />
          </Route>

          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/admin" element={<AdminPage />} />
          </Route>

          <Route path="*" element={<Navigate to={user ? "/" : "/login"} />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
