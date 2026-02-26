from __future__ import annotations

import datetime
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import Integer, Select, Date, String, and_, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.job import InstancerDailyUsage, Job, JobStatus


@dataclass(slots=True)
class DailyQuotaState:
    date_utc: datetime.date
    capacity: int
    used_count: int

    @property
    def remaining(self) -> int:
        return max(self.capacity - self.used_count, 0)


class DailyQuotaExceededError(Exception):
    """Raised when the daily worker limit has been reached."""


async def _ensure_row_for_today(
    session: AsyncSession,
    *,
    today: datetime.date,
    capacity: int,
) -> None:
    stmt = pg_insert(InstancerDailyUsage).values(
        date_utc=today,
        capacity=capacity,
        used_count=0,
    ).on_conflict_do_nothing(
        index_elements=[InstancerDailyUsage.date_utc],
    )
    await session.execute(stmt)

    # If env limit increased, bump capacity up to the new value.
    inc_stmt = (
        update(InstancerDailyUsage)
        .where(
            InstancerDailyUsage.date_utc == today,
            InstancerDailyUsage.capacity < capacity,
        )
        .values(capacity=capacity)
    )
    await session.execute(inc_stmt)

    # If env limit decreased, shrink capacity only when used_count does not exceed the new limit.
    dec_stmt = (
        update(InstancerDailyUsage)
        .where(
            InstancerDailyUsage.date_utc == today,
            InstancerDailyUsage.capacity > capacity,
            InstancerDailyUsage.used_count <= capacity,
        )
        .values(capacity=capacity)
    )
    await session.execute(dec_stmt)


async def get_daily_quota_state(
    session: AsyncSession,
    *,
    today: datetime.date | None = None,
    default_capacity: int,
) -> DailyQuotaState:
    if today is None:
        today = datetime.datetime.now(datetime.UTC).date()

    await _ensure_row_for_today(session, today=today, capacity=default_capacity)

    stmt: Select[tuple[datetime.date, int, int]] = select(
        InstancerDailyUsage.date_utc,
        InstancerDailyUsage.capacity,
        InstancerDailyUsage.used_count,
    ).where(InstancerDailyUsage.date_utc == today)

    row = (await session.execute(stmt)).one()
    date_utc, capacity, used_count = row
    return DailyQuotaState(date_utc=date_utc, capacity=capacity, used_count=used_count)


async def check_and_increment_daily_quota(
    session: AsyncSession,
    *,
    job_id: str,
    default_capacity: int,
) -> DailyQuotaState:
    """Atomically check and increment the daily quota.

    Raises:
        DailyQuotaExceededError: if the daily limit has been reached.
    """
    today = datetime.datetime.now(datetime.UTC).date()

    await _ensure_row_for_today(session, today=today, capacity=default_capacity)

    update_stmt = (
        update(InstancerDailyUsage)
        .where(
            InstancerDailyUsage.date_utc == today,
            InstancerDailyUsage.used_count < InstancerDailyUsage.capacity,
        )
        .values(used_count=InstancerDailyUsage.used_count + 1)
        .returning(
            InstancerDailyUsage.date_utc,
            InstancerDailyUsage.capacity,
            InstancerDailyUsage.used_count,
        )
    )

    result = await session.execute(update_stmt)
    row = result.first()
    if row is None:
        logger.warning(
            "Daily worker limit reached for date={}, job_id={}",
            today,
            job_id,
        )
        raise DailyQuotaExceededError(f"Daily worker limit reached for date={today}")

    date_utc, capacity, used_count = row
    return DailyQuotaState(date_utc=date_utc, capacity=capacity, used_count=used_count)

