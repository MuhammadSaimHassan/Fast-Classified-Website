from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# Enums for Pydantic
class SessionStatusEnum(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class TransactionTypeEnum(str, Enum):
    PAYMENT = "payment"
    WITHDRAWAL = "withdrawal"
    REFUND = "refund"
    DEPOSIT = "deposit"


class NotificationTypeEnum(str, Enum):
    MESSAGE = "message"
    SESSION_BOOKED = "session_booked"
    PAYMENT_RECEIVED = "payment_received"
    REVIEW_POSTED = "review_posted"
    SESSION_REMINDER = "session_reminder"
    TEACHER_ACCEPTED = "teacher_accepted"


# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Profile Schemas
class StudentProfileCreate(BaseModel):
    name: str
    bio: Optional[str] = None
    gpa: Optional[Dict[str, float]] = None
    grade_level: Optional[str] = None
    institution: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_formats: Optional[List[str]] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None


class StudentProfileResponse(StudentProfileCreate):
    id: UUID
    user_id: UUID
    
    class Config:
        from_attributes = True


class TeacherProfileCreate(BaseModel):
    name: str
    bio: Optional[str] = None
    hourly_rate: float
    subjects_taught: Optional[List[str]] = None
    experience_years: Optional[int] = None
    certifications: Optional[Dict] = None
    avatar_url: Optional[str] = None
    preferred_formats: Optional[List[str]] = None
    phone_number: Optional[str] = None
    city: Optional[str] = None
    languages: Optional[List[str]] = None
    availability: Optional[Dict[str, List[str]]] = None


class TeacherProfileResponse(TeacherProfileCreate):
    id: UUID
    user_id: UUID
    average_rating: float
    total_reviews: Optional[int] = 0
    total_sessions: Optional[int] = 0
    is_verified: Optional[bool] = False
    
    class Config:
        from_attributes = True


# Request Schemas
class RequestCreate(BaseModel):
    subject: str
    topic: str
    description: Optional[str] = None
    preferred_format: Optional[str] = None
    urgency_level: Optional[str] = None
    hourly_rate: Optional[float] = None
    duration: Optional[str] = None


class RequestResponse(RequestCreate):
    id: UUID
    student_id: UUID
    status: str
    created_at: datetime
    student_name: Optional[str] = None
    student_grade: Optional[str] = None
    
    class Config:
        from_attributes = True


# Search Schemas
class TeacherSearchParams(BaseModel):
    subject: Optional[str] = None
    min_rate: Optional[float] = None
    max_rate: Optional[float] = None
    min_rating: Optional[float] = None
    formats: Optional[List[str]] = None
    availability: Optional[str] = None
    experience_level: Optional[str] = None
    language: Optional[str] = None
    city: Optional[str] = None
    sort_by: Optional[str] = "rating"  # rating, price_low, price_high, reviews
    page: int = 1
    per_page: int = 10


# Session Schemas
class SessionCreate(BaseModel):
    teacher_id: UUID
    subject: str
    topic: Optional[str] = None
    scheduled_date: datetime
    scheduled_time: str
    duration: float
    is_recurring: bool = False
    recurring_frequency: Optional[str] = None
    notes: Optional[str] = None


class SessionResponse(BaseModel):
    id: UUID
    student_id: UUID
    teacher_id: UUID
    subject: str
    topic: Optional[str]
    scheduled_date: datetime
    scheduled_time: str
    duration: float
    hourly_rate: float
    total_amount: float
    status: str
    payment_status: str
    is_recurring: bool
    recurring_frequency: Optional[str]
    meeting_link: Optional[str]
    notes: Optional[str]
    created_at: datetime
    teacher_name: Optional[str] = None
    student_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class SessionUpdate(BaseModel):
    status: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


# Review Schemas
class ReviewCreate(BaseModel):
    session_id: UUID
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = None


class ReviewResponse(BaseModel):
    id: UUID
    session_id: UUID
    student_id: UUID
    teacher_id: UUID
    rating: int
    review_text: Optional[str]
    is_verified_session: bool
    helpful_votes: int
    teacher_response: Optional[str]
    teacher_response_at: Optional[datetime]
    created_at: datetime
    student_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class ReviewResponseCreate(BaseModel):
    response_text: str


# Message Schemas
class MessageCreate(BaseModel):
    receiver_id: UUID
    content: str
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    receiver_id: UUID
    content: str
    is_read: bool
    attachment_url: Optional[str]
    attachment_type: Optional[str]
    created_at: datetime
    sender_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: UUID
    participant_1_id: UUID
    participant_2_id: UUID
    last_message_at: datetime
    created_at: datetime
    other_participant_name: Optional[str] = None
    other_participant_avatar: Optional[str] = None
    last_message: Optional[str] = None
    unread_count: int = 0
    
    class Config:
        from_attributes = True


# Payment Schemas
class PaymentInitiateRequest(BaseModel):
    amount: float
    customer_email: str
    customer_mobile: str
    description: str
    session_id: UUID
    provider: str  # "jazzcash" or "easypaisa"


class PaymentInitiateResponse(BaseModel):
    transaction_id: str
    payment_url: Optional[str]
    status: str


class PaymentCallbackData(BaseModel):
    transaction_id: str
    status: str
    provider_reference: Optional[str]


# Transaction Schemas
class TransactionResponse(BaseModel):
    id: UUID
    session_id: Optional[UUID]
    amount: float
    transaction_type: str
    status: str
    provider: Optional[str]
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Wallet Schemas
class WalletResponse(BaseModel):
    id: UUID
    balance: float
    currency: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class WalletDepositRequest(BaseModel):
    amount: float
    provider: str
    customer_mobile: str


class WalletWithdrawRequest(BaseModel):
    amount: float
    bank_account_id: UUID


class BankAccountCreate(BaseModel):
    account_title: str
    account_number: str
    bank_name: str
    iban: Optional[str] = None
    is_primary: bool = False


class BankAccountResponse(BankAccountCreate):
    id: UUID
    wallet_id: UUID
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Notification Schemas
class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    message: str
    data: Optional[Dict[str, Any]]
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Admin Schemas
class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    profile_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class AdminStatsResponse(BaseModel):
    total_users: int
    total_students: int
    total_teachers: int
    total_sessions: int
    total_revenue: float
    pending_verifications: int
    active_sessions: int


class VerificationDocumentCreate(BaseModel):
    document_type: str
    document_url: str


class VerificationDocumentResponse(VerificationDocumentCreate):
    id: UUID
    teacher_id: UUID
    status: str
    admin_notes: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class VerificationReviewRequest(BaseModel):
    status: str  # verified, rejected
    admin_notes: Optional[str] = None
