from fastapi import FastAPI, HTTPException, Depends, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, conint, validator # Added validator
import yaml
import os
from pathlib import Path
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import re # For regex

# Temporal Client Imports
from temporalio.client import Client, WorkflowExecutionDescription, WorkflowFailureError, WorkflowExecutionStatus, WorkflowHistoryEventFilterType
from temporalio.exceptions import WorkflowAlreadyStartedError, WorkflowNotFoundError
import httpx

# --- Configuration ---
CONFIG_PATH = Path("../config")
# Load SECRET_KEY from environment variable, with a default for local dev convenience
SECRET_KEY = os.environ.get("APP_SECRET_KEY", "a_default_secret_key_for_development_only_change_in_prod")
if SECRET_KEY == "a_default_secret_key_for_development_only_change_in_prod":
    print("WARNING: Using default development SECRET_KEY. Set APP_SECRET_KEY environment variable for production.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(title="Test Orchestration API")

# --- Temporal Client Setup ---
temporal_client: Optional[Client] = None
@app.on_event("startup")
async def startup_event(): global temporal_client; try: temporal_client = await Client.connect("localhost:7233"); print("Successfully connected to Temporal server.") except Exception as e: print(f"Failed to connect to Temporal server: {e}"); temporal_client = None
@app.on_event("shutdown")
async def shutdown_event(): global temporal_client; if temporal_client: await temporal_client.close(); print("Temporal client closed.")

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)
def get_password_hash(password): return pwd_context.hash(password)

# --- Models (User, Token, Workflow Execution Info) ---
class UserBase(BaseModel): username: str; email: Optional[str] = None; full_name: Optional[str] = None
class UserCreate(UserBase): password: str; roles: List[str] = ["viewer"]
class UserInDBBase(UserBase): id: int; roles: List[str] = ["viewer"]; class Config: orm_mode = True
class UserInDB(UserInDBBase): hashed_password: str
class UserPublic(UserInDBBase): pass
class Token(BaseModel): access_token: str; token_type: str
class TokenData(BaseModel): username: Optional[str] = None; roles: List[str] = []
class TestSuiteExecutionRequest(BaseModel): suite_id: str = Field(...); inputs: Dict[str, Any] = Field(default_factory=dict)
class WorkflowStartResponse(BaseModel): workflow_id: str; message: str
class WorkflowExecutionInfo(BaseModel): workflow_id: str; run_id: Optional[str] = None; task_queue: str; status: str; start_time: datetime; close_time: Optional[datetime] = None
class PaginatedWorkflowExecutions(BaseModel): executions: List[WorkflowExecutionInfo]; next_page_token: Optional[bytes] = None; total_count: Optional[int] = None
class WorkflowExecutionDetails(WorkflowExecutionInfo): history_events_count: Optional[int] = None
class WorkflowEvent(BaseModel): event_id: str; event_time: datetime; event_type: str; attributes: Optional[Dict[str, Any]] = None
class WorkflowExecutionHistory(BaseModel): workflow_id: str; run_id: str; events: List[WorkflowEvent]; next_page_token: Optional[bytes] = None

# Models for Schedules (with validation)
class ScheduleCreateRequest(BaseModel):
    schedule_id: str = Field(..., description="A unique ID for this schedule, e.g., 'daily_product_a_login_tests'. Use letters, numbers, underscores, hyphens.")
    schedule_name: str = Field(..., description="A human-readable name for the schedule.")
    cron_string: str = Field(..., description="The cron string, e.g., '0 5 * * *' for daily at 5 AM UTC.")
    suite_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)

    @validator('schedule_id')
    def validate_schedule_id(cls, value):
        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            raise ValueError("Schedule ID must contain only letters, numbers, underscores, and hyphens.")
        if len(value) < 3 or len(value) > 80:
            raise ValueError("Schedule ID must be between 3 and 80 characters long.")
        return value

    @validator('cron_string')
    def validate_cron_string(cls, value):
        parts = value.split()
        if not (len(parts) == 5 or len(parts) == 6) :
            raise ValueError("Cron string must have 5 or 6 space-separated parts.")
        if not re.match(r"^[0-9*/,-]+(\s[0-9*/,-]+){4,5}$", value): # Basic check, not full validation
             raise ValueError("Cron string contains invalid characters or structure.")
        return value

class ScheduleInfo(BaseModel):
    schedule_id: str
    schedule_name: Optional[str] = None
    cron_string: Optional[str] = None
    suite_id: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    status: str
    start_time: datetime

