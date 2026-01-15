from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """사용자 모델"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    department = Column(String(100))
    role = Column(String(20), default="user")  # admin, manager, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Patient(Base):
    """환자 데이터 모델 (익명화된 데이터)"""
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_hash = Column(String(64), unique=True, index=True)  # 등록번호 해시
    masked_name = Column(String(50))  # 마스킹된 이름
    department = Column(String(50))
    doctor_name = Column(String(50))
    primary_diagnosis = Column(String(200))
    primary_diagnosis_code = Column(String(20), index=True)
    admission_date = Column(DateTime)
    discharge_date = Column(DateTime)
    gender = Column(String(10))
    age = Column(Integer)
    discharge_result = Column(String(50))
    kdrg_code = Column(String(10), index=True)
    aadrg_code = Column(String(10), index=True)
    length_of_stay = Column(Integer)
    claim_amount = Column(Float, default=0)
    
    # Encrypted fields (stored as encrypted string)
    encrypted_patient_id = Column(Text)  # 암호화된 등록번호
    encrypted_patient_name = Column(Text)  # 암호화된 환자명
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    validations = relationship("ValidationResult", back_populates="patient")
    optimizations = relationship("OptimizationResult", back_populates="patient")


class KDRGCode(Base):
    """KDRG 코드 마스터 테이블"""
    __tablename__ = "kdrg_codes"
    
    id = Column(Integer, primary_key=True, index=True)
    aadrg_code = Column(String(10), index=True)
    kdrg_code = Column(String(10), index=True)
    disease_group = Column(String(200))
    mdc = Column(String(10))
    cc = Column(String(10))
    version = Column(String(10))  # 3.5, 4.6
    relative_weight = Column(Float, default=1.0)
    base_payment = Column(Float, default=0)
    is_7drg = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ValidationResult(Base):
    """KDRG 검증 결과"""
    __tablename__ = "validation_results"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    validation_type = Column(String(50))  # kdrg, disease_code, 7drg
    result = Column(String(20))  # 정상, 오류, 경고
    detail = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    patient = relationship("Patient", back_populates="validations")


class OptimizationResult(Base):
    """DRG 최적화 추천 결과"""
    __tablename__ = "optimization_results"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    current_kdrg = Column(String(10))
    current_aadrg = Column(String(10))
    recommended_kdrg = Column(String(10))
    recommended_aadrg = Column(String(10))
    current_payment = Column(Float, default=0)
    potential_payment = Column(Float, default=0)
    payment_difference = Column(Float, default=0)
    recommendation_reason = Column(Text)
    confidence_score = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    patient = relationship("Patient", back_populates="optimizations")


class AuditLog(Base):
    """감사 로그"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100))
    resource = Column(String(100))
    resource_id = Column(Integer)
    details = Column(Text)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class RevenueStatistics(Base):
    """수익 통계"""
    __tablename__ = "revenue_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(20))  # YYYY-MM
    department = Column(String(50))
    drg_group = Column(String(20))
    patient_count = Column(Integer, default=0)
    total_claim = Column(Float, default=0)
    avg_claim = Column(Float, default=0)
    total_loss = Column(Float, default=0)  # 손실 금액
    potential_gain = Column(Float, default=0)  # 최적화 시 예상 추가 수익
    created_at = Column(DateTime, default=datetime.utcnow)
