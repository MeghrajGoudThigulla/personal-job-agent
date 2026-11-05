import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def get_utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

class JobPosting(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), default="Unknown")
    remote_status = Column(String(50), default="Unknown") # Remote, Hybrid, Onsite
    role_category = Column(String(100), default="Software Engineering")
    url = Column(String(512), unique=True, nullable=False, index=True)
    source_platform = Column(String(100), nullable=False, index=True)
    description = Column(Text, default="")
    posted_date = Column(String(100), default="")
    discovered_at = Column(DateTime, default=get_utc_now, index=True)
    
    # Intelligence Match Details
    match_score = Column(Float, default=0.0, index=True)
    match_tier = Column(String(10), default="P1") # P1, P2, P3
    match_reason = Column(Text, default="{}") # JSON metadata: matched_skills, missing_skills, reasoning
    
    # Workflow Status
    status = Column(String(50), default="new", index=True) # new, reviewed, tailored, applied, rejected, archived
    notified = Column(Boolean, default=False, index=True)
    notified_at = Column(DateTime, nullable=True)

    # Relationships
    application = relationship("TailoredApplication", back_populates="job", uselist=False, cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self):
        has_app = False
        if "application" in self.__dict__:
            has_app = self.__dict__["application"] is not None
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "remote_status": self.remote_status,
            "role_category": self.role_category,
            "url": self.url,
            "source_platform": self.source_platform,
            "description": self.description,
            "posted_date": self.posted_date,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
            "match_score": self.match_score,
            "match_tier": self.match_tier,
            "match_reason": self.match_reason,
            "status": self.status,
            "notified": self.notified,
            "notified_at": self.notified_at.isoformat() if self.notified_at else None,
            "has_tailored_application": has_app
        }

class TailoredApplication(Base):
    __tablename__ = "tailored_applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    tailored_resume_tex = Column(Text, default="")
    tailored_resume_md = Column(Text, default="")
    pdf_path = Column(String(512), default="")
    cold_email_hr = Column(Text, default="")
    cold_email_hiring_manager = Column(Text, default="")
    linkedin_4mm = Column(Text, default="")
    slop_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=get_utc_now)

    job = relationship("JobPosting", back_populates="application")

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "tailored_resume_tex": self.tailored_resume_tex,
            "tailored_resume_md": self.tailored_resume_md,
            "pdf_path": self.pdf_path,
            "cold_email_hr": self.cold_email_hr,
            "cold_email_hiring_manager": self.cold_email_hiring_manager,
            "linkedin_4mm": self.linkedin_4mm,
            "slop_score": self.slop_score,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=get_utc_now, index=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, default="")
    status = Column(String(50), default="success")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "action": self.action,
            "details": self.details,
            "status": self.status
        }

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)
