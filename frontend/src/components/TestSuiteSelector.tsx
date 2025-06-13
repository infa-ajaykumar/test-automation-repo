import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/apiService';
import DynamicForm from './DynamicForm'; // Import DynamicForm

interface Product {
  id: string;
  name: string;
  test_suites: string[]; // Array of test suite IDs
}

interface FormInputConfig { // Duplicating from DynamicForm for clarity, could be shared
  name: string;
  label: string;
  type: 'text' | 'dropdown' | 'number' | 'checkbox';
  required?: boolean;
  default_value?: any;
  source?: string;
  depends_on?: string;
  options?: Array<{ id: string; name: string }>;
}

interface TestSuite {
  id: string;
  name: string;
  description?: string;
  inputs: FormInputConfig[];
  // ... other test suite properties
}

const TestSuiteSelector: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string>('');

  const [allTestSuites, setAllTestSuites] = useState<TestSuite[]>([]);
  const [availableTestSuites, setAvailableTestSuites] = useState<TestSuite[]>([]);
  const [selectedSuiteId, setSelectedSuiteId] = useState<string>('');
  const [selectedSuiteConfig, setSelectedSuiteConfig] = useState<TestSuite | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const { token, logout } = useAuth();

  // Fetch products
  useEffect(() => {
    if (!token) return;
    setError(null); // Clear previous errors
    apiService.getConfigData('products', token)
      .then(response => {
        if (Array.isArray(response.data)) {
          setProducts(response.data);
        } else {
          setError("Products data is not in expected format.");
          setProducts([]); // Clear products if format is wrong
        }
      })
      .catch(err => {
        console.error("Error fetching products:", err);
        if (err.response?.status === 401) logout();
        setError("Failed to fetch products.");
      });

    // Fetch all test suites once
    apiService.getConfigData('test_suites', token)
      .then(response => {
        if (Array.isArray(response.data)) {
          setAllTestSuites(response.data);
        } else {
          setError("Test suites data is not in expected format.");
          setAllTestSuites([]);
        }
      })
      .catch(err => {
        console.error("Error fetching test suites:", err);
        if (err.response?.status === 401) logout();
        setError("Failed to fetch all test suites.");
      });
  }, [token, logout]);

  // Update available test suites when product changes
  useEffect(() => {
    setSelectedSuiteId('');
    setSelectedSuiteConfig(null);
    if (selectedProductId && products.length > 0 && allTestSuites.length > 0) {
      const product = products.find(p => p.id === selectedProductId);
      if (product && product.test_suites) { // Ensure product.test_suites exists
        const suiteIdsForProduct = product.test_suites;
        const filteredSuites = allTestSuites.filter(suite => suiteIdsForProduct.includes(suite.id));
        setAvailableTestSuites(filteredSuites);
      } else {
        setAvailableTestSuites([]);
      }
    } else {
      setAvailableTestSuites([]);
    }
  }, [selectedProductId, products, allTestSuites]);

  // Set selected suite config when suite ID changes
  useEffect(() => {
    if (selectedSuiteId) {
      const suite = allTestSuites.find(s => s.id === selectedSuiteId);
      setSelectedSuiteConfig(suite || null);
    } else {
      setSelectedSuiteConfig(null);
    }
  }, [selectedSuiteId, allTestSuites]);

  const handleFormSubmit = async (formData: Record<string, any>) => {
    if (!token || !selectedSuiteConfig) {
      setError("Cannot submit: missing token or suite configuration.");
      return;
    }
    setIsSubmitting(true);
    setWorkflowStatus(null);
    setError(null);
    try {
      const response = await apiService.startWorkflow(selectedSuiteConfig.id, formData, token);
      setWorkflowStatus(`Workflow started successfully! ID: ${response.data.workflow_id}. Message: ${response.data.message}`);
    } catch (err: any) {
      console.error("Error starting workflow:", err);
      setError(err.response?.data?.detail || "Failed to start workflow.");
      if (err.response?.status === 401) logout();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <h2>Select Test Suite to Execute</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}

      <div>
        <label htmlFor="product-select" style={{ marginRight: '5px' }}>Product:</label>
        <select
          id="product-select"
          value={selectedProductId}
          onChange={e => setSelectedProductId(e.target.value)}
          style={{ margin: '10px 0', padding: '8px', minWidth: '200px' }}
        >
          <option value="">-- Select Product --</option>
          {products.map(product => (
            <option key={product.id} value={product.id}>{product.name}</option>
          ))}
        </select>
      </div>

      {selectedProductId && (availableTestSuites.length > 0 ? (
        <div>
          <label htmlFor="suite-select" style={{ marginRight: '5px' }}>Test Suite:</label>
          <select
            id="suite-select"
            value={selectedSuiteId}
            onChange={e => setSelectedSuiteId(e.target.value)}
            style={{ margin: '10px 0', padding: '8px', minWidth: '200px' }}
          >
            <option value="">-- Select Test Suite --</option>
            {availableTestSuites.map(suite => (
              <option key={suite.id} value={suite.id}>{suite.name}</option>
            ))}
          </select>
        </div>
      ) : <p>No test suites available for the selected product, or test suites are still loading.</p>)}


      {selectedSuiteConfig && selectedSuiteConfig.inputs && (
        <DynamicForm
          suiteId={selectedSuiteConfig.id}
          inputsConfig={selectedSuiteConfig.inputs}
          onSubmit={handleFormSubmit}
          isSubmitting={isSubmitting}
        />
      )}

      {workflowStatus && <p style={{ color: 'green' }}>{workflowStatus}</p>}
    </div>
  );
};

export default TestSuiteSelector;
