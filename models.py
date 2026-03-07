from sqlalchemy import Column, Integer, String, Enum, Boolean, ForeignKey, DECIMAL, TIMESTAMP, Text, func
from .database import Base
import enum

class UserRole(str, enum.Enum):
    admin = "admin"
    agent = "agent"

class ConnectionType(str, enum.Enum):
    cable = "cable"
    internet = "internet"

class AccountStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    inactive = "inactive"

class BillingStatus(str, enum.Enum):
    paid = "paid"
    partial = "partial"
    unpaid = "unpaid"

class ClosingStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"

class FaultStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_name = Column(String(150), nullable=False)
    address = Column(Text, nullable=False)
    phone_number = Column(String(20), nullable=False)
    area = Column(String(100), nullable=True, index=True)
    box_detail = Column(String(100), nullable=True)
    subscription_plan = Column(String(100), nullable=False)
    connection_type = Column(Enum(ConnectionType), nullable=False)
    billing_day = Column(Integer, default=1, nullable=False)
    amount_paid = Column(DECIMAL(10, 2), default=0)
    balance_due = Column(DECIMAL(10, 2), default=0)
    account_status = Column(Enum(AccountStatus), default=AccountStatus.active)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, server_default=func.now())

class BillingRecord(Base):
    __tablename__ = "billing_records"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    billing_period = Column(String(7), nullable=False)  # YYYY-MM
    amount_charged = Column(DECIMAL(10, 2), nullable=False)
    amount_paid = Column(DECIMAL(10, 2), default=0)
    balance_due = Column(DECIMAL(10, 2), default=0)
    status = Column(Enum(BillingStatus), default=BillingStatus.unpaid)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Package(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    connection_type = Column(Enum(ConnectionType), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    billing_period = Column(String(7), nullable=False)  # YYYY-MM relation
    amount = Column(DECIMAL(10, 2), nullable=False)
    payment_date = Column(TIMESTAMP, server_default=func.now())
    notes = Column(Text, nullable=True)
    collected_by = Column(Integer, ForeignKey("users.id"), nullable=True)

class DailyClosing(Base):
    __tablename__ = "daily_closings"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(TIMESTAMP, nullable=False)
    system_amount = Column(DECIMAL(10, 2), nullable=False)
    submitted_amount = Column(DECIMAL(10, 2), nullable=False)
    verified_amount = Column(DECIMAL(10, 2), nullable=True)
    status = Column(Enum(ClosingStatus), default=ClosingStatus.pending)
    submitted_at = Column(TIMESTAMP, server_default=func.now())
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(TIMESTAMP, nullable=True)
    expenses_amount = Column(DECIMAL(10, 2), default=0)
    expenses_detail = Column(Text, nullable=True)  # JSON string of expense items
    notes = Column(Text, nullable=True)

class Fault(Base):
    __tablename__ = "faults"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(Enum(FaultStatus), default=FaultStatus.open)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(TIMESTAMP, nullable=True)
    resolution_notes = Column(Text, nullable=True)

