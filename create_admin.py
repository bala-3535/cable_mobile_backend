from database import SessionLocal, engine, Base
from models import User, UserRole, Tenant
from core.security import hash_password
from core.utils import get_ist_now

def create_initial_admin():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if default tenant exists
        tenant = db.query(Tenant).filter(Tenant.name == "Default System").first()
        if not tenant:
            tenant = Tenant(name="Default System")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print("Default tenant created.")

        # Check if super_admin already exists
        super_admin = db.query(User).filter(User.username == "superadmin").first()
        if super_admin:
            print("Super admin user already exists.")
            return

        new_admin = User(
            username="superadmin",
            password_hash=hash_password("superadmin123"), # Change this in production!
            role=UserRole.super_admin,
            is_active=True,
            tenant_id=tenant.id
        )
        db.add(new_admin)
        db.commit()
        print("Initial super admin user created successfully!")
        print("Username: admin")
        print("Password: admin123")
    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_admin()
