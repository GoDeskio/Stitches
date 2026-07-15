from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any


# ---------------- Models ----------------
class RegisterInput(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company: Optional[str] = None
    company_role: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    project_info: Optional[str] = None
    theme: Optional[str] = None
    ui_scale: Optional[float] = None
    notification_prefs: Optional[Dict[str, bool]] = None


class NotifGlobalInput(BaseModel):
    settings: Dict[str, bool]


class ReactInput(BaseModel):
    emoji: str


class NoteInput(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    color: Optional[str] = None


class WorkspaceInput(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = None


class InviteInput(BaseModel):
    email: EmailStr


class ChannelInput(BaseModel):
    workspace_id: str
    name: str
    type: Optional[str] = "channel"
    description: Optional[str] = ""


class MessageInput(BaseModel):
    channel_id: str
    text: str
    parent_id: Optional[str] = None
    mentions: List[str] = []


class ProjectInput(BaseModel):
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "active"
    workspace_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class TaskInput(BaseModel):
    title: str
    description: Optional[str] = ""
    status: Optional[str] = "todo"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class GoogleOAuthInput(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class IntegrationInput(BaseModel):
    type: str
    name: str
    config: Dict[str, Any] = {}
    auth_method: Optional[str] = None


class IntegrationRunInput(BaseModel):
    payload: Dict[str, Any] = {}


class FileKeyInput(BaseModel):
    key: str


class AiInput(BaseModel):
    message: str
    model: Optional[str] = "gpt-5.4"
    provider: Optional[str] = "openai"
    conversation_id: Optional[str] = None


class SeoInput(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    og_image: Optional[str] = None


class FeatureFlagsInput(BaseModel):
    flags: Dict[str, bool]


class SetPasswordInput(BaseModel):
    password: str


class UserAdminUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class EmailInput(BaseModel):
    email: EmailStr


class UserIdInput(BaseModel):
    user_id: str


