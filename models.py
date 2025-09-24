from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class YachtListing(Base):
    __tablename__ = 'yacht_listings'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    price = Column(Float)
    currency = Column(String(10), default='EUR')
    year = Column(Integer)
    brand = Column(String(100))
    model = Column(String(100))
    length = Column(Float)  # in meters
    location = Column(String(200))
    condition = Column(String(50))  # new, used, etc.
    description = Column(Text)
    seller_name = Column(String(200))
    seller_type = Column(String(50))  # dealer, private
    source_url = Column(String(1000), nullable=False)
    source_platform = Column(String(100), nullable=False)
    images = Column(Text)  # JSON string of image URLs
    hin = Column(String(50))  # Hull Identification Number
    mmsi = Column(String(20))  # Maritime Mobile Service Identity
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_duplicate = Column(Boolean, default=False)
    score = Column(Float, default=0.0)  # Attractiveness score
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'price': self.price,
            'currency': self.currency,
            'year': self.year,
            'brand': self.brand,
            'model': self.model,
            'length': self.length,
            'location': self.location,
            'condition': self.condition,
            'description': self.description,
            'seller_name': self.seller_name,
            'seller_type': self.seller_type,
            'source_url': self.source_url,
            'source_platform': self.source_platform,
            'images': self.images,
            'hin': self.hin,
            'mmsi': self.mmsi,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_duplicate': self.is_duplicate,
            'score': self.score
        }

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    company = Column(String(200))
    role = Column(String(20), default='user')  # user, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company': self.company,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SavedSearch(Base):
    __tablename__ = 'saved_searches'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    filters = Column(Text)  # JSON string of search filters
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'filters': self.filters,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ScrapeLog(Base):
    __tablename__ = 'scrape_logs'
    
    id = Column(Integer, primary_key=True)
    platform = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # success, failed
    listings_found = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'status': self.status,
            'listings_found': self.listings_found,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

# Database setup
DATABASE_URL = "sqlite:///yacht_platform.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

