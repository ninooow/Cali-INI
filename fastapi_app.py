from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from config import settings
from database import get_db, init_db
from models.core import Asset
from models.telemetry import HourlyMeasurement
from pydantic import BaseModel, validator
from typing import List, Optional
from models.knowledge import Incident, RcaHeader, RcaPriorityMatrix, Rca4pVerification, Rca4mVerification, RcaCapaAction
from models.workflow import ProblemTicket, OperatorInput, AuditLog
from models.iam import User

app = FastAPI(title=settings.PROJECT_NAME, openapi_url="/api/v1/openapi.json")
app.settings = settings  # expose settings via app for tests
# Database initialization disabled for production; tests invoke init_db explicitly
app.settings = settings  # expose settings via app for tests

# CORS – allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- health & system (secure) ----------
@app.get("/health", tags=["system"])
def health_check():
    return {"status": "healthy"}

@app.get("/system", tags=["system"])
def system_info(db: Session = Depends(get_db)):
    # Simple DB connectivity check without exposing credentials
    try:
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "error"
    return {"status": "healthy", "database": db_status}

# ---------- Pydantic schemas ----------
class AssetResponse(BaseModel):
    asset_id: int
    tag_number: str
    asset_name: str
    equipment_type: Optional[str]
    equipment_class: Optional[str]
    plant_code: Optional[str]
    discipline: Optional[str]
    criticality: Optional[str]
    is_active: bool

    class Config:
        orm_mode = True

class AssetListResponse(BaseModel):
    data: List[AssetResponse]

class HourlyMeasurementCreate(BaseModel):
    # existing fields...
    pass
    asset_id: int
    measured_at: datetime
    feed: Optional[float] = None
    disp: Optional[float] = None
    vib: Optional[float] = None
    temp: Optional[float] = None
    amp: Optional[float] = None
    plant_rate: Optional[float] = None
    run_status: Optional[str] = None
    source_type: Optional[str] = "MANUAL"

    @validator("run_status")
    def validate_run_status(cls, v):
        if v and v not in {"ON", "OFF", "UNKNOWN"}:
            raise ValueError("run_status must be ON, OFF, or UNKNOWN")
        return v

class HourlyMeasurementResponse(BaseModel):
    asset_id: int
    measured_at: datetime
    feed: Optional[float]
    disp: Optional[float]
    vib: Optional[float]
    temp: Optional[float]
    amp: Optional[float]
    plant_rate: Optional[float]
    run_status: Optional[str]
    source_type: Optional[str]

    class Config:
        orm_mode = True

class HourlyMeasurementListResponse(BaseModel):
    data: List[HourlyMeasurementResponse]

# ---------- Reliability schemas ----------
class IncidentBase(BaseModel):
    ar_no: str
    plant: Optional[str] = None
    equipment_class: Optional[str] = None
    date_of_occurrence: Optional[datetime] = None
    risk_score: Optional[float] = None
    pic_rca: Optional[str] = None
    overall_status: Optional[str] = None
    discipline: Optional[str] = None
    equipment_type: Optional[str] = None
    component: Optional[str] = None
    failure_mechanism: Optional[str] = None
    downtime_hours: Optional[float] = None
    actual_loss_kusd: Optional[float] = None
    potential_loss_kusd: Optional[float] = None
    total_loss_kusd: Optional[float] = None
    rca_due_date: Optional[datetime] = None
    source_type: str = "MANUAL"

class IncidentCreate(IncidentBase):
    pass

class IncidentResponse(IncidentBase):
    incident_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class IncidentListResponse(BaseModel):
    data: List[IncidentResponse]

class RcaHeaderBase(BaseModel):
    ar_no: str
    tag_number: Optional[str] = None
    plant: Optional[str] = None
    date_occurrence: Optional[datetime] = None
    pre_risk: Optional[str] = None
    risk_score: Optional[float] = None
    pic_rca: Optional[str] = None
    procedure_no: Optional[str] = None
    problem_statement: Optional[str] = None
    root_cause_statement: Optional[str] = None
    source_type: str = "MANUAL"

