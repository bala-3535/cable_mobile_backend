from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from .models import UserRole, ConnectionType, AccountStatus, BillingStatus, ClosingStatus, FaultStatus

# User Schemas
class UserBase(BaseModel):
    username: str
    role: UserRole
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Billing Record Schemas
class BillingRecordBase(BaseModel):
    customer_id: int
    billing_period: str
    amount_charged: float
    amount_paid: float = 0
    balance_due: float = 0
    status: BillingStatus = BillingStatus.unpaid

class BillingRecordCreate(BillingRecordBase):
    pass

class BillingRecordResponse(BillingRecordBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Customer Schemas
class CustomerBase(BaseModel):
    account_number: str
    customer_name: str
    address: str
    phone_number: str
    area: Optional[str] = None
    box_detail: Optional[str] = None
    subscription_plan: str
    connection_type: ConnectionType
    billing_day: int = 1
    amount_paid: float = 0
    balance_due: float = 0
    account_status: AccountStatus = AccountStatus.active

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(CustomerBase):
    account_number: Optional[str] = None
    customer_name: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    area: Optional[str] = None
    box_detail: Optional[str] = None
    subscription_plan: Optional[str] = None
    connection_type: Optional[ConnectionType] = None
    account_status: Optional[AccountStatus] = None

class CustomerPaymentPatch(BaseModel):
    amount_paid: float
    balance_due: float
    amount_just_paid: float
    notes: Optional[str] = None

class CustomerResponse(CustomerBase):
    id: int
    created_by: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CustomerDetailResponse(CustomerResponse):
    billing_history: List[BillingRecordResponse] = []
    transactions: List[TransactionResponse] = []

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

# Package Schemas
class PackageBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    connection_type: ConnectionType
    is_active: bool = True

class PackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    connection_type: Optional[ConnectionType] = None
    is_active: Optional[bool] = None

class PackageCreate(PackageBase):
    pass

class PackageResponse(PackageBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Transaction Schemas
class TransactionBase(BaseModel):
    customer_id: int
    amount: float
    notes: Optional[str] = None

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    notes: Optional[str] = None

class TransactionResponse(TransactionBase):
    id: int
    billing_period: str
    payment_date: datetime
    collected_by: Optional[int] = None
    collected_by_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class DailyCollectionResponse(BaseModel):
    transaction_id: int
    customer_id: int
    customer_name: str
    account_number: str
    amount: float
    payment_date: datetime
    notes: Optional[str] = None
    collected_by_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Daily Closing Schemas
class DailyClosingBase(BaseModel):
    agent_id: int
    date: datetime
    system_amount: float
    submitted_amount: float
    verified_amount: Optional[float] = None
    status: ClosingStatus = ClosingStatus.pending
    expenses_amount: float = 0
    expenses_detail: Optional[str] = None
    notes: Optional[str] = None

class DailyClosingCreate(BaseModel):
    date: datetime
    submitted_amount: float
    expenses_amount: float = 0
    expenses_detail: Optional[str] = None
    notes: Optional[str] = None

class DailyClosingVerify(BaseModel):
    verified_amount: float
    notes: Optional[str] = None

class DailyClosingResponse(DailyClosingBase):
    id: int
    submitted_at: datetime
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    agent_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Fault Schemas
class FaultBase(BaseModel):
    customer_id: int
    description: str
    status: FaultStatus = FaultStatus.open
    resolution_notes: Optional[str] = None

class FaultCreate(BaseModel):
    customer_id: int
    description: str

class FaultUpdate(BaseModel):
    status: Optional[FaultStatus] = None
    resolution_notes: Optional[str] = None

class FaultResponse(FaultBase):
    id: int
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime
    resolved_by: Optional[int] = None
    resolved_by_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
