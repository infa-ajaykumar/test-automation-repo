from flask import Flask, jsonify, abort, request
import json
import os
import requests
import threading
import datetime
from urllib.parse import urlparse
import shutil # Added for directory deletion

# Attempt to import transformers, will fail if not installed but endpoint won't be hit without install
try:
    from transformers import pipeline
except ImportError:
    pipeline = None # Placeholder if transformers is not installed

app = Flask(__name__)

# --- Constants and Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Construct MODELS_DIR path relative to the project root (one level up from BASE_DIR)
PROJECT_ROOT = os.path.dirname(BASE_DIR)
MODELS_DIR = os.path.join(PROJECT_ROOT, 'models')
MODEL_REGISTRY_PATH = os.path.join(BASE_DIR, 'model_registry.json')
DOWNLOADED_MODELS_INFO_PATH = os.path.join(MODELS_DIR, 'models_downloaded.json')

DOWNLOAD_LOCK = threading.Lock()
MODEL_CACHE_LOCK = threading.Lock()
loaded_models_cache = {}

# --- Initialization ---
def initialize_app():
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)
        print(f"Created directory: {MODELS_DIR}")
    if not os.path.exists(DOWNLOADED_MODELS_INFO_PATH):
        with open(DOWNLOADED_MODELS_INFO_PATH, 'w') as f:
            json.dump([], f)
        print(f"Initialized file: {DOWNLOADED_MODELS_INFO_PATH}")

initialize_app()

