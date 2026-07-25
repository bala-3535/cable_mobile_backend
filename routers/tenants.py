from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Tenant, User, UserRole
from schemas import TenantResponse, TenantRegistration, TenantCreate
from core.security import hash_password
from dependencies import get_current_user, role_required, super_admin_required

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post("/register", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def register_tenant(
    registration: TenantRegistration,
    db: Session = Depends(get_db),
    current_super_admin: User = Depends(super_admin_required())
):
    # Check if tenant name exists
    existing_tenant = db.query(Tenant).filter(Tenant.name == registration.tenant_name).first()
    if existing_tenant:
        raise HTTPException(status_code=400, detail="Tenant name already exists")
        
    # Check if admin username exists
    existing_user = db.query(User).filter(User.username == registration.admin_username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Admin username already exists")
        
    # Create Tenant
    new_tenant = Tenant(name=registration.tenant_name)
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    
    # Create Admin User for this Tenant
    new_admin = User(
        username=registration.admin_username,
        password_hash=hash_password(registration.admin_password),
        role=UserRole.admin,
        is_active=True,
        tenant_id=new_tenant.id
    )
    db.add(new_admin)
    db.commit()
    
    return new_tenant

@router.get("/", response_model=List[TenantResponse])
def get_tenants(
    db: Session = Depends(get_db),
    current_super_admin: User = Depends(super_admin_required())
):
    return db.query(Tenant).all()