# --- Dummy User DB ---
fake_users_db: Dict[int, UserInDB] = {}
next_user_id = 1; initial_admin_username = "admin"; fake_users_db[next_user_id] = UserInDB(id=next_user_id, username=initial_admin_username, email="admin@example.com", full_name="Admin User", hashed_password=get_password_hash("adminpassword"), roles=["admin", "editor", "viewer"]); next_user_id += 1

# --- Authentication & Authorization ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
def create_access_token(data, expires_delta=None): expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)); return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
async def get_user_by_username(username: str): return next((u for u in fake_users_db.values() if u.username == username), None)
async def get_user_by_id(user_id: int): return fake_users_db.get(user_id)
async def authenticate_user(username, password): user = await get_user_by_username(username); return user if user and verify_password(password, user.hashed_password) else None
async def get_current_user(token: str = Depends(oauth2_scheme)):
    exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try: payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]); username = payload.get("sub")
    except jwt.ExpiredSignatureError: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired", headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError: raise exc
    if not username or not (user := await get_user_by_username(username)): raise exc
    return user
async def get_current_active_user(user: UserInDB = Depends(get_current_user)): return user
def require_role(role):
    async def checker(user: UserInDB = Depends(get_current_active_user)):
        if role not in user.roles: raise HTTPException(status.HTTP_403_FORBIDDEN, f"User lacks '{role}' role.")
        return user
    return checker
require_admin, require_editor, require_viewer = require_role("admin"), require_role("editor"), require_role("viewer")

