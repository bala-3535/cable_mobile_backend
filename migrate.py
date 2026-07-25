from database import engine
from sqlalchemy import text

def run_migrations():
    with engine.connect() as conn:
        print("Creating tenants table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tenants (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Add super_admin to enum
        try:
            print("Adding super_admin to enum...")
            conn.execute(text("ALTER TYPE userrole ADD VALUE 'super_admin'"))
            conn.commit()
        except Exception as e:
            print(f"Enum might already exist or error: {e}")
            conn.rollback()

        tables = [
            "users", "customers", "packages", "faults", 
            "daily_closings", "billing_records", "transactions"
        ]
        
        for table in tables:
            try:
                print(f"Adding tenant_id to {table}...")
                conn.execute(text(f"""
                    ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)
                """))
                conn.commit()
            except Exception as e:
                print(f"Error adding to {table}: {e}")
                conn.rollback()

        print("Migration complete!")

if __name__ == "__main__":
    run_migrations()
