from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship
from app.core.clock import UTCDateTime, format_ist, utcnow

Base = declarative_base()

class JobPosting(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(512), default="Unknown")
    remote_status = Column(String(100), default="Unknown") # Remote, Hybrid, Onsite
    role_category = Column(String(255), default="Software Engineering")
    fingerprint = Column(String(64), index=True, nullable=True)
    url = Column(String(1024), unique=True, nullable=False, index=True)
    source_platform = Column(String(100), nullable=False, index=True)
    description = Column(Text, default="")
    posted_date = Column(String(100), default="")
    posted_at = Column(UTCDateTime, nullable=True, index=True)
    posted_date_unverified = Column(Boolean, default=False, nullable=False)
    discovered_at = Column(UTCDateTime, default=utcnow, index=True)

    # Intelligence Match Details
    match_score = Column(Float, default=0.0, index=True)
    match_tier = Column(String(100), default="P1", index=True) # P1, P2, P3, Excluded (Location), etc.
    match_reason = Column(Text, default="{}") # JSON metadata: matched_skills, missing_skills, reasoning

    # Workflow Status
    status = Column(String(100), default="new", index=True) # new, reviewed, tailored, applied, rejected, archived
    notified = Column(Boolean, default=False, index=True)
    notified_at = Column(UTCDateTime, nullable=True)
    notify_attempts = Column(Integer, default=0, nullable=False, index=True)
    next_attempt_at = Column(UTCDateTime, nullable=True, index=True)
    last_error = Column(String(500), nullable=True)
    tailor_status = Column(String(20), default="pending", nullable=False, index=True)

    # Relationships
    application = relationship("TailoredApplication", back_populates="job", uselist=False, cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self, include_description: bool = True):
        has_app = False
        if "application" in self.__dict__:
            has_app = self.__dict__["application"] is not None
        data = {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "remote_status": self.remote_status,
            "role_category": self.role_category,
            "fingerprint": self.fingerprint,
            "url": self.url,
            "source_platform": self.source_platform,
            "posted_date": self.posted_date,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "posted_at_ist": format_ist(self.posted_at) if self.posted_at else None,
            "posted_date_unverified": bool(self.posted_date_unverified),
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
            "discovered_at_ist": format_ist(self.discovered_at) if self.discovered_at else None,
            "match_score": self.match_score,
            "match_tier": self.match_tier,
            "match_reason": self.match_reason,
            "status": self.status,
            "notified": self.notified,
            "notified_at": self.notified_at.isoformat() if self.notified_at else None,
            "notified_at_ist": format_ist(self.notified_at) if self.notified_at else None,
            "notify_attempts": self.notify_attempts or 0,
            "next_attempt_at": self.next_attempt_at.isoformat() if self.next_attempt_at else None,
            "next_attempt_at_ist": format_ist(self.next_attempt_at) if self.next_attempt_at else None,
            "last_error": self.last_error,
            "tailor_status": self.tailor_status or "pending",
            "has_tailored_application": has_app
        }
        if include_description:
            data["description"] = self.__dict__.get("description", getattr(self, "description", "")) or ""
        return data

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
    created_at = Column(UTCDateTime, default=utcnow)

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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_at_ist": format_ist(self.created_at) if self.created_at else None
        }

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(UTCDateTime, default=utcnow, index=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, default="")
    status = Column(String(50), default="success")

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": format_ist(self.timestamp) if self.timestamp else None,
            "action": self.action,
            "details": self.details,
            "status": self.status
        }

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

class SessionRecord(Base):
    __tablename__ = "sessions"

    sid = Column(String(64), primary_key=True)
    csrf_token = Column(String(64), nullable=False)
    created_at = Column(UTCDateTime, default=utcnow, nullable=False)
    expires_at = Column(UTCDateTime, nullable=False, index=True)
    client_ip = Column(String(50), default="")

class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(50), nullable=False, index=True)
    attempted_at = Column(UTCDateTime, default=utcnow, index=True)
    success = Column(Boolean, default=False)


class SeenJob(Base):
    __tablename__ = "seen_jobs"

    url_hash = Column(String(64), primary_key=True)
    fingerprint = Column(String(64), index=True, nullable=False)
    first_seen_at = Column(UTCDateTime, default=utcnow, nullable=False)
    last_seen_at = Column(UTCDateTime, default=utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "url_hash": self.url_hash,
            "fingerprint": self.fingerprint,
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }
