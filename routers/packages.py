from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import User, Package, UserRole
from ..schemas import PackageCreate, PackageResponse, PackageUpdate
from ..dependencies import get_current_user, role_required

router = APIRouter(prefix="/packages", tags=["packages"])

@router.post("/", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
def create_package(
    package_in: PackageCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(role_required(UserRole.admin))
):
    db_package = db.query(Package).filter(Package.name == package_in.name).first()
    if db_package:
        raise HTTPException(status_code=400, detail="Package name already exists")
    
    new_package = Package(**package_in.model_dump())
    db.add(new_package)
    db.commit()
    db.refresh(new_package)
    return new_package

@router.get("/", response_model=List[PackageResponse])
def get_packages(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    return db.query(Package).all()

@router.put("/{package_id}", response_model=PackageResponse)
def update_package(
    package_id: int,
    package_in: PackageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(UserRole.admin))
):
    package = db.query(Package).filter(Package.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    
    update_data = package_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(package, field, value)
    
    db.commit()
    db.refresh(package)
    return package

@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(
    package_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(role_required(UserRole.admin))
):
    package = db.query(Package).filter(Package.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    db.delete(package)
    db.commit()
    return None
