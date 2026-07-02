import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.chat import ChatMessageRequest, ChatSessionDetail, ChatSessionSummary
from app.schemas.library import ContentSearchResult, LibraryResponse
from app.services import chat_service, library_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/", response_model=LibraryResponse, summary="Get user's library")
async def get_library(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LibraryResponse:
    return await library_service.get_library(db, current_user)


@router.get(
    "/search",
    response_model=list[ContentSearchResult],
    summary="Semantic search across catalogue",
)
async def search(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ContentSearchResult]:
    return await library_service.semantic_search(db, q, current_user)


@router.get("/chats", response_model=list[ChatSessionSummary], summary="List chat sessions")
async def list_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionSummary]:
    sessions = await chat_service.list_sessions(db, current_user)
    return [ChatSessionSummary.model_validate(s) for s in sessions]


@router.post("/chats", response_model=ChatSessionSummary, summary="Create a new chat session")
async def create_chat(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionSummary:
    session = await chat_service.create_session(db, current_user)
    return ChatSessionSummary.model_validate(session)


@router.get(
    "/chats/{session_id}", response_model=ChatSessionDetail, summary="Get chat session detail"
)
async def get_chat(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetail:
    session = await chat_service.get_session_or_404(db, session_id, current_user)
    return await chat_service.get_session_detail(db, session)


@router.post("/chats/{session_id}/messages", summary="Send a message, stream the mentor's reply")
async def post_chat_message(
    session_id: int,
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    session = await chat_service.get_session_or_404(db, session_id, current_user)

    async def event_generator():
        # StreamingResponse sends the 200 status + headers as soon as this
        # generator starts running, so an HTTPException raised anywhere inside
        # stream_mentor_reply (e.g. embed_text failing because Bedrock is
        # unreachable/uncredentialled) can no longer become a normal HTTP error
        # response — Starlette would just abort the connection with
        # "Caught handled exception, but response already started." Catch it
        # here and surface it as an SSE error frame instead so the frontend
        # can show the student a real message rather than a silently-dropped
        # reply or a broken connection.
        try:
            async for delta in chat_service.stream_mentor_reply(
                db, session, body.message, current_user
            ):
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except HTTPException as exc:
            yield f"data: {json.dumps({'error': exc.detail})}\n\n"
            return
        except Exception:
            # Belt-and-braces: stream_mentor_reply converts the Bedrock error
            # paths it knows about into HTTPException, but *any* other
            # exception type reaching here would otherwise crash the SSE
            # connection outright (Starlette can't attach CORS/error headers
            # once the response has started streaming) — the browser then
            # reports a bare NetworkError with no useful detail. Log it and
            # degrade to an SSE error frame instead of a dead connection.
            logger.exception(
                "Unhandled error while streaming mentor reply for session %s", session_id
            )
            yield f"data: {json.dumps({'error': 'The mentor is temporarily unavailable'})}\n\n"
            return
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
