from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, desc
from typing import List, Optional
from datetime import timedelta, datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models
import schemas
import auth
from database import get_db, engine

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fast-Classified API", version="2.0.0")

# CORS Configuration
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://frontend-alpha-murex-49.vercel.app",
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
]

# Allow all vercel.app domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Vercel deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Root Endpoint ====================

@app.get("/")
def root():
    return {"message": "Fast-Classified API is running", "version": "2.0.0"}

@app.get("/api")
def api_root():
    return {"message": "Fast-Classified API is running", "version": "2.0.0"}

# ==================== Authentication Endpoints ====================

@app.post("/api/auth/signup", response_model=schemas.Token)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        role=models.UserRole(user.role)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create wallet for user
    wallet = models.Wallet(user_id=new_user.id)
    db.add(wallet)
    db.commit()
    
    access_token = auth.create_access_token(
        data={"sub": new_user.email},
        expires_delta=timedelta(days=7)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(
        data={"sub": db_user.email},
        expires_delta=timedelta(days=7)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
def get_me(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    profile = None
    if current_user.role == models.UserRole.STUDENT:
        profile = db.query(models.StudentProfile).filter(
            models.StudentProfile.user_id == current_user.id
        ).first()
    elif current_user.role == models.UserRole.TEACHER:
        profile = db.query(models.TeacherProfile).filter(
            models.TeacherProfile.user_id == current_user.id
        ).first()
    
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "profile": profile
    }

# ==================== Profile Endpoints ====================

@app.post("/api/profiles/student", response_model=schemas.StudentProfileResponse)
def create_student_profile(
    profile: schemas.StudentProfileCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Only students can create student profiles")
    
    existing = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    new_profile = models.StudentProfile(
        user_id=current_user.id,
        **profile.model_dump()
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile

@app.post("/api/profiles/teacher", response_model=schemas.TeacherProfileResponse)
def create_teacher_profile(
    profile: schemas.TeacherProfileCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can create teacher profiles")
    
    existing = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    new_profile = models.TeacherProfile(
        user_id=current_user.id,
        **profile.model_dump()
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile

@app.patch("/api/profiles/student/{profile_id}", response_model=schemas.StudentProfileResponse)
def update_student_profile(
    profile_id: str,
    profile_update: schemas.StudentProfileCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.id == profile_id,
        models.StudentProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    for key, value in profile_update.model_dump().items():
        setattr(profile, key, value)
    
    db.commit()
    db.refresh(profile)
    return profile

@app.patch("/api/profiles/teacher/{profile_id}", response_model=schemas.TeacherProfileResponse)
def update_teacher_profile(
    profile_id: str,
    profile_update: schemas.TeacherProfileCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.id == profile_id,
        models.TeacherProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    for key, value in profile_update.model_dump().items():
        setattr(profile, key, value)
    
    db.commit()
    db.refresh(profile)
    return profile

# ==================== Request Feed Endpoints ====================

@app.post("/api/requests", response_model=schemas.RequestResponse)
def create_request(
    request: schemas.RequestCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Only students can create requests")
    
    new_request = models.Request(
        student_id=current_user.id,
        **request.model_dump()
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    student_profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()
    
    response = schemas.RequestResponse(
        id=str(new_request.id),
        student_id=str(new_request.student_id),
        subject=new_request.subject,
        topic=new_request.topic,
        description=new_request.description,
        preferred_format=new_request.preferred_format,
        urgency_level=new_request.urgency_level,
        hourly_rate=new_request.hourly_rate,
        duration=new_request.duration,
        status=new_request.status.value,
        created_at=new_request.created_at,
        student_name=student_profile.name if student_profile else "Anonymous"
    )
    return response

@app.get("/api/requests", response_model=List[schemas.RequestResponse])
def get_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * per_page
    requests = db.query(models.Request).filter(
        models.Request.status == models.RequestStatus.ACTIVE
    ).order_by(desc(models.Request.created_at)).offset(offset).limit(per_page).all()
    
    result = []
    for req in requests:
        student_profile = db.query(models.StudentProfile).filter(
            models.StudentProfile.user_id == req.student_id
        ).first()
        
        result.append(schemas.RequestResponse(
            id=str(req.id),
            student_id=str(req.student_id),
            subject=req.subject,
            topic=req.topic,
            description=req.description,
            preferred_format=req.preferred_format,
            urgency_level=req.urgency_level,
            hourly_rate=req.hourly_rate,
            duration=req.duration,
            status=req.status.value,
            created_at=req.created_at,
            student_name=student_profile.name if student_profile else "Anonymous"
        ))
    return result

@app.delete("/api/requests/{request_id}")
def delete_request(
    request_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    request = db.query(models.Request).filter(
        models.Request.id == request_id,
        models.Request.student_id == current_user.id
    ).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    db.delete(request)
    db.commit()
    return {"message": "Request deleted successfully"}

# ==================== Teacher Search Endpoints ====================

@app.get("/api/teachers/search", response_model=List[schemas.TeacherProfileResponse])
def search_teachers(
    subject: Optional[str] = None,
    min_rate: Optional[float] = None,
    max_rate: Optional[float] = None,
    min_rating: Optional[float] = None,
    city: Optional[str] = None,
    format: Optional[str] = None,
    language: Optional[str] = None,
    experience_level: Optional[str] = None,
    verified_only: bool = False,
    sort_by: Optional[str] = "rating",
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.TeacherProfile)
    
    if subject:
        query = query.filter(models.TeacherProfile.subjects_taught.contains([subject]))
    if min_rate:
        query = query.filter(models.TeacherProfile.hourly_rate >= min_rate)
    if max_rate:
        query = query.filter(models.TeacherProfile.hourly_rate <= max_rate)
    if min_rating:
        query = query.filter(models.TeacherProfile.average_rating >= min_rating)
    if city:
        query = query.filter(models.TeacherProfile.city.ilike(f"%{city}%"))
    if format:
        query = query.filter(models.TeacherProfile.preferred_formats.contains([format]))
    if language:
        query = query.filter(models.TeacherProfile.languages.contains([language]))
    if verified_only:
        query = query.filter(models.TeacherProfile.is_verified == True)
    
    if experience_level:
        if experience_level == "beginner":
            query = query.filter(models.TeacherProfile.experience_years <= 2)
        elif experience_level == "intermediate":
            query = query.filter(
                and_(models.TeacherProfile.experience_years > 2, 
                     models.TeacherProfile.experience_years <= 5)
            )
        elif experience_level == "expert":
            query = query.filter(models.TeacherProfile.experience_years > 5)
    
    if sort_by == "rating":
        query = query.order_by(desc(models.TeacherProfile.average_rating))
    elif sort_by == "rate_low":
        query = query.order_by(models.TeacherProfile.hourly_rate)
    elif sort_by == "rate_high":
        query = query.order_by(desc(models.TeacherProfile.hourly_rate))
    elif sort_by == "experience":
        query = query.order_by(desc(models.TeacherProfile.experience_years))
    elif sort_by == "sessions":
        query = query.order_by(desc(models.TeacherProfile.total_sessions))
    
    offset = (page - 1) * per_page
    teachers = query.offset(offset).limit(per_page).all()
    
    return teachers

@app.get("/api/teachers/{teacher_id}", response_model=schemas.TeacherProfileResponse)
def get_teacher(teacher_id: str, db: Session = Depends(get_db)):
    teacher = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.id == teacher_id
    ).first()
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    return teacher

# ==================== Reviews Endpoints ====================

@app.get("/api/reviews/teacher/{teacher_id}", response_model=List[schemas.ReviewResponse])
def get_teacher_reviews(
    teacher_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * per_page
    reviews = db.query(models.Review).filter(
        models.Review.teacher_id == teacher_id
    ).order_by(desc(models.Review.created_at)).offset(offset).limit(per_page).all()
    
    result = []
    for review in reviews:
        result.append(schemas.ReviewResponse.model_validate(review))
    return result

# ==================== Health Check ====================

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Handler for Vercel
handler = app

