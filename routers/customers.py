from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional
from datetime import datetime, date as date_type
from core.utils import get_ist_now
import io
from database import get_db
from models import User, UserRole, Customer, ConnectionType, AccountStatus, BillingRecord, BillingStatus, Package, Transaction
from schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerDetailResponse,
    BillingRecordCreate, BillingRecordResponse,
    CustomerPaymentPatch, TransactionResponse, TransactionUpdate
)
from pydantic import BaseModel
from dependencies import get_current_user, role_required
from core.ai_service import process_file_data, generate_admin_insight
from schemas import DailyCollectionResponse


router = APIRouter(prefix="/customers", tags=["customers"])

def ensure_billing_record(db: Session, customer: Customer) -> BillingRecord:
    billing_period = get_ist_now().strftime("%Y-%m")
    
    # Check if record for current month exists
    record = db.query(BillingRecord).filter(
        BillingRecord.tenant_id == customer.tenant_id,
        BillingRecord.customer_id == customer.id,
        BillingRecord.billing_period == billing_period
    ).first()
    
    if record:
        return record
        
    # If not, create new one. Get latest record to carry forward balance
    latest_record = db.query(BillingRecord).filter(
        BillingRecord.tenant_id == customer.tenant_id,
        BillingRecord.customer_id == customer.id
    ).order_by(BillingRecord.billing_period.desc()).first()
    
    previous_balance = float(latest_record.balance_due) if latest_record else 0.0
    
    # Get package price
    db_package = db.query(Package).filter(Package.name == customer.subscription_plan, Package.tenant_id == customer.tenant_id).first()
    package_price = float(db_package.price) if db_package else 0.0
    
    new_balance = package_price + previous_balance
    
    new_record = BillingRecord(
        tenant_id=customer.tenant_id,
        customer_id=customer.id,
        billing_period=billing_period,
        amount_charged=package_price,
        amount_paid=0.0,
        balance_due=new_balance,
        status=BillingStatus.unpaid
    )
    
    # Update customer cumulative balance
    customer.balance_due = new_balance
    
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    db.refresh(customer)
    
    return new_record

@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_in: CustomerCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(role_required(UserRole.admin))
):
    # Check if account number already exists (globally unique)
    existing_customer = db.query(Customer).filter(Customer.account_number == customer_in.account_number).first()
    if existing_customer:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account number {customer_in.account_number} already exists"
        )

    # Use provided billing_day if available, otherwise default to today's day
    billing_day = customer_in.billing_day if hasattr(customer_in, 'billing_day') and customer_in.billing_day else get_ist_now().day
    billing_period = get_ist_now().strftime("%Y-%m")
    
    # Get package for initial billing
    db_package = db.query(Package).filter(Package.name == customer_in.subscription_plan, Package.tenant_id == current_user.tenant_id).first()
    if not db_package:
        raise HTTPException(status_code=400, detail="Subscription plan not found")
    
    package_price = float(db_package.price)
    amount_paid = float(customer_in.amount_paid)
    balance_due = package_price - amount_paid
    
    try:
        new_customer = Customer(
            tenant_id=current_user.tenant_id,
            **customer_in.model_dump(exclude={"balance_due", "billing_day", "amount_paid"}),
            billing_day=billing_day,
            amount_paid=amount_paid,
            balance_due=balance_due,
            created_by=current_user.id
        )
        db.add(new_customer)
        db.flush() # Flush to get ID without committing yet
        
        # Create initial billing record
        billing_status = BillingStatus.paid if balance_due <= 0 else (BillingStatus.partial if amount_paid > 0 else BillingStatus.unpaid)
        billing_record = BillingRecord(
            tenant_id=current_user.tenant_id,
            customer_id=new_customer.id,
            billing_period=billing_period,
            amount_charged=package_price,
            amount_paid=amount_paid,
            balance_due=balance_due,
            status=billing_status
        )
        db.add(billing_record)
        
        # Create initial transaction record if payment was made
        if amount_paid > 0:
            initial_transaction = Transaction(
                tenant_id=current_user.tenant_id,
                customer_id=new_customer.id,
                billing_period=billing_period,
                amount=amount_paid,
                notes="Initial payment during registration",
                collected_by=current_user.id
            )
            db.add(initial_transaction)
        
        db.commit()
        db.refresh(new_customer)
        return new_customer
    except Exception as e:
        db.rollback()
        # Raise as HTTPException so FastAPI returns JSON instead of text/plain 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during customer creation: {str(e)}"
        )

