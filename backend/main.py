from fastapi import FastAPI, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, desc
from typing import List, Optional
from datetime import timedelta, datetime
import models
import schemas
import auth
from database import get_db, engine
from payment import PaymentGateway
from websocket import manager, websocket_endpoint
import os
import logging
import json
from uuid import uuid4
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fast-Classified API", version="2.0.0")

# CORS Configuration
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": new_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
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
    
    # Get unread notifications count
    unread_notifications = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).count()
    
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "profile": profile,
        "has_profile": profile is not None,
        "unread_notifications": unread_notifications
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
    
    for key, value in profile_update.model_dump(exclude_unset=True).items():
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
    
    for key, value in profile_update.model_dump(exclude_unset=True).items():
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
    
    # Add student info
    student_profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()
    
    response = schemas.RequestResponse.model_validate(new_request)
    if student_profile:
        response.student_name = student_profile.name
        response.student_grade = student_profile.grade_level
    
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
    ).order_by(models.Request.created_at.desc()).offset(offset).limit(per_page).all()
    
    result = []
    for req in requests:
        student_profile = db.query(models.StudentProfile).filter(
            models.StudentProfile.user_id == req.student_id
        ).first()
        
        req_response = schemas.RequestResponse.model_validate(req)
        if student_profile:
            req_response.student_name = student_profile.name
            req_response.student_grade = student_profile.grade_level
        result.append(req_response)
    
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
    formats: Optional[str] = None,
    language: Optional[str] = None,
    city: Optional[str] = None,
    experience_level: Optional[str] = None,
    sort_by: Optional[str] = "rating",
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(models.TeacherProfile)
    
    if subject:
        query = query.filter(models.TeacherProfile.subjects_taught.contains([subject]))
    
    if min_rate is not None:
        query = query.filter(models.TeacherProfile.hourly_rate >= min_rate)
    
    if max_rate is not None:
        query = query.filter(models.TeacherProfile.hourly_rate <= max_rate)
    
    if min_rating is not None:
        query = query.filter(models.TeacherProfile.average_rating >= min_rating)
    
    if formats:
        format_list = formats.split(",")
        for fmt in format_list:
            query = query.filter(models.TeacherProfile.preferred_formats.contains([fmt]))
    
    if language:
        query = query.filter(models.TeacherProfile.languages.contains([language]))
    
    if city:
        query = query.filter(models.TeacherProfile.city.ilike(f"%{city}%"))
    
    if experience_level:
        if experience_level == "beginner":
            query = query.filter(models.TeacherProfile.experience_years <= 2)
        elif experience_level == "intermediate":
            query = query.filter(models.TeacherProfile.experience_years.between(3, 5))
        elif experience_level == "expert":
            query = query.filter(models.TeacherProfile.experience_years > 5)
    
    # Sorting
    if sort_by == "rating":
        query = query.order_by(desc(models.TeacherProfile.average_rating))
    elif sort_by == "price_low":
        query = query.order_by(models.TeacherProfile.hourly_rate)
    elif sort_by == "price_high":
        query = query.order_by(desc(models.TeacherProfile.hourly_rate))
    elif sort_by == "reviews":
        query = query.order_by(desc(models.TeacherProfile.total_reviews))
    
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

# ==================== Session Booking Endpoints ====================