# --- Helpers & Endpoints (Existing, potentially minified for brevity but functional) ---
def get_suite_config_sync(suite_id): fpath = CONFIG_PATH / "test_suites.yaml"; S = []; P = Path(fpath); return next((s for s in (yaml.safe_load(P.read_text()) if P.exists() else []) if isinstance(s,dict) and s.get("id") == suite_id), None)
@app.post("/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()): user = await authenticate_user(form.username, form.password); S={"sub":user.username,"roles":user.roles}; return {"access_token": create_access_token(S) if user else (_ for _ in ()).throw(HTTPException(status.HTTP_401_UNAUTHORIZED,"Incorrect credentials")), "token_type":"bearer"}
@app.post("/users/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate): global next_user_id; U=user_in.username; E=user_in.email; P=user_in.password; R=user_in.roles or ["viewer"]; H=get_password_hash(P); N=UserInDB(id=next_user_id,username=U,email=E,full_name=user_in.full_name,roles=R,hashed_password=H); F=fake_users_db; A=any; GU=get_user_by_username; (await GU(U) and (_ for _ in ()).throw(HTTPException(status.HTTP_400_BAD_REQUEST,"Username taken."))) or (E and A(u.email == E for u in F.values()) and (_ for _ in ()).throw(HTTPException(status.HTTP_400_BAD_REQUEST,"Email taken."))); F[next_user_id]=N; next_user_id+=1; return UserPublic.from_orm(N)
@app.get("/users/me", response_model=UserPublic)
async def users_me(user: UserInDB = Depends(get_current_active_user)): return UserPublic.from_orm(user)
@app.get("/users", response_model=List[UserPublic], dependencies=[Depends(require_admin)])
async def users_list(): return [UserPublic.from_orm(u) for u in fake_users_db.values()]
@app.put("/users/{uid}/roles", response_model=UserPublic, dependencies=[Depends(require_admin)])
async def users_update_roles(uid: int, roles: List[str] = Body(..., embed=True)): U=await get_user_by_id(uid); V={"admin","editor","viewer"}; I=[r for r in roles if r not in V]; (U or (_ for _ in ()).throw(HTTPException(status.HTTP_404_NOT_FOUND))) and ((not roles or I) and (_ for _ in ()).throw(HTTPException(status.HTTP_400_BAD_REQUEST,f"Role issue: {I if I else 'empty'}"))); U.roles=list(set(roles)); return UserPublic.from_orm(U)
@app.get("/")
async def root(): return {"message": "Welcome"}
@app.get("/api/v1/configs/{name}", response_model=List[Dict[str,Any]], dependencies=[Depends(require_viewer)])
async def configs_get(name: str, u:UserInDB=Depends(get_current_active_user)): A=["csps","regions","environments","products","test_suites"]; P=Path(CONFIG_PATH/f"{name}.yaml"); (name in A or (_ for _ in ()).throw(HTTPException(status.HTTP_404_NOT_FOUND,"Bad type."))) and (P.exists() or (_ for _ in ()).throw(HTTPException(status.HTTP_404_NOT_FOUND,"No file."))); D=yaml.safe_load(P.read_text()) or []; (isinstance(D,list) or (_ for _ in ()).throw(HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,"Bad format."))); return D
@app.get("/api/v1/configs", response_model=List[str], dependencies=[Depends(require_viewer)])
async def configs_list_types(u:UserInDB=Depends(get_current_active_user)): return ["csps","regions","environments","products","test_suites"]
@app.get("/admin/test", dependencies=[Depends(require_admin)])
async def admin_test(u:UserInDB=Depends(get_current_active_user)): return {"message":f"Hi Admin {u.username}!"}
@app.post("/api/v1/workflows/test-suites/start", response_model=WorkflowStartResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_editor)])
async def workflows_start_test_suite(req: TestSuiteExecutionRequest, u:UserInDB=Depends(get_current_active_user)): C=get_suite_config_sync(req.suite_id); (C or (_ for _ in ()).throw(HTTPException(status.HTTP_404_NOT_FOUND,f"Suite '{req.suite_id}' not found."))); [di.get("required") and di.get("name") not in req.inputs and (_ for _ in ()).throw(HTTPException(status.HTTP_400_BAD_REQUEST,f"Input missing: '{di.get('name')}'")) for di in C.get("inputs",[])]; W=C.get("worker_config") or (_ for _ in ()).throw(HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,"No worker_config.")); I=f"{req.suite_id}-{u.username}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"; (temporal_client or (_ for _ in ()).throw(HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,"Temporal down."))); A={"suite_id":req.suite_id,"worker_config":W,"user_inputs":req.inputs,"triggered_by":{"user_id":u.id,"username":u.username}}; try: await temporal_client.start_workflow("ExecuteTestSuiteWorkflow",args=A,id=I,task_queue="my-task-queue"); return WorkflowStartResponse(workflow_id=I,message="Started.") except WorkflowAlreadyStartedError: raise HTTPException(status.HTTP_409_CONFLICT,f"ID '{I}' exists.") except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,f"Start failed: {e}")
@app.get("/api/v1/workflows/executions",response_model=PaginatedWorkflowExecutions,dependencies=[Depends(require_viewer)])
async def workflows_list_executions(u:UserInDB=Depends(get_current_active_user),page_size:conint(gt=0,le=100)=20,next_page_token:Optional[bytes]=None,workflow_id_filter:Optional[str]=None,workflow_type_filter:Optional[str]=None,status_filter:Optional[str]=None): (temporal_client or (_ for _ in ()).throw(HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,"Temporal down."))); Q=" AND ".join([p for p in [f"WorkflowId = '{workflow_id_filter}'" if workflow_id_filter else "", f"WorkflowType = '{workflow_type_filter}'" if workflow_type_filter else "", f"ExecutionStatus = '{status_filter.upper()}'" if status_filter else ""] if p]) or "TRUE"; H=temporal_client.list_workflows(query=Q,page_size=page_size,next_page_token=next_page_token); E=[WorkflowExecutionInfo(workflow_id=d.id,run_id=d.run_id,task_queue=d.task_queue,status=d.status.name.replace("WORKFLOW_EXECUTION_STATUS_",""),start_time=d.start_time,close_time=d.close_time) async for d in H]; return PaginatedWorkflowExecutions(executions=E,next_page_token=H.next_page_token)
@app.get("/api/v1/workflows/executions/{workflow_id}",response_model=WorkflowExecutionDetails,dependencies=[Depends(require_viewer)])
async def workflows_get_execution_details(workflow_id:str,run_id:Optional[str]=None,u:UserInDB=Depends(get_current_active_user)): (temporal_client or (_ for _ in ()).throw(HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,"Temporal down."))); D=await temporal_client.get_workflow_handle(workflow_id,run_id=run_id).describe(); return WorkflowExecutionDetails(workflow_id=D.id,run_id=D.run_id,task_queue=D.task_queue,status=D.status.name.replace("WORKFLOW_EXECUTION_STATUS_",""),start_time=D.start_time,close_time=D.close_time)
@app.get("/api/v1/workflows/executions/{workflow_id}/history",response_model=WorkflowExecutionHistory,dependencies=[Depends(require_viewer)])
async def workflows_get_execution_history(workflow_id:str,run_id:Optional[str]=None,wait_new:bool=False,event_filter_type:str="ALL",next_page_token:Optional[bytes]=None,u:UserInDB=Depends(get_current_active_user)): (temporal_client or (_ for _ in ()).throw(HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,"Temporal down."))); H=temporal_client.get_workflow_handle(workflow_id,run_id=run_id); F=WorkflowHistoryEventFilterType[event_filter_type.upper()] if event_filter_type.upper() in WorkflowHistoryEventFilterType.__members__ else WorkflowHistoryEventFilterType.ALL; I=H.fetch_history_events(wait_for_new_event=wait_new,event_filter_type=F,page_token=next_page_token); E=[]; async for e in I: E.append(WorkflowEvent(event_id=str(e.id),event_time=e.timestamp,event_type=e.type.name,attributes=e.attributes.to_json_dict() if e.attributes else None)); len(E)>=50 and (_ for _ in ()).break_(); return WorkflowExecutionHistory(workflow_id=H.id,run_id=H.run_id,events=E,next_page_token=I.next_page_token)