@router.get("/", response_model=List[CustomerResponse])
def get_customers(
    q: Optional[str] = None,
    only_unpaid: bool = False,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Admins see all, Agents see all
    query = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id)
    
    if only_unpaid:
        query = query.filter(Customer.balance_due > 0)
    
    if q:
        query_text = q.strip()
        if query_text:
            search_terms = query_text.split()
            # If multiple words, match if ANY word appears in EITHER field
            # Or for more precision, match if EACH word appears in AT LEAST ONE field
            for term in search_terms:
                term_filter = f"%{term}%"
                query = query.filter(
                    (Customer.customer_name.ilike(term_filter)) |
                    (Customer.account_number.ilike(term_filter)) |
                    (Customer.phone_number.ilike(term_filter)) |
                    (Customer.address.ilike(term_filter))
                )
        
    customers = query.all()
    # Note: Removed ensure_billing_record loop to prevent connection pooling limits
    # and slow response times on the main customer list. 
    # Automated billing checks now only happen on single customer view or payment.
    return customers

@router.get("/daily-collection", response_model=List[DailyCollectionResponse])
def get_daily_collection(
    date: Optional[date_type] = None,
    agent_id: Optional[int] = None,
    area: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    selected_date = date if date else get_ist_now().date()
    day_start = datetime.combine(selected_date, datetime.min.time())
    day_end = datetime.combine(selected_date, datetime.max.time())
    
    query = db.query(
        Transaction.id.label("transaction_id"),
        Transaction.customer_id,
        Customer.customer_name,
        Customer.account_number,
        Transaction.amount,
        Transaction.payment_date,
        Transaction.notes,
        User.username.label("collected_by_name")
    ).join(Customer, Transaction.customer_id == Customer.id)\
     .outerjoin(User, Transaction.collected_by == User.id)\
     .filter(Transaction.tenant_id == current_user.tenant_id, Transaction.payment_date >= day_start, Transaction.payment_date <= day_end)
    
    # Area filter
    if area:
        query = query.filter(Customer.area == area)
    
    # Security: Agents can only see their own collections
    if current_user.role != UserRole.admin:
        query = query.filter(Transaction.collected_by == current_user.id)
    elif agent_id:
        # Admin can filter by specific agent
        query = query.filter(Transaction.collected_by == agent_id)
        
    results = query.order_by(Transaction.payment_date.desc()).all()
    return results

@router.get("/stats/areas")
def get_area_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = db.query(
        Customer.area,
        func.count(Customer.id).label("total_customers"),
        func.sum(Customer.balance_due).label("total_due"),
        func.sum(Customer.amount_paid).label("total_collected"),
        func.sum(case((Customer.balance_due > 0, 1), else_=0)).label("unpaid_customers")
    ).filter(Customer.tenant_id == current_user.tenant_id).group_by(Customer.area).all()
    
    return [
        {
            "area": r.area or "Unassigned",
            "total_customers": r.total_customers,
            "total_due": float(r.total_due or 0),
            "total_collected": float(r.total_collected or 0),
            "unpaid_customers": r.unpaid_customers
        }
        for r in results
    ]

@router.get("/stats/ai-overview")
def get_ai_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.admin:
         raise HTTPException(status_code=403, detail="Admin access required")
         
    total_customers = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id).count()
    total_due = db.query(func.sum(Customer.balance_due)).filter(Customer.tenant_id == current_user.tenant_id).scalar() or 0
    unpaid_count = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id, Customer.balance_due > 0).count()
    
    recent_transactions = db.query(Transaction, Customer.customer_name)\
        .join(Customer).filter(Transaction.tenant_id == current_user.tenant_id).order_by(Transaction.payment_date.desc()).limit(15).all()
        
    area_stats = db.query(
        Customer.area,
        func.count(Customer.id).label("count"),
        func.sum(Customer.balance_due).label("due")
    ).filter(Customer.tenant_id == current_user.tenant_id).group_by(Customer.area).all()
    
    data = {
        "total_customers": total_customers,
        "total_due": float(total_due),
        "unpaid_count": unpaid_count,
        "area_performance": [
            {"area": r.area or "Unassigned", "customers": r.count, "unpaid_balance": float(r.due or 0)} 
            for r in area_stats
        ],
        "recent_activity": [
            {"customer": r[1], "amount": float(r[0].amount), "time": r[0].payment_date.strftime("%H:%M")}
            for r in recent_transactions
        ]
    }
    
    insight = generate_admin_insight(data)
    return {"insight": insight}

