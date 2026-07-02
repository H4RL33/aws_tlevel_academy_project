from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content import Content, ContentTag
from app.models.progress import UserContentProgress
from app.models.user import User, UserTopicInterest
from app.schemas.content import ContentListResponse, TagResponse
from app.schemas.feed import ProgressResponse, ProgressUpdateRequest


def _to_list_response(content: Content) -> ContentListResponse:
    return ContentListResponse(
        id=content.id,
        title=content.title,
        content_type=content.content_type,
        topic_id=content.topic_id,
        t_level_id=content.t_level_id,
        tags=[TagResponse.model_validate(ct.tag) for ct in content.content_tags],
        created_at=content.created_at,
    )


async def get_feed(db: AsyncSession, current_user: User) -> list[ContentListResponse]:
    """
    Return a personalised list of Content items for the current user.

    1. Find all topic_ids from the user's UserTopicInterest rows.
    2. Return Content rows whose topic_id is in the user's topics,
       ordered by created_at DESC.

    Future enhancement (do not implement now): re-rank by tag overlap with
    the user's engagement history.
    """
    topic_ids_result = await db.execute(
        select(UserTopicInterest.topic_id).where(UserTopicInterest.user_id == current_user.id)
    )
    topic_ids = [row[0] for row in topic_ids_result.all()]
    if not topic_ids:
        return []

    result = await db.execute(
        select(Content)
        .options(selectinload(Content.content_tags).selectinload(ContentTag.tag))
        .where(Content.topic_id.in_(topic_ids))
        .order_by(Content.created_at.desc())
    )
    contents = result.scalars().all()
    return [_to_list_response(c) for c in contents]


async def get_progress(db: AsyncSession, current_user: User) -> list[ProgressResponse]:
    """
    Return the user's in-progress Content items (progress_pct < 100),
    ordered by last_viewed_at DESC.
    Join UserContentProgress → Content to populate the nested content field.
    """
    result = await db.execute(
        select(UserContentProgress)
        .options(
            selectinload(UserContentProgress.content)
            .selectinload(Content.content_tags)
            .selectinload(ContentTag.tag)
        )
        .where(
            UserContentProgress.user_id == current_user.id,
            UserContentProgress.progress_pct < 100,
        )
        .order_by(UserContentProgress.last_viewed_at.desc())
    )
    progress_rows = result.scalars().all()
    return [
        ProgressResponse(
            content_id=row.content_id,
            last_viewed_at=row.last_viewed_at,
            progress_pct=row.progress_pct,
            content=_to_list_response(row.content),
        )
        for row in progress_rows
    ]


async def upsert_progress(
    db: AsyncSession,
    current_user: User,
    content_id: int,
    payload: ProgressUpdateRequest,
) -> None:
    """
    Insert or update a UserContentProgress row.

    - If a row exists for (user_id, content_id): update progress_pct and last_viewed_at.
    - If no row exists: insert a new row.
    - Raise HTTP 404 if content_id does not exist in the content table.
    """
    content_exists = await db.execute(select(Content.id).where(Content.id == content_id))
    if content_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Content not found")

    result = await db.execute(
        select(UserContentProgress).where(
            UserContentProgress.user_id == current_user.id,
            UserContentProgress.content_id == content_id,
        )
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        db.add(
            UserContentProgress(
                user_id=current_user.id,
                content_id=content_id,
                progress_pct=payload.progress_pct,
            )
        )
    else:
        # last_viewed_at has onupdate=func.now(), so it refreshes automatically
        # whenever this row is part of an UPDATE — no need to set it explicitly.
        progress.progress_pct = payload.progress_pct
    await db.commit()
