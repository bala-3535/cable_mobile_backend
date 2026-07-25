from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from core.utils import get_ist_now

from database import get_db
from models import Fault, Customer, User, FaultStatus
from schemas import FaultCreate, FaultUpdate, FaultResponse
from dependencies import get_current_user

router = APIRouter(prefix="/faults", tags=["faults"])

@router.post("/", response_model=FaultResponse)
def create_fault(
    fault: FaultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if customer exists
    customer = db.query(Customer).filter(Customer.id == fault.customer_id, Customer.tenant_id == current_user.tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    db_fault = Fault(
        customer_id=fault.customer_id,
        description=fault.description,
        created_by=current_user.id,
        status=FaultStatus.open,
        tenant_id=current_user.tenant_id
    )
    db.add(db_fault)
    db.commit()
    db.refresh(db_fault)
    
    # Enrich for response
    db_fault.created_by_name = current_user.username
    db_fault.customer_name = customer.customer_name
    db_fault.customer_address = customer.address
    return db_fault

@router.get("/", response_model=List[FaultResponse])
def get_faults(
    status: Optional[FaultStatus] = None,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(
        Fault, 
        User.username.label("created_by_name"),
        Customer.customer_name.label("customer_name"),
        Customer.address.label("customer_address")
    ).join(User, Fault.created_by == User.id)\
     .join(Customer, Fault.customer_id == Customer.id)\
     .filter(Fault.tenant_id == current_user.tenant_id)
    
    if status:
        query = query.filter(Fault.status == status)
    if customer_id:
        query = query.filter(Fault.customer_id == customer_id)
        
    results = query.order_by(Fault.created_at.desc()).all()
    
    faults = []
    for f, creator, cust_name, cust_addr in results:
        # Create a dictionary for the response model
        f_data = {
            "id": f.id,
            "customer_id": f.customer_id,
            "description": f.description,
            "status": f.status,
            "created_by": f.created_by,
            "created_at": f.created_at,
            "resolved_by": f.resolved_by,
            "resolved_at": f.resolved_at,
            "resolution_notes": f.resolution_notes,
            "created_by_name": creator,
            "customer_name": cust_name,
            "customer_address": cust_addr,
            "resolved_by_name": None
        }
        
        # Get resolver name if resolved
        if f.resolved_by:
            resolver = db.query(User).filter(User.id == f.resolved_by).first()
            f_data["resolved_by_name"] = resolver.username if resolver else None
            
        faults.append(f_data)
        
    return faults

@router.patch("/{fault_id}", response_model=FaultResponse)
def update_fault(
    fault_id: int,
    fault_update: FaultUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_fault = db.query(Fault).filter(Fault.id == fault_id, Fault.tenant_id == current_user.tenant_id).first()
    if not db_fault:
        raise HTTPException(status_code=404, detail="Fault not found")
        
    if fault_update.status:
        db_fault.status = fault_update.status
        if fault_update.status == FaultStatus.resolved:
            db_fault.resolved_by = current_user.id
            db_fault.resolved_at = get_ist_now()
            
    if fault_update.resolution_notes is not None:
        db_fault.resolution_notes = fault_update.resolution_notes
        
    db.commit()
    db.refresh(db_fault)
    
    # Enrichment
    creator = db.query(User).filter(User.id == db_fault.created_by).first()
    customer = db.query(Customer).filter(Customer.id == db_fault.customer_id).first()
    
    response_data = {
        "id": db_fault.id,
        "customer_id": db_fault.customer_id,
        "description": db_fault.description,
        "status": db_fault.status,
        "created_by": db_fault.created_by,
        "created_at": db_fault.created_at,
        "resolved_by": db_fault.resolved_by,
        "resolved_at": db_fault.resolved_at,
        "resolution_notes": db_fault.resolution_notes,
        "created_by_name": creator.username if creator else None,
        "customer_name": customer.customer_name if customer else None,
        "customer_address": customer.address if customer else None,
        "resolved_by_name": None
    }
    
    if db_fault.resolved_by:
        resolver = db.query(User).filter(User.id == db_fault.resolved_by).first()
        response_data["resolved_by_name"] = resolver.username if resolver else None
        
    return response_data
