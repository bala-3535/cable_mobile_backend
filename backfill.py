from database import engine
from sqlalchemy import text

def backfill():
    with engine.connect() as conn:
        tenant = conn.execute(text("SELECT id FROM tenants WHERE name='Default System' LIMIT 1")).fetchone()
        if not tenant:
            print("No default tenant found.")
            return
        
        t_id = tenant[0]
        
        tables = [
            "users", "customers", "packages", "faults", 
            "daily_closings", "billing_records", "transactions"
        ]
        
        for table in tables:
            print(f"Backfilling {table}...")
            # For users, maybe skip superadmin? Wait, superadmin is already tenant_id=1.
            # But just UPDATE where tenant_id IS NULL.
            conn.execute(text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": t_id})
            conn.commit()
            
            # Optionally add NOT NULL constraints on the columns that require it
            if table != "users":
                try:
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL"))
                    conn.commit()
                except Exception as e:
                    print(f"Failed to set NOT NULL on {table}: {e}")
                    conn.rollback()

        print("Backfill complete.")

if __name__ == "__main__":
    backfill()
