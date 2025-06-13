import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext'; // For token
import apiService from '../services/apiService'; // For fetching source data

interface FormInputConfig {
  name: string;
  label: string;
  type: 'text' | 'dropdown' | 'number' | 'checkbox'; // Add more types as needed
  required?: boolean;
  default_value?: any;
  source?: string; // e.g., "csps.yaml" (filename without extension)
  depends_on?: string; // Name of another field this one depends on
  options?: Array<{ id: string; name: string }>; // Static options if no source
}

interface DynamicFormProps {
  suiteId: string;
  inputsConfig: FormInputConfig[];
  onSubmit: (formData: Record<string, any>) => void;
  isSubmitting: boolean; // To disable button during submission
}

const DynamicForm: React.FC<DynamicFormProps> = ({ suiteId, inputsConfig, onSubmit, isSubmitting }) => {
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [sourceDataCache, setSourceDataCache] = useState<Record<string, Array<{ id: string; name: string }>>>({});
  const { token } = useAuth();

  // Initialize form data with default values
  useEffect(() => {
    const initialData: Record<string, any> = {};
    inputsConfig.forEach(input => {
      if (input.default_value !== undefined) {
        initialData[input.name] = input.default_value;
      } else if (input.type === 'checkbox') {
        initialData[input.name] = false; // Default for checkbox
      } else {
        initialData[input.name] = ''; // Default for others
      }
    });
    setFormData(initialData);
  }, [inputsConfig, suiteId]); // Re-initialize if suite changes

  // Fetch source data for dropdowns
  useEffect(() => {
    if (!token) return;

    const fetchSource = async (sourceName: string) => {
      if (sourceDataCache[sourceName]) return; // Already fetched or fetching

      try {
        // Mark as fetching to avoid re-fetch, even if it fails
        setSourceDataCache(prev => ({ ...prev, [sourceName]: [] }));
        const response = await apiService.getConfigData(sourceName.replace(".yaml", ""), token); // remove .yaml if present
        // Assuming response.data is Array<{id: string, name: string}>
        if (Array.isArray(response.data)) {
          setSourceDataCache(prev => ({ ...prev, [sourceName]: response.data }));
        } else {
          console.error(`Source data for ${sourceName} is not an array:`, response.data);
        }
      } catch (error) {
        console.error(`Failed to fetch source data for ${sourceName}:`, error);
        // Keep it as empty array in cache to avoid retrying constantly on error
      }
    };

    inputsConfig.forEach(input => {
      if (input.type === 'dropdown' && input.source && !sourceDataCache[input.source]) {
        fetchSource(input.source);
      }
    });
  }, [inputsConfig, token, sourceDataCache]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;

    let processedValue = value;
    if (type === 'checkbox') {
      processedValue = (e.target as HTMLInputElement).checked ? true : false;
    } else if (type === 'number') {
      processedValue = value === '' ? '' : Number(value);
    }

    setFormData(prev => ({ ...prev, [name]: processedValue }));
  };

  const getDropdownOptions = useCallback((inputConfig: FormInputConfig): Array<{ id: string; name: string }> => {
    if (inputConfig.options) return inputConfig.options;
    if (!inputConfig.source) return [];

    let options = sourceDataCache[inputConfig.source] || [];

    // Handle depends_on filtering (e.g., regions by csp)
    if (inputConfig.depends_on && formData[inputConfig.depends_on]) {
      const dependentValue = formData[inputConfig.depends_on];
      // This assumes the source items have a field matching the depends_on field name, e.g. item.csp
      // The source items are expected to be {id: '...', name: '...', csp: '...'} for regions.yaml
      options = options.filter(option => (option as any)[inputConfig.depends_on!] === dependentValue);
    }
    return options;
  }, [sourceDataCache, formData]);


  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      <h3>Inputs for {suiteId}</h3>
      {inputsConfig.map(input => (
        <div key={input.name} style={{ marginBottom: '10px' }}>
          <label htmlFor={input.name} style={{ display: 'block', marginBottom: '5px' }}>
            {input.label}{input.required ? '*' : ''}:
          </label>
          {input.type === 'dropdown' ? (
            <select
              id={input.name}
              name={input.name}
              value={formData[input.name] || ''}
              onChange={handleChange}
              required={input.required}
              style={{width: '100%', padding: '8px', boxSizing: 'border-box'}}
            >
              <option value="">-- Select {input.label} --</option>
              {getDropdownOptions(input).map(option => (
                <option key={option.id} value={option.id}>{option.name}</option>
              ))}
            </select>
          ) : input.type === 'checkbox' ? (
             <input
              type="checkbox"
              id={input.name}
              name={input.name}
              checked={formData[input.name] === true}
              onChange={handleChange}
              style={{padding: '8px'}}
            />
          ) : (
            <input
              type={input.type}
              id={input.name}
              name={input.name}
              value={formData[input.name] || ''}
              onChange={handleChange}
              required={input.required}
              style={{width: '100%', padding: '8px', boxSizing: 'border-box'}}
            />
          )}
        </div>
      ))}
      <button type="submit" disabled={isSubmitting} style={{marginTop: '15px', padding: '10px 15px'}}>
        {isSubmitting ? 'Starting Workflow...' : 'Start Test Suite'}
      </button>
    </form>
  );
};

export default DynamicForm;
