import React, { useState, FormEvent } from 'react';
import './TestRunnerForm.css';

interface FormData {
  csp: string;
  region: string;
  product: string;
  pod: string;
  environment: string;
  testsuite_type: string;
}

const cspOptions = ["AWS", "Azure", "GCP", "Other"];
const regionOptions = {
  AWS: ["us-east-1", "us-west-2", "eu-central-1"],
  Azure: ["East US", "West Europe", "Southeast Asia"],
  GCP: ["us-central1", "europe-west1", "asia-east1"],
  Other: ["N/A"],
};
const environmentOptions = ["dev", "staging", "prod", "uat"];
const testsuiteTypeOptions = ["smoke", "functional", "performance", "integration", "security"];

// Define the expected structure of a successful API response
interface ApiResponseSuccess {
  message: string;
  workflow_id: string;
  run_id: string;
}

// Define the expected structure of an API error response (from FastAPI's HTTPException)
interface ApiResponseError {
  detail: string | { msg: string; type: string }[]; // FastAPI can return string or list of errors
}

const TestRunnerForm: React.FC = () => {
  const [formData, setFormData] = useState<FormData>({
    csp: 'AWS',
    region: regionOptions['AWS'][0],
    product: 'DemoProduct', // Pre-filled for easier testing
    pod: '',
    environment: 'dev',
    testsuite_type: 'smoke', // Pre-filled for easier testing
  });
  const [responseMessage, setResponseMessage] = useState<string | null>(null);
  const [errorResponseMessage, setErrorResponseMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const newState = { ...prev, [name]: value };
      if (name === 'csp') {
        const newCsp = value as keyof typeof regionOptions;
        newState.region = regionOptions[newCsp]?.[0] || '';
      }
      return newState;
    });
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    setResponseMessage(null);
    setErrorResponseMessage(null);

    // The backend API endpoint
    const apiUrl = '/api/trigger-test'; // Using relative URL for proxying (dev) or same-origin (prod)

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json', // Important for FastAPI to know client expects JSON
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        // Try to parse error response from FastAPI
        const errorData: ApiResponseError = await response.json();
        let detailMessage = "An unknown error occurred.";
        if (typeof errorData.detail === 'string') {
            detailMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
            // Handle validation errors (list of error objects)
            detailMessage = errorData.detail.map(err => `${err.type}: ${err.msg}`).join(', ');
        } else if (typeof errorData.detail === 'object' && errorData.detail !== null) {
            // Handle other structured error details if any
            detailMessage = JSON.stringify(errorData.detail);
        }
        throw new Error(`HTTP error ${response.status}: ${detailMessage}`);
      }

      const result: ApiResponseSuccess = await response.json();
      setResponseMessage(`${result.message}. Workflow ID: ${result.workflow_id}, Run ID: ${result.run_id}`);

    } catch (error) {
      console.error("Submission error:", error);
      if (error instanceof Error) {
        setErrorResponseMessage(error.message);
      } else {
        setErrorResponseMessage("An unexpected error occurred during submission.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const currentRegionOptions = regionOptions[formData.csp as keyof typeof regionOptions] || [];

  return (
    <div className="test-runner-form-container">
      <h2>Trigger New Test Suite</h2>
      <form onSubmit={handleSubmit} className="test-runner-form">
        {/* CSP Dropdown */}
        <div className="form-group">
          <label htmlFor="csp">CSP:</label>
          <select id="csp" name="csp" value={formData.csp} onChange={handleChange} required>
            {cspOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </div>

        {/* Region Dropdown */}
        <div className="form-group">
          <label htmlFor="region">Region:</label>
          <select id="region" name="region" value={formData.region} onChange={handleChange} required disabled={currentRegionOptions.length === 0}>
            {currentRegionOptions.map(option => <option key={option} value={option}>{option}</option>)}
            {currentRegionOptions.length === 0 && <option value="">Select CSP first</option>}
          </select>
        </div>

        {/* Product Input */}
        <div className="form-group">
          <label htmlFor="product">Product:</label>
          <input type="text" id="product" name="product" value={formData.product} onChange={handleChange} required placeholder="e.g., MyAwesomeApp"/>
        </div>

        {/* Pod Input */}
        <div className="form-group">
          <label htmlFor="pod">Pod (Optional):</label>
          <input type="text" id="pod" name="pod" value={formData.pod} onChange={handleChange} placeholder="e.g., pod-123a"/>
        </div>

        {/* Environment Dropdown */}
        <div className="form-group">
          <label htmlFor="environment">Environment:</label>
          <select id="environment" name="environment" value={formData.environment} onChange={handleChange} required>
            {environmentOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </div>

        {/* Test Suite Type Dropdown */}
        <div className="form-group">
          <label htmlFor="testsuite_type">Test Suite Type:</label>
          <select id="testsuite_type" name="testsuite_type" value={formData.testsuite_type} onChange={handleChange} required>
            {testsuiteTypeOptions.map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </div>

        <button type="submit" className="submit-button" disabled={isLoading}>
          {isLoading ? 'Submitting...' : 'Submit Test Suite'}
        </button>
      </form>
      {isLoading && <p className="loading-message">Submitting test workflow...</p>}
      {responseMessage && <div className="response-message success">{responseMessage}</div>}
      {errorResponseMessage && <div className="response-message error">{errorResponseMessage}</div>}
    </div>
  );
};

export default TestRunnerForm;