# --- Helper Functions ---
def _read_downloaded_models_json_unsafe():
    """Reads the JSON file without lock. Caller must handle locking."""
    if not os.path.exists(DOWNLOADED_MODELS_INFO_PATH):
        return []
    try:
        with open(DOWNLOADED_MODELS_INFO_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: Corrupted or empty {DOWNLOADED_MODELS_INFO_PATH}")
        return []

def _write_downloaded_models_json_unsafe(data):
    """Writes the JSON file without lock. Caller must handle locking."""
    with open(DOWNLOADED_MODELS_INFO_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def get_downloaded_models_data():
    """Safely reads and returns data from models_downloaded.json."""
    with DOWNLOAD_LOCK:
        return _read_downloaded_models_json_unsafe()

def update_downloaded_models_data(new_entry_data, model_id_to_update=None):
    """Safely adds or updates an entry in models_downloaded.json."""
    with DOWNLOAD_LOCK:
        current_data = _read_downloaded_models_json_unsafe()

        if model_id_to_update:
            entry_found_and_updated = False
            for i, entry in enumerate(current_data):
                if entry.get("id") == model_id_to_update:
                    entry.update(new_entry_data) # Merge updates
                    entry_found_and_updated = True
                    break
            if not entry_found_and_updated:
                # If trying to update a non-existent ID, add it as a new entry.
                # This handles the case where an initial "downloading" entry might not exist yet.
                new_entry_with_id = {"id": model_id_to_update}
                new_entry_with_id.update(new_entry_data)
                current_data.append(new_entry_with_id)
        else: # New entry, expect 'id' to be in new_entry_data
            is_existing = False
            for i, entry in enumerate(current_data):
                if entry.get("id") == new_entry_data.get("id"):
                    current_data[i].update(new_entry_data)
                    is_existing = True
                    break
            if not is_existing:
                current_data.append(new_entry_data)

        _write_downloaded_models_json_unsafe(current_data)

def remove_downloaded_model_entry(model_id_to_remove):
    """Safely removes an entry from models_downloaded.json."""
    with DOWNLOAD_LOCK:
        current_data = _read_downloaded_models_json_unsafe()
        updated_data = [entry for entry in current_data if entry.get("id") != model_id_to_remove]

        if len(current_data) == len(updated_data):
            return False # Entry not found

        _write_downloaded_models_json_unsafe(updated_data)
        return True


def get_file_extension(url, default_extension="gguf"):
    try:
        path = urlparse(url).path
        ext = os.path.splitext(path)[1]
        return ext[1:] if ext else default_extension
    except Exception:
        return default_extension

def download_model_thread(model_id, model_name, model_url):
    print(f"Download thread started for {model_name} (ID: {model_id}) from {model_url}")
    initial_entry_data = {
        "name": model_name, "file_name": "N/A", "path": "N/A",
        "download_date": datetime.datetime.utcnow().isoformat() + "Z",
        "status": "downloading", "url": model_url
    }
    update_downloaded_models_data(initial_entry_data, model_id_to_update=model_id)

    file_extension = get_file_extension(model_url)
    is_hf_model = not bool(os.path.splitext(urlparse(model_url).path)[1]) and file_extension not in ['gguf', 'bin', 'pth', 'onnx']

    if is_hf_model:
        print(f"Model {model_id} identified as HF model ID. Path will be a directory.")
        dir_name = model_id
        actual_model_dir_path = os.path.join(MODELS_DIR, dir_name)
        json_path_field = os.path.join('models', dir_name).replace(os.sep, '/')

        os.makedirs(actual_model_dir_path, exist_ok=True)
        print(f"Directory {actual_model_dir_path} ensured for HF model {model_id}.")
        status_update_data = {"status": "completed", "file_name": dir_name, "path": json_path_field, "name":model_name, "url":model_url}
        update_downloaded_models_data(status_update_data, model_id_to_update=model_id)
        print(f"HF Model {model_id} registered. Files expected at {actual_model_dir_path}.")
        return

    file_name_single = f"{model_id}.{file_extension}"
    file_path_single = os.path.join(MODELS_DIR, file_name_single)
    try:
        os.makedirs(MODELS_DIR, exist_ok=True)
        with requests.get(model_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(file_path_single, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192 * 16):
                    f.write(chunk)
        print(f"Successfully downloaded {file_name_single}")
        status_update_data = {
            "status": "completed", "file_name": file_name_single,
            "path": os.path.join('models', file_name_single).replace(os.sep, '/'),
            "name":model_name, "url":model_url
        }
        update_downloaded_models_data(status_update_data, model_id_to_update=model_id)
    except Exception as e:
        print(f"Failed to download {model_name} (ID: {model_id}). Error: {str(e)}")
        error_update_data = {"status": "failed", "error": str(e), "file_name": file_name_single, "name":model_name, "url":model_url}
        update_downloaded_models_data(error_update_data, model_id_to_update=model_id)

# --- API Endpoints ---
@app.route('/api/models', methods=['GET'])
def get_models_registry():
    # ... (endpoint code remains the same)
    if not os.path.exists(MODEL_REGISTRY_PATH):
        abort(404, description="Model registry not found.")
    try:
        with open(MODEL_REGISTRY_PATH, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        abort(500, description=f"Error reading model registry: {str(e)}")

@app.route('/api/models/download', methods=['POST'])
def download_model_endpoint():
    # ... (endpoint code remains largely the same)
    data = request.get_json()
    model_id = data.get('model_id')
    model_name = data.get('model_name')
    model_url = data.get('model_url')

    if not all([model_id, model_name, model_url]):
        abort(400, description="Missing model_id, model_name, or model_url in request.")

    downloaded_data = get_downloaded_models_data()
    for entry in downloaded_data:
        if entry['id'] == model_id and entry['status'] == 'completed':
            return jsonify({"status": "already_downloaded", "model_id": model_id, "details": entry}), 409
        if entry['id'] == model_id and entry['status'] == 'downloading':
            return jsonify({"status": "download_in_progress", "model_id": model_id, "details": entry}), 409

    thread = threading.Thread(target=download_model_thread, args=(model_id, model_name, model_url))
    thread.start()
    return jsonify({"status": "download_initiated", "model_id": model_id}), 202


@app.route('/api/models/downloaded', methods=['GET'])
def list_downloaded_models():
    # ... (endpoint code remains the same)
    data = get_downloaded_models_data()
    return jsonify(data)

@app.route('/api/models/download/status/<string:model_id>', methods=['GET'])
def get_download_status(model_id):
    # ... (endpoint code remains the same)
    data = get_downloaded_models_data()
    for entry in data:
        if entry.get('id') == model_id:
            return jsonify(entry)
    return jsonify({"status": "not_found", "model_id": model_id}), 404

@app.route('/api/models/infer', methods=['POST'])
def infer_model_endpoint():
    # ... (endpoint code remains largely the same)
    if pipeline is None:
        return jsonify({"error": "Transformers library not installed or failed to import."}), 501

    payload = request.get_json()
    model_id = payload.get('model_id')
    prompt = payload.get('prompt')
    max_new_tokens = payload.get('max_new_tokens', 50)

    if not model_id or not prompt:
        abort(400, description="Missing 'model_id' or 'prompt' in request.")

    downloaded_models = get_downloaded_models_data()
    model_info = next((m for m in downloaded_models if m.get('id') == model_id and m.get('status') == 'completed'), None)

    if not model_info:
        return jsonify({"error": f"Model '{model_id}' not found or not successfully downloaded."}), 404

    hf_model_identifier_or_path = model_info.get('path')

    if hf_model_identifier_or_path.startswith("models/"):
        model_dir_name = os.path.basename(hf_model_identifier_or_path)
        actual_model_load_path = os.path.join(MODELS_DIR, model_dir_name)
        print(f"Constructed path for local HF model: {actual_model_load_path}")
    else:
        actual_model_load_path = hf_model_identifier_or_path
        print(f"Using HF model identifier: {actual_model_load_path}")

    cached_pipeline = None
    with MODEL_CACHE_LOCK:
        if model_id in loaded_models_cache:
            cached_pipeline = loaded_models_cache[model_id]
            print(f"Using cached model: {model_id}")
        else:
            print(f"Loading model: {model_id} from {actual_model_load_path}...")
            try:
                loaded_pipeline = pipeline("text-generation", model=actual_model_load_path, tokenizer=actual_model_load_path, device=-1)
                loaded_models_cache[model_id] = loaded_pipeline
                cached_pipeline = loaded_pipeline
                print(f"Model {model_id} loaded and cached.")
            except Exception as e:
                print(f"Error loading model {model_id} from {actual_model_load_path}: {str(e)}")
                return jsonify({"error": f"Failed to load model {model_id}: {str(e)}"}), 500

    if not cached_pipeline:
        return jsonify({"error": "Model pipeline not available after loading attempt."}), 500

    try:
        print(f"Running inference for model {model_id} with prompt: '{prompt[:50]}...'")
        generated_outputs = cached_pipeline(prompt, max_new_tokens=max_new_tokens)

        if generated_outputs and isinstance(generated_outputs, list) and generated_outputs[0].get("generated_text"):
            extracted_text = generated_outputs[0]["generated_text"]
        else:
            extracted_text = "No text generated or unexpected output format."
            print(f"Unexpected output format from pipeline: {generated_outputs}")

        print(f"Inference completed for model {model_id}.")
        return jsonify({
            "model_id": model_id,
            "prompt": prompt,
            "generated_text": extracted_text
        })
    except Exception as e:
        print(f"Error during inference with model {model_id}: {str(e)}")
        return jsonify({"error": f"Inference error with model {model_id}: {str(e)}"}), 500

# --- New Delete Endpoint ---
@app.route('/api/models/delete/<string:model_id>', methods=['DELETE'])
def delete_model_endpoint(model_id):
    downloaded_models = get_downloaded_models_data() # Reads with lock
    model_entry = next((entry for entry in downloaded_models if entry.get("id") == model_id), None)

    if not model_entry:
        abort(404, description=f"Model with ID '{model_id}' not found in downloaded models list.")

    # Path from JSON is like "models/model_id.gguf" or "models/model_id_hf_dir"
    # It's relative to PROJECT_ROOT already.
    # MODELS_DIR is PROJECT_ROOT/models.
    # So, if entry['path'] is "models/foo", full path is PROJECT_ROOT/models/foo
    # which is os.path.join(PROJECT_ROOT, entry['path'])
    # Or, more simply, os.path.join(MODELS_DIR, os.path.basename(entry['path']))

    path_from_json = model_entry.get('path')
    if not path_from_json:
        # If path is somehow missing, we can't delete fs objects but can still remove from JSON
        print(f"Warning: Path missing for model {model_id}. Will only remove from JSON.")
    else:
        # Construct full path for deletion.
        # Assuming path_from_json is like "models/model_file_or_dir_name"
        # MODELS_DIR is ProjectRoot/models
        # So, the actual file/dir name is os.path.basename(path_from_json)
        target_name_in_models_dir = os.path.basename(path_from_json)
        full_path_to_delete = os.path.join(MODELS_DIR, target_name_in_models_dir)

        print(f"Attempting to delete filesystem object: {full_path_to_delete}")
        try:
            if os.path.exists(full_path_to_delete):
                if os.path.isfile(full_path_to_delete) or os.path.islink(full_path_to_delete):
                    os.remove(full_path_to_delete)
                    print(f"File {full_path_to_delete} deleted.")
                elif os.path.isdir(full_path_to_delete):
                    shutil.rmtree(full_path_to_delete)
                    print(f"Directory {full_path_to_delete} deleted.")
                else:
                    print(f"Warning: {full_path_to_delete} is not a file or directory. Skipping deletion.")
            else:
                print(f"Warning: Path {full_path_to_delete} not found. Skipping deletion.")
        except Exception as e:
            print(f"Error deleting {full_path_to_delete}: {str(e)}")
            # Decide if this is fatal. For now, continue to remove from JSON and cache.
            # abort(500, description=f"Failed to delete model files for {model_id}: {str(e)}")
            # For a more robust system, you might want to stop here or mark for cleanup.


    # Update models_downloaded.json
    if not remove_downloaded_model_entry(model_id):
        # This means entry was not found by remove_downloaded_model_entry,
        # which shouldn't happen if we found it earlier. Could indicate race condition if locks are imperfect.
        print(f"Warning: Model ID {model_id} not found by remove_downloaded_model_entry, though found initially.")
        # abort(500, description=f"Failed to update models_downloaded.json for {model_id}, consistency issue.")

    # Unload from Inference Cache
    with MODEL_CACHE_LOCK:
        if model_id in loaded_models_cache:
            print(f"Unloading model {model_id} from inference cache.")
            del loaded_models_cache[model_id]
            # TODO: Consider more explicit cleanup if model objects need it (e.g., release GPU memory with torch.cuda.empty_cache())
            # For CPU models with transformers pipeline, 'del' should be mostly sufficient for Python's GC.

    return jsonify({"status": "deleted", "model_id": model_id}), 200


if __name__ == '__main__':
    print(f"PROJECT_ROOT set to: {PROJECT_ROOT}")
    print(f"MODELS_DIR set to: {MODELS_DIR}")
    print(f"DOWNLOADED_MODELS_INFO_PATH set to: {DOWNLOADED_MODELS_INFO_PATH}")
    app.run(debug=True, use_reloader=False)
