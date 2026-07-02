from datetime import datetime

from pydantic import BaseModel, Field

# Defined here (rather than in chat_service, which imports several schemas
# from this module) so both chat_service and ChatSessionRenameRequest below
# can share one constant without introducing a circular import.
TITLE_MAX_LEN = 60


class ChatSessionRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX_LEN)


class ChatSessionSummary(BaseModel):
    id: int
    title: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageSource(BaseModel):
    content_id: int
    title: str


class ChatMessageRecord(BaseModel):
    id: int
    role: str
    text: str
    sources: list[ChatMessageSource] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetail(BaseModel):
    id: int
    title: str
    messages: list[ChatMessageRecord]


class ChatMessageRequest(BaseModel):
    message: str
