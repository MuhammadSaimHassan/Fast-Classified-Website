from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, ForeignKey, ARRAY, JSON, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime
import enum


class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class RequestStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class TransactionType(str, enum.Enum):
    PAYMENT = "payment"
    WITHDRAWAL = "withdrawal"
    REFUND = "refund"
    DEPOSIT = "deposit"


class NotificationType(str, enum.Enum):
    MESSAGE = "message"
    SESSION_BOOKED = "session_booked"
    PAYMENT_RECEIVED = "payment_received"
    REVIEW_POSTED = "review_posted"
    SESSION_REMINDER = "session_reminder"
    TEACHER_ACCEPTED = "teacher_accepted"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student_profile = relationship("StudentProfile", back_populates="user", uselist=False)
    teacher_profile = relationship("TeacherProfile", back_populates="user", uselist=False)
    requests = relationship("Request", back_populates="student")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
    notifications = relationship("Notification", back_populates="user")
    wallet = relationship("Wallet", back_populates="user", uselist=False)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    name = Column(String, nullable=False)
    bio = Column(String)
    gpa = Column(JSON)  # {"Math": 3.8, "Physics": 3.5}
    grade_level = Column(String)
    institution = Column(String)
    avatar_url = Column(String)
    preferred_formats = Column(ARRAY(String))
    phone_number = Column(String)
    city = Column(String)
    
    user = relationship("User", back_populates="student_profile")
    sessions_as_student = relationship("Session", back_populates="student")
    reviews_given = relationship("Review", back_populates="student")


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    name = Column(String, nullable=False)
    bio = Column(String)
    hourly_rate = Column(Float, nullable=False)
    subjects_taught = Column(JSON)  # ["Math", "Physics", "Chemistry"]
    experience_years = Column(Integer)
    certifications = Column(JSON)
    avatar_url = Column(String)
    preferred_formats = Column(ARRAY(String))
    average_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    total_sessions = Column(Integer, default=0)
    phone_number = Column(String)
    city = Column(String)
    languages = Column(ARRAY(String))  # ["English", "Urdu"]
    availability = Column(JSON)  # {"monday": ["09:00", "10:00", ...], ...}
    is_verified = Column(Boolean, default=False)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    
    user = relationship("User", back_populates="teacher_profile")
    sessions_as_teacher = relationship("Session", back_populates="teacher")
    reviews_received = relationship("Review", back_populates="teacher")
    verification_documents = relationship("VerificationDocument", back_populates="teacher")


class Request(Base):
    __tablename__ = "requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    description = Column(String)
    preferred_format = Column(String)
    urgency_level = Column(String)
    hourly_rate = Column(Float)
    duration = Column(String)
    status = Column(Enum(RequestStatus), default=RequestStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("User", back_populates="requests")


class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teacher_profiles.id"), nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String)
    scheduled_date = Column(DateTime, nullable=False)
    scheduled_time = Column(String, nullable=False)
    duration = Column(Float, nullable=False)  # in hours
    hourly_rate = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    is_recurring = Column(Boolean, default=False)
    recurring_frequency = Column(String)  # weekly, bi-weekly, monthly
    meeting_link = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship("StudentProfile", back_populates="sessions_as_student")
    teacher = relationship("TeacherProfile", back_populates="sessions_as_teacher")
    transaction = relationship("Transaction", back_populates="session", uselist=False)
    review = relationship("Review", back_populates="session", uselist=False)


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teacher_profiles.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    review_text = Column(Text)
    is_verified_session = Column(Boolean, default=True)
    helpful_votes = Column(Integer, default=0)
    teacher_response = Column(Text)
    teacher_response_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session = relationship("Session", back_populates="review")
    student = relationship("StudentProfile", back_populates="reviews_given")
    teacher = relationship("TeacherProfile", back_populates="reviews_received")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    attachment_url = Column(String)
    attachment_type = Column(String)  # image, document, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_1_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    participant_2_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    participant_1 = relationship("User", foreign_keys=[participant_1_id])
    participant_2 = relationship("User", foreign_keys=[participant_2_id])


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    provider = Column(String)  # jazzcash, easypaisa
    provider_transaction_id = Column(String)
    payment_reference = Column(String)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session = relationship("Session", back_populates="transaction")
    wallet = relationship("Wallet", back_populates="transactions")


class Wallet(Base):
    __tablename__ = "wallets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0.0)
    currency = Column(String, default="PKR")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")
    bank_accounts = relationship("BankAccount", back_populates="wallet")


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False)
    account_title = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    bank_name = Column(String, nullable=False)
    iban = Column(String)
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    wallet = relationship("Wallet", back_populates="bank_accounts")


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON)  # Additional data like session_id, sender_id, etc.
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notifications")


class VerificationDocument(Base):
    __tablename__ = "verification_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teacher_profiles.id"), nullable=False)
    document_type = Column(String, nullable=False)  # id_card, degree, certificate, etc.
    document_url = Column(String, nullable=False)
    status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    admin_notes = Column(Text)
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    teacher = relationship("TeacherProfile", back_populates="verification_documents")
