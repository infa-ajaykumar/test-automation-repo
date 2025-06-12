from fastapi import FastAPI, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import yaml
import os
from pathlib import Path
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext

# Temporal Client Imports
from temporalio.client import Client, WorkflowExecutionDescription, WorkflowFailureError
from temporalio.exceptions import WorkflowAlreadyStartedError
import httpx # For consistency, though not directly used by FastAPI client here

# --- Configuration ---
CONFIG_PATH = Path("../config")
SECRET_KEY = "YOUR_VERY_SECRET_KEY"  # CHANGE THIS IN PRODUCTION!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(title="Test Orchestration API")

# --- Temporal Client Setup ---
temporal_client: Optional[Client] = None

@app.on_event("startup")
async def startup_event():
    global temporal_client
    try:
        temporal_client = await Client.connect("localhost:7233")
        print("Successfully connected to Temporal server for workflow initiation.")
    except Exception as e:
        print(f"Failed to connect to Temporal server on startup: {e}")
        temporal_client = None

@app.on_event("shutdown")
async def shutdown_event():
    if temporal_client:
        await temporal_client.close()
        print("Temporal client connection closed.")

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# --- Models ---
class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    roles: List[str] = ["viewer"]

class UserInDBBase(UserBase):
    id: int
    roles: List[str] = ["viewer"]
    class Config:
        orm_mode = True

class UserInDB(UserInDBBase):
    hashed_password: str

class UserPublic(UserInDBBase):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    roles: List[str] = []

# Models for Workflow Execution
class TestSuiteExecutionRequest(BaseModel):
    suite_id: str = Field(..., description="The ID of the test suite to execute, e.g., 'suite_login'")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Key-value pairs for test inputs, e.g., {'username': 'test01'}")

class WorkflowStartResponse(BaseModel):
    workflow_id: str
    message: str

# --- Dummy User DB (ID-based) ---
fake_users_db: Dict[int, UserInDB] = {}
next_user_id = 1
initial_admin_username = "admin" # Used in user registration logic
initial_admin_email = "admin@example.com"
initial_admin_hashed_password = get_password_hash("adminpassword")
fake_users_db[next_user_id] = UserInDB(
    id=next_user_id, username=initial_admin_username, email=initial_admin_email,
    full_name="Admin User", hashed_password=initial_admin_hashed_password,
    roles=["admin", "editor", "viewer"]
)
next_user_id += 1

# --- Authentication & Authorization ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_user_by_username(username: str) -> Optional[UserInDB]:
    for user in fake_users_db.values():
        if user.username == username:
            return user
    return None

async def get_user_by_id(user_id: int) -> Optional[UserInDB]:
    return fake_users_db.get(user_id)

async def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = await get_user_by_username(username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        # roles: List[str] = payload.get("roles", []) # Roles from token if needed
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired", headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError:
        raise credentials_exception

    user = await get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    return current_user # Add disabled check if UserInDB gets a 'disabled' field

def require_role(required_role: str):
    async def role_checker(user: UserInDB = Depends(get_current_active_user)):
        if required_role not in user.roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"User lacks '{required_role}' role.")
        return user
    return role_checker

require_admin = require_role("admin")
require_editor = require_role("editor")
require_viewer = require_role("viewer")

# --- Helper for loading Test Suite Config ---
def get_suite_config_sync(suite_id: str) -> Optional[Dict[str, Any]]:
    file_path = CONFIG_PATH / "test_suites.yaml"
    if not file_path.exists(): return None
    try:
        with open(file_path, 'r') as f:
            all_suites = yaml.safe_load(f)
            if not all_suites: return None
            for suite in all_suites:
                if isinstance(suite, dict) and suite.get("id") == suite_id:
                    return suite
    except Exception: return None # Log error
    return None

# --- API Endpoints ---
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    token_data = {"sub": user.username, "roles": user.roles}
    return {"access_token": create_access_token(token_data), "token_type": "bearer"}