@router.get("/stats/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    today_start = get_ist_now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Collection today
    today_collection = db.query(func.sum(Transaction.amount))\
        .filter(Transaction.tenant_id == current_user.tenant_id, Transaction.payment_date >= today_start).scalar() or 0
        
    # New customers today
    new_customers = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id, Customer.created_at >= today_start).count()
    
    # Status breakdown
    status_counts = db.query(Customer.account_status, func.count(Customer.id))\
        .filter(Customer.tenant_id == current_user.tenant_id).group_by(Customer.account_status).all()
        
    # Pending billing (total due)
    total_due = db.query(func.sum(Customer.balance_due)).filter(Customer.tenant_id == current_user.tenant_id).scalar() or 0

    return {
        "today_collection": float(today_collection),
        "new_customers_today": new_customers,
        "total_due": float(total_due),
        "status_breakdown": {s.name: count for s, count in status_counts}
    }

@router.get("/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(
    customer_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == current_user.tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    ensure_billing_record(db, customer)
    
    # Fetch billing history
    history = db.query(BillingRecord).filter(BillingRecord.customer_id == customer_id, BillingRecord.tenant_id == current_user.tenant_id).order_by(BillingRecord.billing_period.desc()).all()
    
    # Fetch transactions with collector names
    transactions_query = db.query(
        Transaction.id,
        Transaction.customer_id,
        Transaction.billing_period,
        Transaction.amount,
        Transaction.payment_date,
        Transaction.notes,
        Transaction.collected_by,
        User.username.label("collected_by_name")
    ).outerjoin(User, Transaction.collected_by == User.id)\
     .filter(Transaction.customer_id == customer_id, Transaction.tenant_id == current_user.tenant_id)\
     .order_by(Transaction.payment_date.desc())\
     .all()

    # Convert to response object
    return {
        **customer.__dict__,
        "billing_history": history,
        "transactions": transactions_query
    }

@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int, 
    customer_in: CustomerUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == current_user.tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    update_data = customer_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)
    
    db.commit()
    db.refresh(customer)
    return customer

