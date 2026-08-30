from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
import datetime
from .db import Base

class Incident(Base):
    __tablename__ = "incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String)
    service = Column(String)
    severity = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    trigger = Column(String)
    status = Column(String)
    initial_metrics = Column(JSON)
    resolved_at = Column(DateTime)

class Evidence(Base):
    __tablename__ = "evidence"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    category = Column(String)
    content = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RemediationAction(Base):
    __tablename__ = "remediation_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    action_type = Column(String)
    params = Column(JSON)
    risk_level = Column(String)
    approved = Column(Boolean, default=False)
    approved_by = Column(String)
    executed_at = Column(DateTime)
    status = Column(String)
    result = Column(JSON, nullable=True)

class VerificationResult(Base):
    __tablename__ = "verification_results"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"))
    before_metrics = Column(JSON)
    after_metrics = Column(JSON)
    recovered = Column(Boolean)
    checked_at = Column(DateTime, default=datetime.datetime.utcnow)