class RcaHeaderCreate(RcaHeaderBase):
    pass

class RcaHeaderResponse(RcaHeaderBase):
    rca_header_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class RcaHeaderListResponse(BaseModel):
    data: List[RcaHeaderResponse]

class PriorityMatrixBase(BaseModel):
    ar_no: str
    root_cause_id: str
    impact_level: Optional[str] = None
    control_level: Optional[str] = None
    priority_rank: Optional[int] = None
    description_short: Optional[str] = None

class PriorityMatrixCreate(PriorityMatrixBase):
    pass

class PriorityMatrixResponse(PriorityMatrixBase):
    priority_matrix_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class PriorityMatrixListResponse(BaseModel):
    data: List[PriorityMatrixResponse]

class Rca4pBase(BaseModel):
    ar_no: str
    parameter_id: str
    problem_phenomenon_parameter: Optional[str] = None
    result: Optional[str] = None
    evidence_finding: Optional[str] = None

class Rca4pCreate(Rca4pBase):
    pass

class Rca4pResponse(Rca4pBase):
    verification_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Rca4pListResponse(BaseModel):
    data: List[Rca4pResponse]

class Rca4mBase(BaseModel):
    ar_no: str
    factor_id: str
    factor_category: Optional[str] = None
    result: Optional[str] = None
    evidence_finding: Optional[str] = None

class Rca4mCreate(Rca4mBase):
    pass

class Rca4mResponse(Rca4mBase):
    verification_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Rca4mListResponse(BaseModel):
    data: List[Rca4mResponse]

class CapaActionBase(BaseModel):
    ar_no: str
    rc: Optional[str] = None
    action_type: Optional[str] = None
    action_plan: str
    target_date: Optional[datetime] = None
    pic: Optional[str] = None
    status: Optional[str] = None
    fingerprint: str

class CapaActionCreate(CapaActionBase):
    pass

class CapaActionResponse(CapaActionBase):
    capa_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class CapaActionListResponse(BaseModel):
    data: List[CapaActionResponse]

# ---------- Asset endpoints ----------
@app.get(
    f"{settings.API_V1_PREFIX}/assets",
    response_model=AssetListResponse,
    tags=["assets"],
)
def list_assets(
    search: Optional[str] = None,
    plant: Optional[str] = None,
    equipment_type: Optional[str] = None,
    criticality: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Asset)
    if search:
        q = q.filter(Asset.tag_number.ilike(f"%{search}%"))
    if plant:
        q = q.filter(Asset.plant_code == plant)
    if equipment_type:
        q = q.filter(Asset.equipment_type == equipment_type)
    if criticality:
        q = q.filter(Asset.criticality == criticality)
    if is_active is not None:
        q = q.filter(Asset.is_active == is_active)
    assets = q.all()
    return {"data": assets}

@app.get(
    f"{settings.API_V1_PREFIX}/assets/{{asset_id}}",
    response_model=AssetResponse,
    tags=["assets"],
)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.asset_id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

