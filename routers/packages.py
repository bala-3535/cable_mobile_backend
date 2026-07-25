from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User, Package, UserRole
from schemas import PackageCreate, PackageResponse, PackageUpdate
from dependencies import get_current_user, role_required

router = APIRouter(prefix="/packages", tags=["packages"])

def _get_admin_or_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Allow both admin and super_admin to manage packages."""
    if current_user.role not in (UserRole.admin, UserRole.super_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. Admin or Super Admin role required."
        )
    return current_user

@router.post("/", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
def create_package(
    package_in: PackageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_admin_or_superadmin)
):
    """Create a new package for the current tenant."""
    # Check for duplicate name within the same tenant
    existing = db.query(Package).filter(
        Package.name == package_in.name,
        Package.tenant_id == current_user.tenant_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Package name already exists for this tenant")

    new_package = Package(**package_in.model_dump(), tenant_id=current_user.tenant_id)
    db.add(new_package)
    db.commit()
    db.refresh(new_package)
    return new_package

@router.get("/", response_model=List[PackageResponse])
def get_packages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all packages belonging to the current tenant."""
    return (
        db.query(Package)
        .filter(Package.tenant_id == current_user.tenant_id)
        .order_by(Package.name)
        .all()
    )

@router.get("/{package_id}", response_model=PackageResponse)
def get_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single package by ID (must belong to current tenant)."""
    package = db.query(Package).filter(
        Package.id == package_id,
        Package.tenant_id == current_user.tenant_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return package

@router.put("/{package_id}", response_model=PackageResponse)
def update_package(
    package_id: int,
    package_in: PackageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_admin_or_superadmin)
):
    """Update an existing package (must belong to current tenant)."""
    package = db.query(Package).filter(
        Package.id == package_id,
        Package.tenant_id == current_user.tenant_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    # Check for name collision if name is being changed
    update_data = package_in.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != package.name:
        conflict = db.query(Package).filter(
            Package.name == update_data["name"],
            Package.tenant_id == current_user.tenant_id,
            Package.id != package_id
        ).first()
        if conflict:
            raise HTTPException(status_code=400, detail="Another package with this name already exists")

    for field, value in update_data.items():
        setattr(package, field, value)

    db.commit()
    db.refresh(package)
    return package

@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_admin_or_superadmin)
):
    """Delete a package (must belong to current tenant)."""
    package = db.query(Package).filter(
        Package.id == package_id,
        Package.tenant_id == current_user.tenant_id
    ).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    db.delete(package)
    db.commit()
    return None
