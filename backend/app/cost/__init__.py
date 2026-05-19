"""Daily cost tracking — the financial kill-switch.

See SPEC §8.3 and the CLAUDE.md 'critical rules' section. The cost guard
MUST NOT be bypassed. Cost is debited *after* generation so a single
expensive run can't pre-empt the budget; the check at job creation time
uses the rolling debited total.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import DailyCost


async def get_today_cost(session: AsyncSession) -> Decimal:
    """Return today's debited cost total (UTC). 0 if no debits yet."""
    row = await _fetch_today(session)
    if row is None:
        return Decimal("0")
    return Decimal(row.total_cost_usd)


async def record_cost(session: AsyncSession, cost_usd: Decimal) -> None:
    """Debit `cost_usd` to today's daily_costs row. No-op if cost is zero.

    Caller is responsible for committing the surrounding transaction.
    """
    if cost_usd <= 0:
        return
    row = await _fetch_today(session)
    if row is None:
        session.add(
            DailyCost(
                date=date.today(),
                total_cost_usd=cost_usd,
                job_count=1,
            )
        )
    else:
        row.total_cost_usd = Decimal(row.total_cost_usd) + cost_usd
        row.job_count = (row.job_count or 0) + 1
    await session.flush()


async def _fetch_today(session: AsyncSession) -> DailyCost | None:
    result = await session.execute(
        select(DailyCost).where(DailyCost.date == date.today())
    )
    return result.scalar_one_or_none()
