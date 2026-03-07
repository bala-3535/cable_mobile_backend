from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, date as date_type
from database import get_db
from models import User, UserRole, Transaction, DailyClosing, ClosingStatus
from schemas import DailyClosingCreate, DailyClosingVerify, DailyClosingResponse
from dependencies import get_current_user, role_required

router = APIRouter(prefix="/daily-closing", tags=["daily-closing"])

@router.get("/summary", response_model=dict)
def get_daily_summary(
    date: Optional[date_type] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not date:
        today = datetime.now().date()
    else:
        today = date
        
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Calculate total collected by this agent today
    total_collected = db.query(func.sum(Transaction.amount)).filter(
        Transaction.collected_by == current_user.id,
        Transaction.payment_date >= today_start,
        Transaction.payment_date <= today_end
    ).scalar() or 0.0
    
    # Check if a closing report already exists
    existing_report = db.query(DailyClosing).filter(
        DailyClosing.agent_id == current_user.id,
        DailyClosing.date >= today_start,
        DailyClosing.date <= today_end
    ).first()
    
    return {
        "date": today,
        "system_amount": float(total_collected),
        "has_submitted": existing_report is not None,
        "status": existing_report.status if existing_report else None,
        "submitted_amount": float(existing_report.submitted_amount) if existing_report else 0.0,
        "expenses_amount": float(existing_report.expenses_amount) if existing_report else 0.0,
        "expenses_detail": existing_report.expenses_detail if existing_report else None,
        "notes": existing_report.notes if existing_report else None
    }

@router.post("/submit", response_model=DailyClosingResponse)
def submit_daily_closing(
    closing_in: DailyClosingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Agents can only submit for themselves
    # Check if already submitted for this date
    selected_date = closing_in.date.date()
    today_start = datetime.combine(selected_date, datetime.min.time())
    today_end = datetime.combine(selected_date, datetime.max.time())
    
    existing = db.query(DailyClosing).filter(
        DailyClosing.agent_id == current_user.id,
        DailyClosing.date >= today_start,
        DailyClosing.date <= today_end
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Daily closing already submitted for this date")
    
    # Calculate system amount
    system_amount = db.query(func.sum(Transaction.amount)).filter(
        Transaction.collected_by == current_user.id,
        Transaction.payment_date >= today_start,
        Transaction.payment_date <= today_end
    ).scalar() or 0.0
    
    new_closing = DailyClosing(
        agent_id=current_user.id,
        date=today_start, # Store as start of day
        system_amount=system_amount,
        submitted_amount=closing_in.submitted_amount,
        expenses_amount=closing_in.expenses_amount,
        expenses_detail=closing_in.expenses_detail,
        status=ClosingStatus.pending,
        notes=closing_in.notes
    )
    
    db.add(new_closing)
    db.commit()
    db.refresh(new_closing)
    
    # Add agent_name for response
    new_closing.agent_name = current_user.username
    return new_closing

@router.get("/list", response_model=List[DailyClosingResponse])
def list_daily_closings(
    date: Optional[date_type] = None,
    agent_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(UserRole.admin))
):
    query = db.query(
        DailyClosing.id,
        DailyClosing.agent_id,
        DailyClosing.date,
        DailyClosing.system_amount,
        DailyClosing.submitted_amount,
        DailyClosing.verified_amount,
        DailyClosing.status,
        DailyClosing.expenses_amount,
        DailyClosing.expenses_detail,
        DailyClosing.submitted_at,
        DailyClosing.verified_by,
        DailyClosing.verified_at,
        DailyClosing.notes,
        User.username.label("agent_name")
    ).join(User, DailyClosing.agent_id == User.id)
    
    if date:
        today_start = datetime.combine(date, datetime.min.time())
        today_end = datetime.combine(date, datetime.max.time())
        query = query.filter(DailyClosing.date >= today_start, DailyClosing.date <= today_end)
        
    if agent_id:
        query = query.filter(DailyClosing.agent_id == agent_id)
        
    return query.order_by(DailyClosing.submitted_at.desc()).all()

@router.post("/{report_id}/verify", response_model=DailyClosingResponse)
def verify_daily_closing(
    report_id: int,
    verify_in: DailyClosingVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(UserRole.admin))
):
    report = db.query(DailyClosing).filter(DailyClosing.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Closing report not found")
        
    report.verified_amount = verify_in.verified_amount
    report.verified_by = current_user.id
    report.verified_at = datetime.now()
    report.status = ClosingStatus.verified
    if verify_in.notes:
        report.notes = (report.notes or "") + f"\nVerification notes: {verify_in.notes}"
    
    db.commit()
    db.refresh(report)
    
    # Get agent name for response
    agent = db.query(User).filter(User.id == report.agent_id).first()
    report.agent_name = agent.username if agent else "Unknown"
    
    return report
