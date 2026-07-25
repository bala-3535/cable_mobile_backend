import re
import os

filepath = 'routers/customers.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# ensure_billing_record
content = content.replace(
    'record = db.query(BillingRecord).filter(\n        BillingRecord.customer_id == customer.id,',
    'record = db.query(BillingRecord).filter(\n        BillingRecord.tenant_id == customer.tenant_id,\n        BillingRecord.customer_id == customer.id,'
)
content = content.replace(
    'db.query(BillingRecord).filter(\n        BillingRecord.customer_id == customer.id\n    ).order_by',
    'db.query(BillingRecord).filter(\n        BillingRecord.tenant_id == customer.tenant_id,\n        BillingRecord.customer_id == customer.id\n    ).order_by'
)
content = content.replace(
    'new_record = BillingRecord(\n        customer_id=customer.id,',
    'new_record = BillingRecord(\n        tenant_id=customer.tenant_id,\n        customer_id=customer.id,'
)
content = content.replace(
    'db.query(Package).filter(Package.name == customer.subscription_plan).first()',
    'db.query(Package).filter(Package.name == customer.subscription_plan, Package.tenant_id == customer.tenant_id).first()'
)

# create_customer
content = content.replace(
    'db_package = db.query(Package).filter(Package.name == customer_in.subscription_plan).first()',
    'db_package = db.query(Package).filter(Package.name == customer_in.subscription_plan, Package.tenant_id == current_user.tenant_id).first()'
)
content = content.replace(
    'new_customer = Customer(\n        **customer_in.model_dump',
    'new_customer = Customer(\n        tenant_id=current_user.tenant_id,\n        **customer_in.model_dump'
)
content = content.replace(
    'billing_record = BillingRecord(\n        customer_id=new_customer.id,',
    'billing_record = BillingRecord(\n        tenant_id=current_user.tenant_id,\n        customer_id=new_customer.id,'
)
content = content.replace(
    'initial_transaction = Transaction(\n            customer_id=new_customer.id,',
    'initial_transaction = Transaction(\n            tenant_id=current_user.tenant_id,\n            customer_id=new_customer.id,'
)

# get_customers
content = content.replace(
    'query = db.query(Customer)',
    'query = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id)'
)

# get_daily_collection
content = content.replace(
    'query = db.query(\n        Transaction.id.label("transaction_id"),',
    'query = db.query(\n        Transaction.id.label("transaction_id"),'
)
content = content.replace(
    '.filter(Transaction.payment_date >= day_start, Transaction.payment_date <= day_end)',
    '.filter(Transaction.tenant_id == current_user.tenant_id, Transaction.payment_date >= day_start, Transaction.payment_date <= day_end)'
)

# get_area_stats
content = content.replace(
    'func.sum(case((Customer.balance_due > 0, 1), else_=0)).label("unpaid_customers")\n    ).group_by',
    'func.sum(case((Customer.balance_due > 0, 1), else_=0)).label("unpaid_customers")\n    ).filter(Customer.tenant_id == current_user.tenant_id).group_by'
)

# get_ai_overview
content = content.replace(
    'total_customers = db.query(Customer).count()',
    'total_customers = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id).count()'
)
content = content.replace(
    'total_due = db.query(func.sum(Customer.balance_due)).scalar() or 0',
    'total_due = db.query(func.sum(Customer.balance_due)).filter(Customer.tenant_id == current_user.tenant_id).scalar() or 0'
)
content = content.replace(
    'unpaid_count = db.query(Customer).filter(Customer.balance_due > 0).count()',
    'unpaid_count = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id, Customer.balance_due > 0).count()'
)
content = content.replace(
    'recent_transactions = db.query(Transaction, Customer.customer_name)\\\n        .join(Customer).order_by',
    'recent_transactions = db.query(Transaction, Customer.customer_name)\\\n        .join(Customer).filter(Transaction.tenant_id == current_user.tenant_id).order_by'
)
content = content.replace(
    'area_stats = db.query(\n        Customer.area,\n        func.count(Customer.id).label("count"),\n        func.sum(Customer.balance_due).label("due")\n    ).group_by(Customer.area).all()',
    'area_stats = db.query(\n        Customer.area,\n        func.count(Customer.id).label("count"),\n        func.sum(Customer.balance_due).label("due")\n    ).filter(Customer.tenant_id == current_user.tenant_id).group_by(Customer.area).all()'
)

# get_dashboard_summary
content = content.replace(
    'today_collection = db.query(func.sum(Transaction.amount))\\\n        .filter(Transaction.payment_date >= today_start)',
    'today_collection = db.query(func.sum(Transaction.amount))\\\n        .filter(Transaction.tenant_id == current_user.tenant_id, Transaction.payment_date >= today_start)'
)
content = content.replace(
    'new_customers = db.query(Customer).filter(Customer.created_at >= today_start)',
    'new_customers = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id, Customer.created_at >= today_start)'
)
content = content.replace(
    'status_counts = db.query(Customer.account_status, func.count(Customer.id))\\\n        .group_by',
    'status_counts = db.query(Customer.account_status, func.count(Customer.id))\\\n        .filter(Customer.tenant_id == current_user.tenant_id).group_by'
)

# Common replacements for standard endpoints
content = content.replace(
    '.filter(Customer.id == customer_id)',
    '.filter(Customer.id == customer_id, Customer.tenant_id == current_user.tenant_id)'
)
content = content.replace(
    '.filter(BillingRecord.customer_id == customer_id)',
    '.filter(BillingRecord.customer_id == customer_id, BillingRecord.tenant_id == current_user.tenant_id)'
)
content = content.replace(
    'filter(Transaction.customer_id == customer_id)',
    'filter(Transaction.customer_id == customer_id, Transaction.tenant_id == current_user.tenant_id)'
)
content = content.replace(
    '.filter(Transaction.id == transaction_id)',
    '.filter(Transaction.id == transaction_id, Transaction.tenant_id == current_user.tenant_id)'
)

# new_transaction
content = content.replace(
    'new_transaction = Transaction(\n        customer_id=customer_id,',
    'new_transaction = Transaction(\n        tenant_id=current_user.tenant_id,\n        customer_id=customer_id,'
)

# generate_monthly_bills
content = content.replace(
    'active_customers = db.query(Customer).filter(\n        Customer.account_status == AccountStatus.active\n    ).all()',
    'active_customers = db.query(Customer).filter(\n        Customer.tenant_id == current_user.tenant_id,\n        Customer.account_status == AccountStatus.active\n    ).all()'
)
content = content.replace(
    'existing = db.query(BillingRecord).filter(\n            BillingRecord.customer_id == customer.id,',
    'existing = db.query(BillingRecord).filter(\n            BillingRecord.tenant_id == current_user.tenant_id,\n            BillingRecord.customer_id == customer.id,'
)

# upload_customers
content = content.replace(
    'existing = db.query(Customer).filter(Customer.account_number == acc_num).first()',
    'existing = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id, Customer.account_number == acc_num).first()'
)
content = content.replace(
    'customer = Customer(**row, created_by=current_user.id)',
    'customer = Customer(**row, created_by=current_user.id, tenant_id=current_user.tenant_id)'
)


with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("customers.py patched successfully")