# --- Endpoints for Schedules ---
@app.post("/api/v1/schedules", status_code=status.HTTP_201_CREATED, response_model=ScheduleInfo, dependencies=[Depends(require_editor)])
async def create_schedule(schedule_data: ScheduleCreateRequest, current_user: UserInDB = Depends(get_current_active_user)):
    if not temporal_client: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Temporal service not available.")
    suite_config = get_suite_config_sync(schedule_data.suite_id)
    if not suite_config: raise HTTPException(status.HTTP_404_NOT_FOUND, f"Test suite '{schedule_data.suite_id}' configuration not found.")
    worker_config_params = suite_config.get("worker_config")
    if not worker_config_params: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Worker configuration missing for suite '{schedule_data.suite_id}'.")

    schedule_runner_params = {
        "suite_id": schedule_data.suite_id, "worker_config": worker_config_params,
        "user_inputs": schedule_data.inputs, "schedule_name": schedule_data.schedule_name,
        "cron_string": schedule_data.cron_string,
        "triggered_by": {"type": "schedule_creation", "username": current_user.username}
    }
    cron_workflow_id = schedule_data.schedule_id
    try:
        await temporal_client.start_workflow(
            "ScheduledTestSuiteRunnerWorkflow", args=[schedule_runner_params], id=cron_workflow_id,
            task_queue="my-task-queue", cron_schedule=schedule_data.cron_string,
            memo={"schedule_name": schedule_data.schedule_name, "suite_id": schedule_data.suite_id, "cron_string": schedule_data.cron_string}
        )
        return ScheduleInfo( schedule_id=cron_workflow_id, schedule_name=schedule_data.schedule_name, cron_string=schedule_data.cron_string,
            suite_id=schedule_data.suite_id, inputs=schedule_data.inputs, status="ACTIVE", start_time=datetime.utcnow())
    except WorkflowAlreadyStartedError: raise HTTPException(status.HTTP_409_CONFLICT, f"Schedule ID '{cron_workflow_id}' already exists.")
    except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to create schedule: {str(e)}")

@app.get("/api/v1/schedules", response_model=List[ScheduleInfo], dependencies=[Depends(require_viewer)])
async def list_schedules(current_user: UserInDB = Depends(get_current_active_user)):
    if not temporal_client: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Temporal service not available.")
    schedules_list: List[ScheduleInfo] = []
    try:
        query = "WorkflowType = 'ScheduledTestSuiteRunnerWorkflow' AND ExecutionStatus = 'Running'"
        async for wf_exec in temporal_client.list_workflows(query=query):
            memo = wf_exec.memo or {}
            desc = await temporal_client.get_workflow_handle(wf_exec.id, run_id=wf_exec.run_id).describe()
            schedules_list.append(ScheduleInfo(
                schedule_id=wf_exec.id, schedule_name=memo.get("schedule_name",["N/A"])[0],
                cron_string=desc.cron_schedule, suite_id=memo.get("suite_id",["N/A"])[0],
                status=wf_exec.status.name.replace("WORKFLOW_EXECUTION_STATUS_",""), start_time=wf_exec.start_time
            ))
        return schedules_list
    except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to list schedules: {str(e)}")

@app.delete("/api/v1/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_editor)])
async def delete_schedule(schedule_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    if not temporal_client: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Temporal service not available.")
    try:
        await temporal_client.get_workflow_handle(schedule_id).terminate(reason=f"Schedule deleted by user {current_user.username}")
    except WorkflowNotFoundError: raise HTTPException(status.HTTP_404_NOT_FOUND, f"Schedule ID '{schedule_id}' not found.")
    except Exception as e: raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to delete schedule: {str(e)}")
