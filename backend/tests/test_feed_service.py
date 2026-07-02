import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, ContentType
from app.models.progress import UserContentProgress
from app.models.topic import Topic
from app.models.user import User, UserTopicInterest
from app.schemas.feed import ProgressUpdateRequest
from app.services import feed_service


async def _make_topic(db: AsyncSession, slug: str = "digital-infrastructure") -> Topic:
    topic = Topic(
        slug=slug,
        name="Digital Infrastructure",
        description="...",
        accent_colour="#CC3300",
    )
    db.add(topic)
    await db.flush()
    return topic


async def _make_user(db: AsyncSession) -> User:
    user = User(cognito_sub="sub-1", email="a@example.com", first_name="A", last_name="B")
    db.add(user)
    await db.flush()
    return user


async def test_get_feed_returns_content_for_users_interests_ordered_newest_first(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    interested_topic = await _make_topic(db_session, slug="cloud")
    other_topic = await _make_topic(db_session, slug="cyber")
    db_session.add(UserTopicInterest(user_id=user.id, topic_id=interested_topic.id))

    older = Content(
        title="Older", content_type=ContentType.article, topic_id=interested_topic.id
    )
    newer = Content(
        title="Newer", content_type=ContentType.article, topic_id=interested_topic.id
    )
    unrelated = Content(
        title="Unrelated", content_type=ContentType.article, topic_id=other_topic.id
    )
    db_session.add_all([older, newer, unrelated])
    await db_session.commit()
    # force distinct created_at ordering deterministically
    older.created_at = older.created_at.replace(year=2020)
    await db_session.commit()

    result = await feed_service.get_feed(db_session, user)

    titles = [c.title for c in result]
    assert titles == ["Newer", "Older"]


async def test_get_feed_returns_empty_list_when_user_has_no_topic_interests(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    result = await feed_service.get_feed(db_session, user)
    assert result == []


async def test_get_progress_returns_only_in_progress_items_newest_first(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    topic = await _make_topic(db_session)
    in_progress = Content(title="In progress", content_type=ContentType.article, topic_id=topic.id)
    finished = Content(title="Finished", content_type=ContentType.article, topic_id=topic.id)
    db_session.add_all([in_progress, finished])
    await db_session.flush()
    db_session.add(
        UserContentProgress(user_id=user.id, content_id=in_progress.id, progress_pct=40)
    )
    db_session.add(
        UserContentProgress(user_id=user.id, content_id=finished.id, progress_pct=100)
    )
    await db_session.commit()

    result = await feed_service.get_progress(db_session, user)

    assert len(result) == 1
    assert result[0].content.title == "In progress"
    assert result[0].progress_pct == 40


async def test_upsert_progress_inserts_new_row(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    topic = await _make_topic(db_session)
    content = Content(title="Snippet", content_type=ContentType.article, topic_id=topic.id)
    db_session.add(content)
    await db_session.commit()

    await feed_service.upsert_progress(
        db_session, user, content.id, ProgressUpdateRequest(progress_pct=25)
    )

    result = await feed_service.get_progress(db_session, user)
    assert len(result) == 1
    assert result[0].progress_pct == 25


async def test_upsert_progress_updates_existing_row(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    topic = await _make_topic(db_session)
    content = Content(title="Snippet", content_type=ContentType.article, topic_id=topic.id)
    db_session.add(content)
    await db_session.flush()
    db_session.add(UserContentProgress(user_id=user.id, content_id=content.id, progress_pct=10))
    await db_session.commit()

    await feed_service.upsert_progress(
        db_session, user, content.id, ProgressUpdateRequest(progress_pct=80)
    )

    result = await feed_service.get_progress(db_session, user)
    assert len(result) == 1
    assert result[0].progress_pct == 80


async def test_upsert_progress_raises_404_for_missing_content(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await feed_service.upsert_progress(
            db_session, user, 999, ProgressUpdateRequest(progress_pct=10)
        )
    assert exc_info.value.status_code == 404
