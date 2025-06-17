document.addEventListener('DOMContentLoaded', () => {
    // Existing selectors
    const modelsListContainer = document.getElementById('models-list-container');
    const downloadedModelsListContainer = document.getElementById('downloaded-models-list-container');
    const errorMessageContainer = document.getElementById('error-message-container');

    // Chat UI Selectors
    const chatModelSelect = document.getElementById('chat-model-select');
    const chatHistoryContainer = document.getElementById('chat-history-container');
    const chatPromptInput = document.getElementById('chat-prompt-input');
    const chatSendButton = document.getElementById('chat-send-button');
    const chatErrorMessageContainer = document.getElementById('chat-error-message-container');

    const API_BASE_URL = 'http://localhost:5000/api';
    let pollingIntervalId = null;
    let downloadedModelsCache = []; // Cache of downloaded models

    // --- Fetch Available Models (from model_registry.json) ---
    async function fetchModels() {
        try {
            const response = await fetch(`${API_BASE_URL}/models`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
            const models = await response.json();
            displayModels(models);
            updateAvailableModelsStatuses();
        } catch (error) {
            console.error('Failed to fetch available models:', error);
            errorMessageContainer.textContent = `Failed to load available models. Error: ${error.message}.`;
        }
    }

    // --- Display Available Models ---
    function displayModels(models) {
        modelsListContainer.innerHTML = '';
        if (!models || models.length === 0) {
            modelsListContainer.textContent = 'No models available in the registry.';
            return;
        }
        models.forEach(model => {
            const modelElement = document.createElement('div');
            modelElement.classList.add('model-item');
            modelElement.setAttribute('data-model-id', model.id);

            const nameElement = document.createElement('h3');
            nameElement.textContent = model.name;
            const descriptionElement = document.createElement('p');
            descriptionElement.textContent = `Description: ${model.description}`;
            const sizeElement = document.createElement('p');
            sizeElement.textContent = `Size: ${model.size}`;
            const formatElement = document.createElement('p');
            formatElement.textContent = `Format: ${model.format}`;
            const idElement = document.createElement('p');
            idElement.textContent = `ID: ${model.id}`;
            const downloadButton = document.createElement('button');
            downloadButton.textContent = 'Download';
            downloadButton.setAttribute('data-model-id', model.id);
            downloadButton.setAttribute('data-model-name', model.name);
            downloadButton.setAttribute('data-model-url', model.url);
            const statusSpan = document.createElement('span');
            statusSpan.classList.add('model-status');
            statusSpan.setAttribute('id', `status-${model.id}`);

            downloadButton.onclick = () => {
                initiateDownload(model.id, model.name, model.url, model.format, statusSpan, downloadButton);
            };
            modelElement.appendChild(nameElement);
            modelElement.appendChild(idElement);
            modelElement.appendChild(descriptionElement);
            modelElement.appendChild(sizeElement);
            modelElement.appendChild(formatElement);
            modelElement.appendChild(downloadButton);
            modelElement.appendChild(statusSpan);
            const hrElement = document.createElement('hr');
            modelElement.appendChild(hrElement);
            modelsListContainer.appendChild(modelElement);
        });
        updateAvailableModelsStatuses();
    }

    // --- Initiate Download ---
    async function initiateDownload(modelId, modelName, modelUrl, modelFormat, statusSpan, button) {
        statusSpan.textContent = 'Initiating...';
        button.disabled = true;
        button.textContent = 'Downloading...';
        try {
            const response = await fetch(`${API_BASE_URL}/models/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId, model_name: modelName, model_url: modelUrl, model_format: modelFormat })
            });
            const result = await response.json();
            if (response.status === 202) {
                statusSpan.textContent = 'Downloading...';
                if (!pollingIntervalId) startPolling(); else fetchDownloadedModels();
            } else if (response.status === 409) {
                statusSpan.textContent = result.details && result.details.status === 'completed' ? 'Already Downloaded' : 'Download in Progress';
                button.textContent = result.details && result.details.status === 'completed' ? 'Downloaded' : 'Downloading...';
                if (result.details && result.details.status === 'completed') button.disabled = true;
                fetchDownloadedModels();
            } else {
                const errorMsg = result.description || result.error || `Failed to initiate download. Status: ${response.status}`;
                throw new Error(errorMsg);
            }
        } catch (error) {
            console.error('Download initiation error:', error);
            statusSpan.textContent = `Error: ${error.message}`;
            button.disabled = false;
            button.textContent = 'Download';
        }
    }

    // --- Fetch Downloaded Models Information ---
    async function fetchDownloadedModels() {
        try {
            const response = await fetch(`${API_BASE_URL}/models/downloaded`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            downloadedModelsCache = await response.json();
            displayDownloadedModels(downloadedModelsCache);
            updateAvailableModelsStatuses();
            populateChatModelDropdown(downloadedModelsCache);
        } catch (error) {
            console.error('Failed to fetch downloaded models:', error);
            downloadedModelsListContainer.innerHTML = `<p style="color:red;">Error fetching downloaded models: ${error.message}</p>`;
        }
    }

    // --- Display Downloaded Models (with Delete Button) ---
    function displayDownloadedModels(downloadedModels) {
        downloadedModelsListContainer.innerHTML = '';
        if (!downloadedModels || downloadedModels.length === 0) {
            downloadedModelsListContainer.textContent = 'No models have been downloaded yet.';
            return;
        }
        downloadedModels.forEach(model => {
            const item = document.createElement('div');
            item.classList.add('model-item');

            let formatDisplay = model.format || 'Unknown';
            if(model.url && !model.url.includes('.') && !model.url.endsWith('.gguf')) formatDisplay = "HuggingFace";

            item.innerHTML = `
                <h3>${model.name} (ID: ${model.id})</h3>
                <p>File: ${model.file_name || 'N/A'}</p>
                <p>Path: ${model.path || 'N/A'}</p>
                <p>Status: <span class="download-status-${model.status}">${model.status}</span></p>
                <p>Format: ${formatDisplay}</p>
                <p>Date: ${model.download_date ? new Date(model.download_date).toLocaleString() : 'N/A'}</p>
                ${model.status === 'failed' && model.error ? `<p style="color:red;">Error: ${model.error}</p>` : ''}
            `;

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.classList.add('delete-model-button'); // For styling
            deleteButton.style.backgroundColor = '#dc3545'; // Red color for delete
            deleteButton.style.marginLeft = '10px';
            deleteButton.dataset.modelId = model.id; // Store modelId on the button

            deleteButton.onclick = (event) => {
                const modelIdToDelete = event.target.dataset.modelId;
                deleteModel(modelIdToDelete);
            };

            // Find a place to append the button, e.g., after the status or at the end of the item
            const statusParagraph = item.querySelector(`p:nth-of-type(3)`); // Assuming status is the 3rd <p>
            if (statusParagraph) {
                statusParagraph.appendChild(deleteButton);
            } else {
                item.appendChild(deleteButton); // Fallback
            }

            downloadedModelsListContainer.appendChild(item);
        });
    }

    // --- Delete Model ---
    async function deleteModel(modelId) {
        if (!window.confirm(`Are you sure you want to delete model "${modelId}"? This will remove its files.`)) {
            return;
        }

        // Optionally, provide visual feedback that deletion is in progress
        const modelItemDiv = downloadedModelsListContainer.querySelector(`.model-item h3:contains("${modelId}")`)?.closest('.model-item');
        if (modelItemDiv) {
            // This querySelector might not work directly like jQuery :contains.
            // A more robust way is to add data-model-id to the model-item div itself.
            // For now, just proceed with API call.
        }

        chatErrorMessageContainer.textContent = `Deleting model ${modelId}...`; // Use chat error for general messages

        try {
            const response = await fetch(`${API_BASE_URL}/models/delete/${modelId}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ description: response.statusText }));
                throw new Error(errorData.description || `Failed to delete model. Status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Delete successful:', result);
            chatErrorMessageContainer.textContent = `Model ${modelId} deleted successfully.`;
            fetchDownloadedModels(); // Refresh the list of downloaded models
        } catch (error) {
            console.error('Failed to delete model:', error);
            chatErrorMessageContainer.textContent = `Error deleting model ${modelId}: ${error.message}`;
        } finally {
            // Clear message after a delay
            setTimeout(() => { if(chatErrorMessageContainer.textContent.includes(`model ${modelId}`)) chatErrorMessageContainer.textContent = ''; }, 5000);
        }
    }

    // --- Update Statuses in Available Models List ---
    function updateAvailableModelsStatuses() {
        // ... (same as before)
        if (!downloadedModelsCache || downloadedModelsCache.length === 0) {
             // Clear statuses from available models if no models are downloaded
            const allAvailableModelItems = modelsListContainer.querySelectorAll('.model-item');
            allAvailableModelItems.forEach(item => {
                const statusSpan = item.querySelector('.model-status');
                const button = item.querySelector('button');
                if (statusSpan) statusSpan.textContent = '';
                if (button) {
                    button.textContent = 'Download';
                    button.disabled = false;
                }
            });
            return;
        }
        const downloadedIds = new Set(downloadedModelsCache.map(m => m.id));

        const allAvailableModelItems = modelsListContainer.querySelectorAll('.model-item');
        allAvailableModelItems.forEach(item => {
            const modelId = item.dataset.modelId;
            const statusSpan = item.querySelector('.model-status');
            const button = item.querySelector('button');
            const downloadedModel = downloadedModelsCache.find(m => m.id === modelId);

            if (downloadedModel) { // If this model ID is in the downloaded list
                if (downloadedModel.status === 'completed') {
                    statusSpan.textContent = 'Downloaded'; button.textContent = 'Downloaded'; button.disabled = true;
                } else if (downloadedModel.status === 'downloading') {
                    statusSpan.textContent = 'Downloading...'; button.textContent = 'Downloading...'; button.disabled = true;
                } else if (downloadedModel.status === 'failed') {
                    statusSpan.textContent = 'Download Failed'; button.textContent = 'Retry Download'; button.disabled = false;
                }
            } else { // If not in downloaded list
                 if (statusSpan) statusSpan.textContent = '';
                 if (button) {
                    button.textContent = 'Download';
                    button.disabled = false;
                 }
            }
        });
    }

    // --- Populate Chat Model Dropdown ---
    function populateChatModelDropdown(models) {
        // ... (same as before)
        const currentSelection = chatModelSelect.value;
        chatModelSelect.innerHTML = '<option value="">-- Select a model --</option>';
        models.forEach(model => {
            if (model.status === 'completed' && model.url && !model.url.includes('/') && !model.url.endsWith('.gguf') ) {
                 const option = document.createElement('option');
                 option.value = model.id;
                 option.textContent = `${model.name} (${model.id})`;
                 chatModelSelect.appendChild(option);
            }
        });
        if (Array.from(chatModelSelect.options).some(opt => opt.value === currentSelection)) {
            chatModelSelect.value = currentSelection;
        } else {
            chatModelSelect.value = ""; // Reset if selected model is no longer valid
        }
    }

    // --- Append Message to Chat History ---
    function appendMessageToChatHistory(message, sender) {
        // ... (same as before)
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message', `chat-message-${sender}`);
        messageDiv.textContent = message;
        chatHistoryContainer.appendChild(messageDiv);
        chatHistoryContainer.scrollTop = chatHistoryContainer.scrollHeight;
    }

    // --- Chat Send Button Event Listener ---
    chatSendButton.addEventListener('click', async () => {
        // ... (same as before)
        const selectedModelId = chatModelSelect.value;
        const promptText = chatPromptInput.value.trim();
        chatErrorMessageContainer.textContent = '';
        if (!selectedModelId) { chatErrorMessageContainer.textContent = 'Please select a model.'; return; }
        if (!promptText) { chatErrorMessageContainer.textContent = 'Please enter a prompt.'; return; }
        appendMessageToChatHistory(promptText, "user");
        chatPromptInput.value = '';
        chatSendButton.disabled = true;
        chatPromptInput.disabled = true;
        try {
            const response = await fetch(`${API_BASE_URL}/models/infer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: selectedModelId, prompt: promptText })
            });
            const result = await response.json();
            if (!response.ok) {
                const errorMsg = result.error || result.description || `Error: ${response.statusText}`;
                throw new Error(errorMsg);
            }
            appendMessageToChatHistory(result.generated_text, "model");
        } catch (error) {
            console.error('Inference error:', error);
            appendMessageToChatHistory(`Error: ${error.message}`, "model");
            chatErrorMessageContainer.textContent = `Error: ${error.message}`;
        } finally {
            chatSendButton.disabled = false;
            chatPromptInput.disabled = false;
            chatPromptInput.focus();
        }
    });

    // --- Polling ---
    function startPolling() {
        if (pollingIntervalId) clearInterval(pollingIntervalId);
        pollingIntervalId = setInterval(fetchDownloadedModels, 5000);
        fetchDownloadedModels();
    }

    // --- Initial Load ---
    fetchModels();
    startPolling();
});