@app.post("/users/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate):
    global next_user_id
    if await get_user_by_username(user_in.username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already registered")
    if user_in.email and any(u.email == user_in.email for u in fake_users_db.values()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    new_user = UserInDB(
        id=next_user_id, username=user_in.username, email=user_in.email,
        full_name=user_in.full_name, roles=user_in.roles or ["viewer"],
        hashed_password=get_password_hash(user_in.password)
    )
    fake_users_db[next_user_id] = new_user
    next_user_id += 1
    return UserPublic.from_orm(new_user)

@app.get("/users/me", response_model=UserPublic)
async def read_users_me(user: UserInDB = Depends(get_current_active_user)):
    return UserPublic.from_orm(user)

@app.get("/users", response_model=List[UserPublic], dependencies=[Depends(require_admin)])
async def list_users():
    return [UserPublic.from_orm(u) for u in fake_users_db.values()]

@app.put("/users/{user_id}/roles", response_model=UserPublic, dependencies=[Depends(require_admin)])
async def update_user_roles(user_id: int, roles: List[str] = Body(..., embed=True)):
    user = await get_user_by_id(user_id)
    if not user: raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not roles: raise HTTPException(status.HTTP_400_BAD_REQUEST, "Roles list cannot be empty.")
    valid_roles = {"admin", "editor", "viewer"}
    if any(r not in valid_roles for r in roles):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid roles. Valid: {valid_roles}")
    user.roles = list(set(roles))
    return UserPublic.from_orm(user)

@app.get("/")
async def read_root(): return {"message": "Welcome to the Test Orchestration API"}

@app.get("/api/v1/configs/{config_name}", response_model=List[Dict[str, Any]], dependencies=[Depends(require_viewer)])
async def get_configuration_file(config_name: str, user: UserInDB = Depends(get_current_active_user)):
    allowed = ["csps", "regions", "environments", "products", "test_suites"]
    if config_name not in allowed: raise HTTPException(status.HTTP_404_NOT_FOUND, "Config type not found.")
    fpath = CONFIG_PATH / f"{config_name}.yaml"
    if not fpath.exists(): raise HTTPException(status.HTTP_404_NOT_FOUND, "Config file not found.")
    try:
        with open(fpath, 'r') as f: data = yaml.safe_load(f)
        if data is None: return []
        if not isinstance(data, list): raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Config not list format.")
        return data
    except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Error reading/parsing {config_name}.yaml: {e}")

@app.get("/api/v1/configs", response_model=List[str], dependencies=[Depends(require_viewer)])
async def list_configuration_types(user: UserInDB = Depends(get_current_active_user)):
    return ["csps", "regions", "environments", "products", "test_suites"]

@app.get("/admin/test", dependencies=[Depends(require_admin)])
async def admin_test_endpoint(user: UserInDB = Depends(get_current_active_user)):
    return {"message": f"Hello Admin {user.username}! You have access."}

# New Endpoint to Start Test Suite Workflows
@app.post("/api/v1/workflows/test-suites/start",
            response_model=WorkflowStartResponse,
            status_code=status.HTTP_202_ACCEPTED,
            dependencies=[Depends(require_editor)])
async def start_test_suite_workflow(
    request_data: TestSuiteExecutionRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    if not temporal_client:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Temporal service not available.")

    suite_id = request_data.suite_id
    user_inputs = request_data.inputs
    suite_config = get_suite_config_sync(suite_id)
    if not suite_config:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Test suite '{suite_id}' configuration not found.")

    defined_inputs = suite_config.get("inputs", [])
    for di in defined_inputs:
        name, required = di.get("name"), di.get("required", False)
        if required and name not in user_inputs:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Missing required input: '{name}' for suite '{suite_id}'.")

    worker_config = suite_config.get("worker_config")
    if not worker_config:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Worker configuration missing for suite '{suite_id}'.")

    workflow_id = f"{suite_id}-{current_user.username}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    try:
        await temporal_client.start_workflow(
            "ExecuteTestSuiteWorkflow",
            args={
                "suite_id": suite_id,
                "worker_config": worker_config,
                "user_inputs": user_inputs,
                "triggered_by": {"user_id": current_user.id, "username": current_user.username}
            },
            id=workflow_id,
            task_queue="my-task-queue",
        )
        return WorkflowStartResponse(workflow_id=workflow_id, message=f"Test suite '{suite_id}' execution started.")
    except WorkflowAlreadyStartedError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Workflow ID '{workflow_id}' already exists.")
    except Exception as e:
        # Log e
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to start workflow: {e}")
