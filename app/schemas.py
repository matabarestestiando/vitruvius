from typing import Literal
from pydantic import BaseModel, Field


class ExpertIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    specialty: str = Field(min_length=1, max_length=1000)
    principles: str = Field(default="", max_length=16000)
    model: str | None = None
    skill_ids: list[str] = Field(default_factory=list, max_length=30)


class BoardIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    expert_ids: list[str] = Field(min_length=1, max_length=12)
    mission: str = Field(default="", max_length=4000)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=8000)


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    content: str = Field(min_length=1, max_length=64000)
    previous_id: str | None = None
    active: bool = True


class SessionIn(BaseModel):
    board_id: str
    project_id: str
    title: str = Field(default="Nueva discusión", max_length=200)


class TurnIn(BaseModel):
    text: str = Field(min_length=1, max_length=24000)
    max_turns: int = Field(default=5, ge=1, le=12)


class SourceMetadata(BaseModel):
    medium: Literal["text", "video", "social", "pdf"] = "text"
    kind: Literal["author_work", "official_documentation", "other"] = "author_work"
    reviewed_by_owner: bool = False
    author: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2000)
    edition: str | None = Field(default=None, max_length=200)
    published_at: str | None = Field(default=None, max_length=100)
    rights_confirmed: bool = False


class ContextIn(BaseModel):
    source: SourceMetadata | None = None
    session_id: str
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default="", max_length=200000)
    scope: Literal["REQUEST", "SESSION", "PROJECT", "BOARD", "EXPERT", "GLOBAL"] = (
        "SESSION"
    )
    expert_ids: list[str] = Field(default_factory=list, max_length=12)
    retention_hours: int = Field(default=24, ge=1, le=720)
    permanent_consent: bool = False


class ArtifactIn(BaseModel):
    project_id: str
    session_id: str
    kind: Literal["requirement", "adr", "specification"]
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=64000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=50)
    previous_id: str | None = None


class MemoryIn(BaseModel):
    text: str = Field(min_length=1, max_length=24000)
    scope: Literal["personal", "project", "board", "expert"]
    target_id: str | None = None
    approved: bool = False


class RepositoryIn(BaseModel):
    project_id: str
    path: str


class ConnectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str
    token_env: str | None = None
    expert_ids: list[str] = Field(default_factory=list)
    read_tools: list[str] = Field(default_factory=list)
    write_tools: list[str] = Field(default_factory=list)


class ToolCallIn(BaseModel):
    expert_id: str
    tool: str
    arguments: dict = Field(default_factory=dict)


class DraftIn(BaseModel):
    kind: Literal["requirement", "adr", "specification"] = "specification"


class ReviewIn(BaseModel):
    repository_id: str
    query: str = Field(min_length=1, max_length=200)


class MemorySearchIn(BaseModel):
    scope: Literal["personal", "project", "board", "expert"]
    target_id: str | None = None
    query: str = Field(min_length=1, max_length=4000)


class ExpertLibraryIn(BaseModel):
    document_ids: list[str] = Field(max_length=100)
    role: Literal["primary", "complementary"] = "primary"
    approved: bool = False


class ExpertReferenceIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=200)
    kind: Literal["article", "x_post", "pdf", "youtube"]
    url: str | None = Field(default=None, max_length=2000)


class ReferenceImportIn(BaseModel):
    session_id: str
    permanent_consent: bool = False


class ReferenceTextIn(ReferenceImportIn):
    text: str = Field(min_length=1, max_length=200000)


class ProfileDraftIn(BaseModel):
    session_id: str


class ProfileApprovalIn(BaseModel):
    approved: bool = False