# ---------- Hourly telemetry endpoints ----------
@app.get(
    f"{settings.API_V1_PREFIX}/telemetry/hourly",
    response_model=HourlyMeasurementListResponse,
    tags=["telemetry"],
)
def list_hourly(
    asset_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    q = db.query(HourlyMeasurement)
    if asset_id:
        q = q.filter(HourlyMeasurement.asset_id == asset_id)
    if start:
        q = q.filter(HourlyMeasurement.measured_at >= start)
    if end:
        q = q.filter(HourlyMeasurement.measured_at <= end)
    rows = q.order_by(HourlyMeasurement.measured_at.desc()).all()
    return {"data": rows}

@app.post(
    f"{settings.API_V1_PREFIX}/telemetry/hourly",
    response_model=HourlyMeasurementListResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["telemetry"],
)
def create_hourly(
    measurements: List[HourlyMeasurementCreate],
    db: Session = Depends(get_db),
):
    # Verify asset existence
    asset_ids = {m.asset_id for m in measurements}
    existing = db.query(Asset.asset_id).filter(Asset.asset_id.in_(list(asset_ids))).all()
    existing_ids = {aid for (aid,) in existing}
    missing = asset_ids - existing_ids
    if missing:
        raise HTTPException(status_code=400, detail=f"Asset(s) not found: {missing}")
    objs = [HourlyMeasurement(**m.dict()) for m in measurements]
    db.bulk_save_objects(objs)
    db.commit()
    return {"data": objs}

# Initialize DB on startup
@app.on_event("startup")
def on_startup():
    pass

# ---------- Reliability endpoints ----------
# Incident endpoints
@app.get(f"{settings.API_V1_PREFIX}/reliability/incidents", response_model=IncidentListResponse, tags=["reliability"])
def list_incidents(db: Session = Depends(get_db)):
    incidents = db.query(Incident).all()
    return {"data": incidents}

@app.get(f"{settings.API_V1_PREFIX}/reliability/incidents/{{incident_id}}", response_model=IncidentResponse, tags=["reliability"])
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.incident_id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

@app.post(f"{settings.API_V1_PREFIX}/reliability/incidents", response_model=IncidentListResponse, status_code=status.HTTP_201_CREATED, tags=["reliability"])
def create_incidents(incidents: List[IncidentCreate], db: Session = Depends(get_db)):
    # Insert incidents and return fully populated objects with IDs and timestamps
    objs = [Incident(**inc.dict()) for inc in incidents]
    db.add_all(objs)
    db.commit()
    # Refresh to get autogenerated fields
    for obj in objs:
        db.refresh(obj)
    return {"data": objs}

# RCA Header endpoints
@app.get(f"{settings.API_V1_PREFIX}/reliability/rca", response_model=RcaHeaderListResponse, tags=["reliability"])
def list_rca_headers(db: Session = Depends(get_db)):
    headers = db.query(RcaHeader).all()
    return {"data": headers}

@app.get(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}", response_model=RcaHeaderResponse, tags=["reliability"])
def get_rca_header(ar_no: str, db: Session = Depends(get_db)):
    hdr = db.query(RcaHeader).filter(RcaHeader.ar_no == ar_no).first()
    if not hdr:
        raise HTTPException(status_code=404, detail="RCA header not found")
    return hdr

@app.post(f"{settings.API_V1_PREFIX}/reliability/rca", response_model=RcaHeaderListResponse, status_code=status.HTTP_201_CREATED, tags=["reliability"])
def create_rca_headers(headers: List[RcaHeaderCreate], db: Session = Depends(get_db)):
    objs = [RcaHeader(**h.dict()) for h in headers]
    db.bulk_save_objects(objs)
    db.commit()
    return {"data": objs}

# Priority Matrix endpoints
@app.get(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/priority-matrix", response_model=PriorityMatrixListResponse, tags=["reliability"])
def list_priority_matrix(ar_no: str, db: Session = Depends(get_db)):
    rows = db.query(RcaPriorityMatrix).filter(RcaPriorityMatrix.ar_no == ar_no).all()
    return {"data": rows}

@app.post(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/priority-matrix", response_model=PriorityMatrixListResponse, status_code=status.HTTP_201_CREATED, tags=["reliability"])
def create_priority_matrix(ar_no: str, items: List[PriorityMatrixCreate], db: Session = Depends(get_db)):
    objs = []
    for itm in items:
        if itm.ar_no != ar_no:
            raise HTTPException(status_code=400, detail="ar_no mismatch in payload")
        objs.append(RcaPriorityMatrix(**itm.dict()))
    db.bulk_save_objects(objs)
    db.commit()
    return {"data": objs}

# 4P verification endpoints
@app.get(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/4p", response_model=Rca4pListResponse, tags=["reliability"])
def list_4p(ar_no: str, db: Session = Depends(get_db)):
    rows = db.query(Rca4pVerification).filter(Rca4pVerification.ar_no == ar_no).all()
    return {"data": rows}

@app.post(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/4p", response_model=Rca4pListResponse, status_code=status.HTTP_201_CREATED, tags=["reliability"])
def create_4p(ar_no: str, items: List[Rca4pCreate], db: Session = Depends(get_db)):
    objs = []
    for itm in items:
        if itm.ar_no != ar_no:
            raise HTTPException(status_code=400, detail="ar_no mismatch")
        objs.append(Rca4pVerification(**itm.dict()))
    db.bulk_save_objects(objs)
    db.commit()
    return {"data": objs}

# 4M verification endpoints
@app.get(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/4m", response_model=Rca4mListResponse, tags=["reliability"])
def list_4m(ar_no: str, db: Session = Depends(get_db)):
    rows = db.query(Rca4mVerification).filter(Rca4mVerification.ar_no == ar_no).all()
    return {"data": rows}

@app.post(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/4m", response_model=Rca4mListResponse, status_code=status.HTTP_201_CREATED, tags=["reliability"])
def create_4m(ar_no: str, items: List[Rca4mCreate], db: Session = Depends(get_db)):
    objs = []
    for itm in items:
        if itm.ar_no != ar_no:
            raise HTTPException(status_code=400, detail="ar_no mismatch")
        objs.append(Rca4mVerification(**itm.dict()))
    db.bulk_save_objects(objs)
    db.commit()
    return {"data": objs}

# CAPA actions endpoints
@app.get(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/capa", response_model=CapaActionListResponse, tags=["reliability"])
def list_capa(ar_no: str, db: Session = Depends(get_db)):
    rows = db.query(RcaCapaAction).filter(RcaCapaAction.ar_no == ar_no).all()
    return {"data": rows}

@app.post(f"{settings.API_V1_PREFIX}/reliability/rca/{{ar_no}}/capa", response_model=CapaActionListResponse, status_code=status.HTTP_201_CREATED, tags=["reliability"])
def create_capa(ar_no: str, items: List[CapaActionCreate], db: Session = Depends(get_db)):
    objs = []
    for itm in items:
        if itm.ar_no != ar_no:
            raise HTTPException(status_code=400, detail="ar_no mismatch")
        objs.append(RcaCapaAction(**itm.dict()))
    db.bulk_save_objects(objs)
    db.commit()
    return {"data": objs}

# ---------- Workflow (Problems / Operator) schemas ----------
class ProblemTicketBase(BaseModel):
    ticket_id: str
    asset_id: int
    opened_at: datetime
    condition_state: Optional[str] = None
    priority: Optional[str] = None
    owner_role: Optional[str] = None
    ticket_state: Optional[str] = "OPEN"
    action_status: Optional[str] = "NOT_STARTED"
    normal_streak: Optional[int] = 0
    matched_rca_ar: Optional[str] = None
    evidence_strength: Optional[str] = None
    operator_decision: Optional[str] = None
    last_operator_name: Optional[str] = None
    operator_comment: Optional[str] = None
    field_observation: Optional[str] = None
    update_source: Optional[str] = "ENGINE"
    last_observation_time: Optional[datetime] = None

class ProblemTicketCreate(ProblemTicketBase):
    pass

class ProblemTicketUpdate(BaseModel):
    ticket_state: Optional[str] = None
    action_status: Optional[str] = None
    operator_decision: Optional[str] = None
    operator_comment: Optional[str] = None
    field_observation: Optional[str] = None
    last_operator_name: Optional[str] = None
    last_observation_time: Optional[datetime] = None

class ProblemTicketResponse(ProblemTicketBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        orm_mode = True

class ProblemTicketListResponse(BaseModel):
    data: List[ProblemTicketResponse]


class AuditLogResponse(BaseModel):
    audit_id: int
    event_time: datetime
    ticket_id: str
    asset_id: int
    update_source: Optional[str]
    event_type: Optional[str]
    previous_ticket_state: Optional[str]
    new_ticket_state: Optional[str]
    previous_action_status: Optional[str]
    new_action_status: Optional[str]
    operator_decision: Optional[str]
    operator_name: Optional[str]
    owner_role: Optional[str]
    field_observation: Optional[str]
    comment: Optional[str]
    class Config:
        orm_mode = True

class AuditLogListResponse(BaseModel):
    data: List[AuditLogResponse]


# ---------- Workflow endpoints ----------
@app.get(f"{settings.API_V1_PREFIX}/workflow/tickets", response_model=ProblemTicketListResponse, tags=["workflow"])
def list_tickets(db: Session = Depends(get_db)):
    tickets = db.query(ProblemTicket).all()
    return {'data': tickets}

@app.get(f"{settings.API_V1_PREFIX}/workflow/tickets/{{ticket_id}}", response_model=ProblemTicketResponse, tags=["workflow"])
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.query(ProblemTicket).filter(ProblemTicket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@app.post(f"{settings.API_V1_PREFIX}/workflow/tickets", response_model=ProblemTicketListResponse, status_code=status.HTTP_201_CREATED, tags=["workflow"])
def create_ticket(ticket: ProblemTicketCreate, db: Session = Depends(get_db)):
    # Validate asset exists
    asset = db.query(Asset).filter(Asset.asset_id == ticket.asset_id).first()
    if not asset:
        raise HTTPException(status_code=400, detail="Asset not found")
    db_ticket = ProblemTicket(**ticket.dict())
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    # Create initial audit log
    audit = AuditLog(
        ticket_id=db_ticket.ticket_id,
        asset_id=db_ticket.asset_id,
        event_type="CREATE",
        new_ticket_state=db_ticket.ticket_state,
        new_action_status=db_ticket.action_status,
    )
    db.add(audit)
    db.commit()
    return {'data': [db_ticket]}


@app.patch(f"{settings.API_V1_PREFIX}/workflow/tickets/{{ticket_id}}", response_model=ProblemTicketResponse, tags=["workflow"])
def update_ticket(ticket_id: str, updates: ProblemTicketUpdate, db: Session = Depends(get_db)):
    ticket = db.query(ProblemTicket).filter(ProblemTicket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # Preserve previous state for audit
    prev_state = ticket.ticket_state
    prev_action = ticket.action_status
    # Apply updates
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(ticket, field, value)
    db.add(ticket)
    # Create audit log entry
    audit = AuditLog(
        ticket_id=ticket.ticket_id,
        asset_id=ticket.asset_id,
        event_type="UPDATE",
        previous_ticket_state=prev_state,
        new_ticket_state=ticket.ticket_state,
        previous_action_status=prev_action,
        new_action_status=ticket.action_status,
        operator_decision=updates.operator_decision,
        operator_name=updates.last_operator_name,
        comment=updates.operator_comment,
        field_observation=updates.field_observation,
        update_source="OPERATOR",
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)
    return ticket

@app.get(f"{settings.API_V1_PREFIX}/workflow/tickets/{{ticket_id}}/audit_logs", response_model=AuditLogListResponse, tags=["workflow"])
def get_audit_logs(ticket_id: str, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).filter(AuditLog.ticket_id == ticket_id).order_by(AuditLog.event_time.desc()).all()
    return {'data': logs}

# ---------- User administration schemas ----------
class UserBase(BaseModel):
    username: str
    display_name: str
    email: Optional[str] = None
    employee_id: Optional[str] = None
    role: Optional[str] = None
    discipline: Optional[str] = None
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    employee_id: Optional[str] = None
    role: Optional[str] = None
    discipline: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    user_id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        orm_mode = True

class UserListResponse(BaseModel):
    data: List[UserResponse]

# ---------- User administration endpoints ----------
@app.get(f"{settings.API_V1_PREFIX}/users", response_model=UserListResponse, tags=["users"])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {"data": users}

@app.get(f"{settings.API_V1_PREFIX}/users/{{user_id}}", response_model=UserResponse, tags=["users"])
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post(f"{settings.API_V1_PREFIX}/users", response_model=UserListResponse, status_code=status.HTTP_201_CREATED, tags=["users"])
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    db_user = User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"data": [db_user]}

@app.patch(f"{settings.API_V1_PREFIX}/users/{{user_id}}", response_model=UserResponse, tags=["users"])
def update_user(user_id: int, updates: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

