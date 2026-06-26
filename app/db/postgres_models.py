import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, Text, ForeignKey, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    industry = Column(String, nullable=False)  # "healthcare" | "banking" | "insurance"
    status = Column(String, nullable=False, default="pending")  # "pending" | "validated" | "repaired" | "certified"
    uploaded_by = Column(String, nullable=False, default="system")
    upload_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    raw_content = Column(Text, nullable=True)

    # Relationships
    jobs = relationship("ValidationJob", back_populates="document", cascade="all, delete-orphan")
    audit_reports = relationship("AuditReport", back_populates="document", cascade="all, delete-orphan")

class ValidationJob(Base):
    __tablename__ = "validation_jobs"
    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    total_errors = Column(Integer, nullable=False, default=0)
    compliance_score = Column(Float, nullable=False, default=100.0)

    # Relationships
    document = relationship("Document", back_populates="jobs")
    results = relationship("ValidationResult", back_populates="job", cascade="all, delete-orphan")
    audit_reports = relationship("AuditReport", back_populates="job", cascade="all, delete-orphan")

class ValidationResult(Base):
    __tablename__ = "validation_results"
    result_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("validation_jobs.job_id", ondelete="CASCADE"), nullable=False)
    error_type = Column(String, nullable=False)  # "structural" | "semantic" | "relational"
    field = Column(String, nullable=False)
    value = Column(String, nullable=True)
    rule_violated = Column(String, nullable=False)
    llm_explanation = Column(Text, nullable=True)
    regulation_cited = Column(String, nullable=True)
    severity = Column(String, nullable=False)  # "critical" | "warning" | "info"
    triage_category = Column(String, nullable=False)  # "safe_fix" | "risky_fix" | "manual"
    status = Column(String, nullable=False, default="pending")  # "pending" | "approved" | "rejected" | "auto_fixed"

    # Relationships
    job = relationship("ValidationJob", back_populates="results")
    repair_history = relationship("RepairHistory", back_populates="result", cascade="all, delete-orphan")

class RepairHistory(Base):
    __tablename__ = "repair_history"
    repair_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(UUID(as_uuid=True), ForeignKey("validation_results.result_id", ondelete="CASCADE"), nullable=False)
    original_value = Column(String, nullable=True)
    suggested_fix = Column(String, nullable=True)
    fix_type = Column(String, nullable=False)  # "safe" | "risky"
    human_decision = Column(String, nullable=True)  # "approved" | "rejected" | null
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(String, nullable=True)

    # Relationships
    result = relationship("ValidationResult", back_populates="repair_history")

class HumanFeedbackLog(Base):
    __tablename__ = "human_feedback_logs"
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    error_type = Column(String, nullable=False)
    field = Column(String, nullable=False)
    rule_violated = Column(String, nullable=False)
    original_value = Column(String, nullable=True)
    approved_fix = Column(String, nullable=True)
    feedback_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    industry = Column(String, nullable=False)

class AuditReport(Base):
    __tablename__ = "audit_reports"
    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("validation_jobs.job_id", ondelete="CASCADE"), nullable=False)
    compliance_score = Column(Float, nullable=False, default=100.0)
    total_errors = Column(Integer, nullable=False, default=0)
    auto_fixed = Column(Integer, nullable=False, default=0)
    human_approved = Column(Integer, nullable=False, default=0)
    human_rejected = Column(Integer, nullable=False, default=0)
    certified = Column(Boolean, nullable=False, default=False)
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    final_payload = Column(JSON, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="audit_reports")
    job = relationship("ValidationJob", back_populates="audit_reports")
