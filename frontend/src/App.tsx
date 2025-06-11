import React from 'react';
import './App.css';
import TestRunnerForm from './components/TestRunnerForm'; // Uncommented

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Test Suite Orchestrator</h1>
      </header>
      <main>
        <TestRunnerForm /> {/* Use the form here */}
      </main>
      <footer className="App-footer">
        <p>&copy; {new Date().getFullYear()} Test Orchestration System</p>
      </footer>
    </div>
  );
}

export default App;
