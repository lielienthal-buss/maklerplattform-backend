from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
import hashlib
import jwt
from datetime import datetime, timedelta
import os

from models import (
    YachtListing, User, SavedSearch, ScrapeLog, 
    get_db, create_tables, SessionLocal
)
from scrapers import run_scraping
from deduplication import run_deduplication_and_scoring

app = FastAPI(title="Yacht Platform API", version="1.0.0")

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://maklerplattform.vercel.app"],  # In production, specify actual frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
SECRET_KEY = "yacht_platform_secret_key_change_in_production"

# Create tables on startup
@app.on_event("startup")
async def startup_event():
    create_tables()
    
    # Create default admin user if not exists
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter_by(email="admin@yachtplatform.com").first()
        if not admin_user:
            admin_user = User(
                email="admin@yachtplatform.com",
                password_hash=hash_password("admin123"),
                first_name="Admin",
                last_name="User",
                company="Yacht Platform",
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            print("Default admin user created: admin@yachtplatform.com / admin123")
    finally:
        db.close()

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == hashed

def create_access_token(user_id: int, email: str, role: str) -> str:
    """Create JWT access token"""
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get current user from JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_admin(current_user: User = Depends(get_current_user)):
    """Require admin role"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Authentication endpoints
@app.post("/auth/register")
async def register(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    company: str = None,
    db: Session = Depends(get_db)
):
    """Register new user"""
    # Check if user exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        company=company
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create access token
    token = create_access_token(user.id, user.email, user.role)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }

@app.post("/auth/login")
async def login(email: str, password: str, db: Session = Depends(get_db)):
    """Login user"""
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account deactivated")
    
    token = create_access_token(user.id, user.email, user.role)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict()
    }

# Yacht listings endpoints
@app.get("/listings")
async def get_listings(
    skip: int = 0,
    limit: int = 50,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    location: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get yacht listings with filters"""
    query = db.query(YachtListing).filter(YachtListing.is_duplicate == False)
    
    if brand:
        query = query.filter(YachtListing.brand.ilike(f"%{brand}%"))
    if min_price:
        query = query.filter(YachtListing.price >= min_price)
    if max_price:
        query = query.filter(YachtListing.price <= max_price)
    if min_year:
        query = query.filter(YachtListing.year >= min_year)
    if max_year:
        query = query.filter(YachtListing.year <= max_year)
    if location:
        query = query.filter(YachtListing.location.ilike(f"%{location}%"))
    
    total = query.count()
    listings = query.order_by(YachtListing.score.desc()).offset(skip).limit(limit).all()
    
    return {
        "listings": [listing.to_dict() for listing in listings],
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/listings/{listing_id}")
async def get_listing(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single yacht listing"""
    listing = db.query(YachtListing).filter(YachtListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    return listing.to_dict()

# Scraping endpoints
@app.post("/scrape")
async def trigger_scraping(current_user: User = Depends(get_current_user)):
    """Trigger scraping of all platforms"""
    try:
        results = run_scraping()
        return {
            "message": "Scraping completed",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.post("/deduplicate-and-score")
async def trigger_deduplication_and_scoring(current_user: User = Depends(get_current_user)):
    """Trigger deduplication and scoring of listings"""
    try:
        results = run_deduplication_and_scoring()
        return {
            "message": "Deduplication and scoring completed",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deduplication and scoring failed: {str(e)}")

# Saved searches endpoints
@app.post("/saved-searches")
async def create_saved_search(
    name: str,
    filters: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create saved search"""
    import json
    
    saved_search = SavedSearch(
        user_id=current_user.id,
        name=name,
        filters=json.dumps(filters)
    )
    db.add(saved_search)
    db.commit()
    db.refresh(saved_search)
    
    return saved_search.to_dict()

@app.get("/saved-searches")
async def get_saved_searches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's saved searches"""
    searches = db.query(SavedSearch).filter(SavedSearch.user_id == current_user.id).all()
    return [search.to_dict() for search in searches]

@app.delete("/saved-searches/{search_id}")
async def delete_saved_search(
    search_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete saved search"""
    search = db.query(SavedSearch).filter(
        SavedSearch.id == search_id,
        SavedSearch.user_id == current_user.id
    ).first()
    
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")
    
    db.delete(search)
    db.commit()
    
    return {"message": "Saved search deleted"}

# Admin endpoints
@app.get("/admin/users")
async def get_all_users(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all users (admin only)"""
    users = db.query(User).all()
    return [user.to_dict() for user in users]

@app.put("/admin/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    is_active: bool,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user status (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = is_active
    db.commit()
    
    return {"message": f"User {'activated' if is_active else 'deactivated'}"}

@app.get("/admin/scrape-logs")
async def get_scrape_logs(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get scraping logs (admin only)"""
    logs = db.query(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(100).all()
    return [log.to_dict() for log in logs]

@app.get("/admin/stats")
async def get_admin_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get platform statistics (admin only)"""
    total_listings = db.query(YachtListing).count()
    active_listings = db.query(YachtListing).filter(YachtListing.is_duplicate == False).count()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    return {
        "total_listings": total_listings,
        "active_listings": active_listings,
        "duplicate_listings": total_listings - active_listings,
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users
    }

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

