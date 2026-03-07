from app.database import SessionLocal, engine, Base
from app.models import User, UserRole
from app.core.security import hash_password

def create_initial_admin():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if admin already exists
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            print("Admin user already exists.")
            return

        new_admin = User(
            username="admin",
            password_hash=hash_password("admin123"), # Change this in production!
            role=UserRole.admin,
            is_active=True
        )
        db.add(new_admin)
        db.commit()
        print("Initial admin user created successfully!")
        print("Username: admin")
        print("Password: admin123")
    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_admin()