@router.patch("/payment/{customer_id}", response_model=CustomerResponse)
def update_payment(
    customer_id: int, 
    payment_in: CustomerPaymentPatch, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == current_user.tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    billing_period = get_ist_now().strftime("%Y-%m")

    # Ensure billing record exists for this month
    billing_record = db.query(BillingRecord).filter(
        BillingRecord.customer_id == customer_id,
        BillingRecord.tenant_id == current_user.tenant_id,
        BillingRecord.billing_period == billing_period
    ).first()
    
    if not billing_record:
        billing_record = ensure_billing_record(db, customer)

    # Create the transaction record FIRST
    new_transaction = Transaction(
        tenant_id=current_user.tenant_id,
        customer_id=customer_id,
        billing_period=billing_period,
        amount=payment_in.amount_just_paid,
        notes=payment_in.notes,
        collected_by=current_user.id
    )
    db.add(new_transaction)
    db.flush()  # Flush so the new transaction is included in the sum below

    # Re-sum all transactions for this period to get accurate monthly total
    total_paid_this_period = db.query(func.sum(Transaction.amount)).filter(
        Transaction.tenant_id == current_user.tenant_id,
        Transaction.customer_id == customer_id,
        Transaction.billing_period == billing_period
    ).scalar() or 0.0
    total_paid_this_period = float(total_paid_this_period)

    amount_charged = float(billing_record.amount_charged)
    # Carry-over from previous balance (amount_charged already includes it from ensure_billing_record)
    new_billing_balance = amount_charged - total_paid_this_period

    billing_record.amount_paid = total_paid_this_period
    billing_record.balance_due = new_billing_balance
    billing_record.status = (
        BillingStatus.paid if new_billing_balance <= 0
        else (BillingStatus.partial if total_paid_this_period > 0 else BillingStatus.unpaid)
    )

    # Update the customer-level running totals
    customer.amount_paid = payment_in.amount_paid
    customer.balance_due = payment_in.balance_due
    
    db.commit()
    db.refresh(customer)
    return customer

@router.get("/{customer_id}/history", response_model=List[BillingRecordResponse])
def get_billing_history(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(BillingRecord).filter(BillingRecord.customer_id == customer_id, BillingRecord.tenant_id == current_user.tenant_id).order_by(BillingRecord.billing_period.desc()).all()

@router.get("/{customer_id}/transactions", response_model=List[TransactionResponse])
def get_transactions(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = db.query(
        Transaction.id,
        Transaction.customer_id,
        Transaction.billing_period,
        Transaction.amount,
        Transaction.payment_date,
        Transaction.notes,
        Transaction.collected_by,
        User.username.label("collected_by_name")
    ).outerjoin(User, Transaction.collected_by == User.id)\
     .filter(Transaction.customer_id == customer_id, Transaction.tenant_id == current_user.tenant_id)\
     .order_by(Transaction.payment_date.desc())\
     .all()
    return results

@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.tenant_id == current_user.tenant_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    customer = db.query(Customer).filter(Customer.id == transaction.customer_id, Customer.tenant_id == current_user.tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # If amount changes, update customer and billing record balances
    if transaction_update.amount is not None:
        diff = float(transaction_update.amount) - float(transaction.amount)
        
        transaction.amount = transaction_update.amount
        customer.amount_paid = float(customer.amount_paid) + diff
        customer.balance_due = float(customer.balance_due) - diff
        
        # Update matching billing record
        billing_record = db.query(BillingRecord).filter(
            BillingRecord.tenant_id == current_user.tenant_id,
            BillingRecord.customer_id == customer.id,
            BillingRecord.billing_period == transaction.billing_period
        ).first()
        
        if billing_record:
            billing_record.amount_paid = float(billing_record.amount_paid) + diff
            billing_record.balance_due = float(billing_record.balance_due) - diff
            billing_record.status = BillingStatus.paid if billing_record.balance_due <= 0 else (BillingStatus.partial if billing_record.amount_paid > 0 else BillingStatus.unpaid)

    if transaction_update.notes is not None:
        transaction.notes = transaction_update.notes

    db.commit()
    
    # Re-query with join to get collected_by_name
    result = db.query(
        Transaction.id,
        Transaction.customer_id,
        Transaction.billing_period,
        Transaction.amount,
        Transaction.payment_date,
        Transaction.notes,
        Transaction.collected_by,
        User.username.label("collected_by_name")
    ).outerjoin(User, Transaction.collected_by == User.id)\
     .filter(Transaction.id == transaction_id, Transaction.tenant_id == current_user.tenant_id)\
     .first()

    return result

@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.tenant_id == current_user.tenant_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    customer = db.query(Customer).filter(Customer.id == transaction.customer_id, Customer.tenant_id == current_user.tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Reverse the payment on customer and billing record
    amount = float(transaction.amount)
    customer.amount_paid = float(customer.amount_paid) - amount
    customer.balance_due = float(customer.balance_due) + amount
    
    billing_record = db.query(BillingRecord).filter(
        BillingRecord.tenant_id == customer.tenant_id,
        BillingRecord.customer_id == customer.id,
        BillingRecord.billing_period == transaction.billing_period
    ).first()
    
    if billing_record:
        billing_record.amount_paid = float(billing_record.amount_paid) - amount
        billing_record.balance_due = float(billing_record.balance_due) + amount
        billing_record.status = BillingStatus.paid if billing_record.balance_due <= 0 else (BillingStatus.partial if billing_record.amount_paid > 0 else BillingStatus.unpaid)

    db.delete(transaction)
    db.commit()
    return None


@router.post("/generate-monthly-bills", status_code=status.HTTP_200_OK)
def generate_monthly_bills(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(UserRole.admin))
):
    """
    Admin-only endpoint. Auto-generates billing records for ALL active customers
    for the current month if they don't already have one.
    Call this once at the start of each billing month.
    """
    billing_period = get_ist_now().strftime("%Y-%m")
    active_customers = db.query(Customer).filter(
        Customer.tenant_id == current_user.tenant_id,
        Customer.account_status == AccountStatus.active
    ).all()

    created_count = 0
    skipped_count = 0

    for customer in active_customers:
        existing = db.query(BillingRecord).filter(
            BillingRecord.tenant_id == current_user.tenant_id,
            BillingRecord.customer_id == customer.id,
            BillingRecord.billing_period == billing_period
        ).first()
        if not existing:
            ensure_billing_record(db, customer)
            created_count += 1
        else:
            skipped_count += 1

    return {
        "message": f"Monthly bills generated for {billing_period}",
        "created": created_count,
        "already_existed": skipped_count,
        "total_customers": len(active_customers)
    }


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(role_required(UserRole.admin))
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == current_user.tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    db.delete(customer)
    db.commit()
    return None

@router.post("/upload-customers", status_code=status.HTTP_201_CREATED)
async def upload_customers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Only Excel and CSV files are supported")
    
    contents = await file.read()
    try:
        mapped_rows = process_file_data(contents, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Processing failed: {str(e)}")

    customers_added = 0
    errors = []
    processed_account_numbers = set()

    for row in mapped_rows:
        try:
            # Normalize account number to string
            acc_num = str(row.get('account_number', '')).strip()
            if not acc_num:
                continue
                
            row['account_number'] = acc_num

            # Check if already processed in this batch
            if acc_num in processed_account_numbers:
                errors.append(f"Customer {acc_num} duplicated in file")
                continue
            
            # Check if customer already exists in DB (account_number is globally unique across all tenants)
            existing = db.query(Customer).filter(Customer.account_number == acc_num).first()
            if existing:
                if existing.tenant_id == current_user.tenant_id:
                    errors.append(f"Customer {acc_num} already exists in your database")
                else:
                    errors.append(f"Customer {acc_num} already exists under a different account")
                continue

            # Handle optional fields and defaults
            if 'connection_type' in row:
                row['connection_type'] = ConnectionType(row['connection_type'])
            if 'account_status' in row:
                row['account_status'] = AccountStatus(row['account_status'])

            customer = Customer(**row, created_by=current_user.id, tenant_id=current_user.tenant_id)
            db.add(customer)
            customers_added += 1
            processed_account_numbers.add(acc_num)
        except Exception as e:
            errors.append(f"Error adding {row.get('account_number', 'unknown')}: {str(e)}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Import failed due to a database conflict: {str(e)}"
        )

    return {
        "message": f"Successfully imported {customers_added} customers",
        "total_attempted": len(mapped_rows),
        "errors": errors
    }

# Alias for backward compatibility
@router.post("/upload-excel", status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def upload_excel_alias(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await upload_customers(file, db, current_user)
