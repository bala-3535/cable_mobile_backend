from fastapi import FastAPI
from database import engine, Base
from routers import users, customers, packages, daily_closing, faults, health
from core.config import settings
from core.logging import setup_logging
from services.keep_alive import start_keep_alive
from contextlib import asynccontextmanager

# Setup structured logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start keep-alive service
    start_keep_alive()
    yield
    # Shutdown: Clean up if needed
    pass

# Create database tables
Base.metadata.create_all(bind=engine)

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Cable Service Management API",
    lifespan=lifespan
)

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins, change this for production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(users.router)
app.include_router(customers.router)
app.include_router(packages.router)
app.include_router(daily_closing.router)
app.include_router(faults.router)

@app.get("/")
def root():
    return {"message": "Welcome to Cable Service User Management System API"}
