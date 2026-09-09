import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr

class UserBase(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    auth_provider: str
    external_auth_id: Optional[str] = None

class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime
    # Note: external_auth_id must never be included in read schemas for clients.
    
    model_config = ConfigDict(from_attributes=True)