@app.post("/api/sessions/book", response_model=schemas.SessionResponse)
def book_session(
    session_data: schemas.SessionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Only students can book sessions")
    
    # Get student profile
    student_profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()
    
    if not student_profile:
        raise HTTPException(status_code=400, detail="Please create a profile first")
    
    # Get teacher profile
    teacher = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.id == session_data.teacher_id
    ).first()
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Calculate total amount
    total_amount = teacher.hourly_rate * session_data.duration
    
    # Create session
    new_session = models.Session(
        student_id=student_profile.id,
        teacher_id=teacher.id,
        subject=session_data.subject,
        topic=session_data.topic,
        scheduled_date=session_data.scheduled_date,
        scheduled_time=session_data.scheduled_time,
        duration=session_data.duration,
        hourly_rate=teacher.hourly_rate,
        total_amount=total_amount,
        is_recurring=session_data.is_recurring,
        recurring_frequency=session_data.recurring_frequency,
        notes=session_data.notes
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    # Create notification for teacher
    notification = models.Notification(
        user_id=teacher.user_id,
        type=models.NotificationType.SESSION_BOOKED,
        title="New Session Booking",
        message=f"{student_profile.name} has booked a {session_data.subject} session with you.",
        data={"session_id": str(new_session.id)}
    )
    db.add(notification)
    db.commit()
    
    response = schemas.SessionResponse.model_validate(new_session)
    response.teacher_name = teacher.name
    response.student_name = student_profile.name
    
    return response

@app.get("/api/sessions", response_model=List[schemas.SessionResponse])
def get_sessions(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Get user's profile
    if current_user.role == models.UserRole.STUDENT:
        profile = db.query(models.StudentProfile).filter(
            models.StudentProfile.user_id == current_user.id
        ).first()
        if not profile:
            return []
        query = db.query(models.Session).filter(models.Session.student_id == profile.id)
    else:
        profile = db.query(models.TeacherProfile).filter(
            models.TeacherProfile.user_id == current_user.id
        ).first()
        if not profile:
            return []
        query = db.query(models.Session).filter(models.Session.teacher_id == profile.id)
    
    if status:
        query = query.filter(models.Session.status == status)
    
    offset = (page - 1) * per_page
    sessions = query.order_by(desc(models.Session.scheduled_date)).offset(offset).limit(per_page).all()
    
    result = []
    for session in sessions:
        response = schemas.SessionResponse.model_validate(session)
        response.teacher_name = session.teacher.name if session.teacher else None
        response.student_name = session.student.name if session.student else None
        result.append(response)
    
    return result

@app.patch("/api/sessions/{session_id}", response_model=schemas.SessionResponse)
def update_session(
    session_id: str,
    session_update: schemas.SessionUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(models.Session).filter(models.Session.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Verify user has access to this session
    if current_user.role == models.UserRole.TEACHER:
        profile = db.query(models.TeacherProfile).filter(
            models.TeacherProfile.user_id == current_user.id
        ).first()
        if not profile or session.teacher_id != profile.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    for key, value in session_update.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(session, key, value)
    
    db.commit()
    db.refresh(session)
    
    response = schemas.SessionResponse.model_validate(session)
    response.teacher_name = session.teacher.name if session.teacher else None
    response.student_name = session.student.name if session.student else None
    
    return response

# ==================== Review Endpoints ====================

@app.post("/api/reviews", response_model=schemas.ReviewResponse)
def create_review(
    review_data: schemas.ReviewCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Only students can leave reviews")
    
    # Get student profile
    student_profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()
    
    if not student_profile:
        raise HTTPException(status_code=400, detail="Please create a profile first")
    
    # Get session
    session = db.query(models.Session).filter(
        models.Session.id == review_data.session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.student_id != student_profile.id:
        raise HTTPException(status_code=403, detail="You can only review your own sessions")
    
    if session.status != models.SessionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="You can only review completed sessions")
    
    # Check if review already exists
    existing_review = db.query(models.Review).filter(
        models.Review.session_id == review_data.session_id
    ).first()
    
    if existing_review:
        raise HTTPException(status_code=400, detail="Review already exists for this session")
    
    # Create review
    new_review = models.Review(
        session_id=session.id,
        student_id=student_profile.id,
        teacher_id=session.teacher_id,
        rating=review_data.rating,
        review_text=review_data.review_text
    )
    db.add(new_review)
    
    # Update teacher's average rating
    teacher = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.id == session.teacher_id
    ).first()
    
    if teacher:
        all_reviews = db.query(models.Review).filter(
            models.Review.teacher_id == teacher.id
        ).all()
        total_rating = sum(r.rating for r in all_reviews) + review_data.rating
        teacher.total_reviews = len(all_reviews) + 1
        teacher.average_rating = total_rating / teacher.total_reviews
        
        # Create notification for teacher
        notification = models.Notification(
            user_id=teacher.user_id,
            type=models.NotificationType.REVIEW_POSTED,
            title="New Review",
            message=f"{student_profile.name} left a {review_data.rating}-star review.",
            data={"review_id": str(new_review.id)}
        )
        db.add(notification)
    
    db.commit()
    db.refresh(new_review)
    
    response = schemas.ReviewResponse.model_validate(new_review)
    response.student_name = student_profile.name
    
    return response

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
        response = schemas.ReviewResponse.model_validate(review)
        response.student_name = review.student.name if review.student else None
        result.append(response)
    
    return result

@app.post("/api/reviews/{review_id}/response")
def respond_to_review(
    review_id: str,
    response_data: schemas.ReviewResponseCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can respond to reviews")
    
    teacher_profile = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.user_id == current_user.id
    ).first()
    
    if not teacher_profile:
        raise HTTPException(status_code=400, detail="Profile not found")
    
    review = db.query(models.Review).filter(
        models.Review.id == review_id,
        models.Review.teacher_id == teacher_profile.id
    ).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review.teacher_response = response_data.response_text
    review.teacher_response_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Response added successfully"}

@app.post("/api/reviews/{review_id}/helpful")
def mark_review_helpful(
    review_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review.helpful_votes += 1
    db.commit()
    
    return {"helpful_votes": review.helpful_votes}

# ==================== Messaging Endpoints ====================

@app.post("/api/messages", response_model=schemas.MessageResponse)
async def send_message(
    message_data: schemas.MessageCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Check if conversation exists
    conversation = db.query(models.Conversation).filter(
        or_(
            and_(
                models.Conversation.participant_1_id == current_user.id,
                models.Conversation.participant_2_id == message_data.receiver_id
            ),
            and_(
                models.Conversation.participant_1_id == message_data.receiver_id,
                models.Conversation.participant_2_id == current_user.id
            )
        )
    ).first()
    
    if not conversation:
        # Create new conversation
        conversation = models.Conversation(
            participant_1_id=current_user.id,
            participant_2_id=message_data.receiver_id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Create message
    new_message = models.Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        receiver_id=message_data.receiver_id,
        content=message_data.content,
        attachment_url=message_data.attachment_url,
        attachment_type=message_data.attachment_type
    )
    db.add(new_message)
    
    # Update conversation's last message time
    conversation.last_message_at = datetime.utcnow()
    
    # Create notification
    notification = models.Notification(
        user_id=message_data.receiver_id,
        type=models.NotificationType.MESSAGE,
        title="New Message",
        message=f"You have a new message",
        data={"conversation_id": str(conversation.id), "sender_id": str(current_user.id)}
    )
    db.add(notification)
    
    db.commit()
    db.refresh(new_message)
    
    # Send real-time notification via WebSocket
    await manager.send_new_message(
        {
            "id": str(new_message.id),
            "conversation_id": str(conversation.id),
            "sender_id": str(current_user.id),
            "content": new_message.content,
            "created_at": new_message.created_at.isoformat()
        },
        str(message_data.receiver_id)
    )
    
    response = schemas.MessageResponse.model_validate(new_message)
    return response

@app.get("/api/conversations", response_model=List[schemas.ConversationResponse])
def get_conversations(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    conversations = db.query(models.Conversation).filter(
        or_(
            models.Conversation.participant_1_id == current_user.id,
            models.Conversation.participant_2_id == current_user.id
        )
    ).order_by(desc(models.Conversation.last_message_at)).all()
    
    result = []
    for conv in conversations:
        # Get other participant
        other_id = conv.participant_2_id if conv.participant_1_id == current_user.id else conv.participant_1_id
        other_user = db.query(models.User).filter(models.User.id == other_id).first()
        
        # Get profile name
        other_name = None
        other_avatar = None
        if other_user:
            if other_user.role == models.UserRole.STUDENT:
                profile = db.query(models.StudentProfile).filter(
                    models.StudentProfile.user_id == other_id
                ).first()
            else:
                profile = db.query(models.TeacherProfile).filter(
                    models.TeacherProfile.user_id == other_id
                ).first()
            if profile:
                other_name = profile.name
                other_avatar = profile.avatar_url
        
        # Get last message
        last_message = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id
        ).order_by(desc(models.Message.created_at)).first()
        
        # Get unread count
        unread_count = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id,
            models.Message.receiver_id == current_user.id,
            models.Message.is_read == False
        ).count()
        
        response = schemas.ConversationResponse.model_validate(conv)
        response.other_participant_name = other_name
        response.other_participant_avatar = other_avatar
        response.last_message = last_message.content if last_message else None
        response.unread_count = unread_count
        result.append(response)
    
    return result

@app.get("/api/conversations/{conversation_id}/messages", response_model=List[schemas.MessageResponse])
def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Verify user is part of conversation
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        or_(
            models.Conversation.participant_1_id == current_user.id,
            models.Conversation.participant_2_id == current_user.id
        )
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Mark messages as read
    db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id,
        models.Message.receiver_id == current_user.id,
        models.Message.is_read == False
    ).update({"is_read": True})
    db.commit()
    
    offset = (page - 1) * per_page
    messages = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(desc(models.Message.created_at)).offset(offset).limit(per_page).all()
    
    return [schemas.MessageResponse.model_validate(m) for m in messages]

# ==================== Payment Endpoints ====================

@app.post("/api/payment/initiate", response_model=schemas.PaymentInitiateResponse)
def initiate_payment(
    payment_data: schemas.PaymentInitiateRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Validate session
    session = db.query(models.Session).filter(
        models.Session.id == payment_data.session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.payment_status == models.PaymentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Session already paid")
    
    # Initialize payment gateway
    gateway = PaymentGateway(payment_data.provider)
    
    # Initiate payment
    if payment_data.provider == "jazzcash":
        result = gateway.initiate_payment_jazzcash(
            amount=payment_data.amount,
            customer_email=payment_data.customer_email,
            customer_mobile=payment_data.customer_mobile,
            description=payment_data.description
        )
    else:
        result = gateway.initiate_payment_easypaisa(
            amount=payment_data.amount,
            customer_email=payment_data.customer_email,
            customer_mobile=payment_data.customer_mobile,
            description=payment_data.description
        )
    
    # Create transaction record
    transaction = models.Transaction(
        session_id=session.id,
        user_id=current_user.id,
        amount=payment_data.amount,
        transaction_type=models.TransactionType.PAYMENT,
        provider=payment_data.provider,
        provider_transaction_id=result.get("transaction_id"),
        description=payment_data.description
    )
    db.add(transaction)
    db.commit()
    
    return schemas.PaymentInitiateResponse(
        transaction_id=result.get("transaction_id", ""),
        payment_url=result.get("payment_url"),
        status=result.get("status", "failed")
    )

@app.post("/api/payment/{provider}/callback")
async def payment_callback(
    provider: str,
    request: Request,
    db: Session = Depends(get_db)
):
    # Get transaction data
    if provider == "jazzcash":
        transaction_data = dict(await request.form())
    else:
        transaction_data = await request.json()
    
    # Create gateway instance
    gateway = PaymentGateway(provider)
    
    # Verify payment
    is_valid = gateway.verify_payment(transaction_data)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    
    # Get transaction ID
    transaction_id = transaction_data.get("pp_TxnRefNo") if provider == "jazzcash" else transaction_data.get("orderRefNum")
    
    # Find transaction
    transaction = db.query(models.Transaction).filter(
        models.Transaction.provider_transaction_id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Get response code
    response_code = transaction_data.get("pp_ResponseCode") if provider == "jazzcash" else transaction_data.get("responseCode")
    
    # Update transaction status
    payment_status = gateway.get_payment_status(response_code)
    
    if payment_status == "completed":
        transaction.status = models.PaymentStatus.COMPLETED
        transaction.payment_reference = transaction_data.get("pp_TxnRefNo") if provider == "jazzcash" else transaction_data.get("transactionId")
        
        # Update session
        if transaction.session_id:
            session = db.query(models.Session).filter(
                models.Session.id == transaction.session_id
            ).first()
            if session:
                session.payment_status = models.PaymentStatus.COMPLETED
                session.status = models.SessionStatus.CONFIRMED
                
                # Notify teacher
                notification = models.Notification(
                    user_id=session.teacher.user_id,
                    type=models.NotificationType.PAYMENT_RECEIVED,
                    title="Payment Received",
                    message=f"Payment of PKR {transaction.amount} received for session.",
                    data={"session_id": str(session.id)}
                )
                db.add(notification)
    else:
        transaction.status = models.PaymentStatus.FAILED
    
    db.commit()
    
    return {"status": transaction.status.value}

# ==================== Wallet Endpoints ====================

@app.get("/api/wallet", response_model=schemas.WalletResponse)
def get_wallet(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        # Create wallet if doesn't exist
        wallet = models.Wallet(user_id=current_user.id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    
    return wallet

@app.get("/api/wallet/transactions", response_model=List[schemas.TransactionResponse])
def get_wallet_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        return []
    
    offset = (page - 1) * per_page
    transactions = db.query(models.Transaction).filter(
        models.Transaction.wallet_id == wallet.id
    ).order_by(desc(models.Transaction.created_at)).offset(offset).limit(per_page).all()
    
    return [schemas.TransactionResponse.model_validate(t) for t in transactions]

@app.post("/api/wallet/deposit")
def deposit_to_wallet(
    deposit_data: schemas.WalletDepositRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        wallet = models.Wallet(user_id=current_user.id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    
    # Initialize payment gateway
    gateway = PaymentGateway(deposit_data.provider)
    
    # Initiate deposit
    if deposit_data.provider == "jazzcash":
        result = gateway.initiate_payment_jazzcash(
            amount=deposit_data.amount,
            customer_email=current_user.email,
            customer_mobile=deposit_data.customer_mobile,
            description="Wallet Deposit"
        )
    else:
        result = gateway.initiate_payment_easypaisa(
            amount=deposit_data.amount,
            customer_email=current_user.email,
            customer_mobile=deposit_data.customer_mobile,
            description="Wallet Deposit"
        )
    
    # Create transaction record
    transaction = models.Transaction(
        wallet_id=wallet.id,
        user_id=current_user.id,
        amount=deposit_data.amount,
        transaction_type=models.TransactionType.DEPOSIT,
        provider=deposit_data.provider,
        provider_transaction_id=result.get("transaction_id"),
        description="Wallet Deposit"
    )
    db.add(transaction)
    db.commit()
    
    return {
        "transaction_id": result.get("transaction_id"),
        "payment_url": result.get("payment_url"),
        "status": result.get("status")
    }

@app.post("/api/wallet/withdraw")
def withdraw_from_wallet(
    withdraw_data: schemas.WalletWithdrawRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    if wallet.balance < withdraw_data.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Verify bank account
    bank_account = db.query(models.BankAccount).filter(
        models.BankAccount.id == withdraw_data.bank_account_id,
        models.BankAccount.wallet_id == wallet.id
    ).first()
    
    if not bank_account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    
    # Create withdrawal transaction
    transaction = models.Transaction(
        wallet_id=wallet.id,
        user_id=current_user.id,
        amount=withdraw_data.amount,
        transaction_type=models.TransactionType.WITHDRAWAL,
        description=f"Withdrawal to {bank_account.bank_name} - {bank_account.account_number[-4:]}"
    )
    db.add(transaction)
    
    # Deduct from wallet
    wallet.balance -= withdraw_data.amount
    
    db.commit()
    
    return {"message": "Withdrawal request submitted", "transaction_id": str(transaction.id)}

# ==================== Bank Account Endpoints ====================

@app.post("/api/wallet/bank-accounts", response_model=schemas.BankAccountResponse)
def add_bank_account(
    account_data: schemas.BankAccountCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        wallet = models.Wallet(user_id=current_user.id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    
    bank_account = models.BankAccount(
        wallet_id=wallet.id,
        **account_data.model_dump()
    )
    db.add(bank_account)
    db.commit()
    db.refresh(bank_account)
    
    return bank_account

@app.get("/api/wallet/bank-accounts", response_model=List[schemas.BankAccountResponse])
def get_bank_accounts(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    wallet = db.query(models.Wallet).filter(
        models.Wallet.user_id == current_user.id
    ).first()
    
    if not wallet:
        return []
    
    return db.query(models.BankAccount).filter(
        models.BankAccount.wallet_id == wallet.id
    ).all()

# ==================== Notification Endpoints ====================

@app.get("/api/notifications", response_model=List[schemas.NotificationResponse])
def get_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
    
    offset = (page - 1) * per_page
    notifications = query.order_by(desc(models.Notification.created_at)).offset(offset).limit(per_page).all()
    
    return [schemas.NotificationResponse.model_validate(n) for n in notifications]

@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    db.commit()
    
    return {"message": "Notification marked as read"}

@app.post("/api/notifications/read-all")
def mark_all_notifications_read(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    
    return {"message": "All notifications marked as read"}

# ==================== Admin Endpoints ====================

@app.get("/api/admin/stats", response_model=schemas.AdminStatsResponse)
def get_admin_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    total_users = db.query(models.User).count()
    total_students = db.query(models.User).filter(models.User.role == models.UserRole.STUDENT).count()
    total_teachers = db.query(models.User).filter(models.User.role == models.UserRole.TEACHER).count()
    total_sessions = db.query(models.Session).count()
    
    total_revenue = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.status == models.PaymentStatus.COMPLETED,
        models.Transaction.transaction_type == models.TransactionType.PAYMENT
    ).scalar() or 0.0
    
    pending_verifications = db.query(models.VerificationDocument).filter(
        models.VerificationDocument.status == models.VerificationStatus.PENDING
    ).count()
    
    active_sessions = db.query(models.Session).filter(
        models.Session.status.in_([models.SessionStatus.PENDING, models.SessionStatus.CONFIRMED])
    ).count()
    
    return schemas.AdminStatsResponse(
        total_users=total_users,
        total_students=total_students,
        total_teachers=total_teachers,
        total_sessions=total_sessions,
        total_revenue=total_revenue,
        pending_verifications=pending_verifications,
        active_sessions=active_sessions
    )

@app.get("/api/admin/users", response_model=List[schemas.AdminUserResponse])
def get_admin_users(
    role: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(models.User)
    
    if role:
        query = query.filter(models.User.role == role)
    
    offset = (page - 1) * per_page
    users = query.order_by(desc(models.User.created_at)).offset(offset).limit(per_page).all()
    
    result = []
    for user in users:
        response = schemas.AdminUserResponse(
            id=user.id,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at
        )
        
        # Get profile name
        if user.role == models.UserRole.STUDENT:
            profile = db.query(models.StudentProfile).filter(
                models.StudentProfile.user_id == user.id
            ).first()
        else:
            profile = db.query(models.TeacherProfile).filter(
                models.TeacherProfile.user_id == user.id
            ).first()
        
        if profile:
            response.profile_name = profile.name
        
        result.append(response)
    
    return result

@app.get("/api/admin/verifications", response_model=List[schemas.VerificationDocumentResponse])
def get_pending_verifications(
    status: Optional[str] = "pending",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(models.VerificationDocument)
    
    if status:
        query = query.filter(models.VerificationDocument.status == status)
    
    offset = (page - 1) * per_page
    documents = query.order_by(desc(models.VerificationDocument.created_at)).offset(offset).limit(per_page).all()
    
    return [schemas.VerificationDocumentResponse.model_validate(d) for d in documents]

@app.post("/api/admin/verifications/{document_id}/review")
def review_verification(
    document_id: str,
    review_data: schemas.VerificationReviewRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    document = db.query(models.VerificationDocument).filter(
        models.VerificationDocument.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    document.status = models.VerificationStatus(review_data.status)
    document.admin_notes = review_data.admin_notes
    
    if review_data.status == "verified":
        document.verified_at = datetime.utcnow()
        
        # Update teacher's verification status
        teacher = db.query(models.TeacherProfile).filter(
            models.TeacherProfile.id == document.teacher_id
        ).first()
        
        if teacher:
            # Check if all documents are verified
            all_verified = db.query(models.VerificationDocument).filter(
                models.VerificationDocument.teacher_id == teacher.id,
                models.VerificationDocument.status != models.VerificationStatus.VERIFIED
            ).count() == 0
            
            if all_verified:
                teacher.is_verified = True
                teacher.verification_status = models.VerificationStatus.VERIFIED
    
    db.commit()
    
    return {"message": f"Document {review_data.status}"}

# ==================== Teacher Verification Endpoints ====================

@app.post("/api/verification/documents", response_model=schemas.VerificationDocumentResponse)
def upload_verification_document(
    document_data: schemas.VerificationDocumentCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can upload verification documents")
    
    teacher_profile = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.user_id == current_user.id
    ).first()
    
    if not teacher_profile:
        raise HTTPException(status_code=400, detail="Please create a profile first")
    
    document = models.VerificationDocument(
        teacher_id=teacher_profile.id,
        **document_data.model_dump()
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return document

@app.get("/api/verification/documents", response_model=List[schemas.VerificationDocumentResponse])
def get_my_verification_documents(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Only teachers can view verification documents")
    
    teacher_profile = db.query(models.TeacherProfile).filter(
        models.TeacherProfile.user_id == current_user.id
    ).first()
    
    if not teacher_profile:
        return []
    
    return db.query(models.VerificationDocument).filter(
        models.VerificationDocument.teacher_id == teacher_profile.id
    ).all()

# ==================== WebSocket Endpoint ====================

@app.websocket("/ws/{user_id}")
async def websocket_route(websocket: WebSocket, user_id: str):
    await websocket_endpoint(websocket, user_id)

# ==================== Root Endpoint ====================

@app.get("/")
def root():
    return {"message": "Fast-Classified API is running", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
