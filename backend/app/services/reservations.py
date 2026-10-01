from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy import text

from app.core.database_pool import db_pool


async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Decimal:
    """
    Calculates revenue for a specific month, bucketed in the PROPERTY's local time zone.

    Month boundaries are naive local datetimes. Each reservation's check-in (stored as UTC
    timestamptz) is converted to the property's time zone before comparing, so a booking at
    2024-02-29 23:30 UTC for a Paris property (= 2024-03-01 00:30 local) counts in March.
    """
    start_date = datetime(year, month, 1)
    end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    query = text("""
        SELECT COALESCE(SUM(r.total_amount), 0) AS total
        FROM reservations r
        JOIN properties p
          ON p.id = r.property_id AND p.tenant_id = r.tenant_id
        WHERE r.property_id = :property_id
          AND r.tenant_id = :tenant_id
          AND (r.check_in_date AT TIME ZONE p.timezone) >= :start_date
          AND (r.check_in_date AT TIME ZONE p.timezone) <  :end_date
    """)

    await db_pool.initialize()
    async with db_pool.get_session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "start_date": start_date,
            "end_date": end_date,
        })
        return Decimal(str(result.scalar_one()))


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue for one property of one tenant.

    Errors are NOT swallowed: returning placeholder figures on failure showed fake
    (and cross-tenant) revenue to clients. The caller surfaces the error instead.
    """
    query = text("""
        SELECT
            COALESCE(SUM(total_amount), 0) AS total_revenue,
            COUNT(*) AS reservation_count
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
    """)

    # Use the shared pool instead of creating a new engine on every request.
    await db_pool.initialize()
    async with db_pool.get_session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
        })
        row = result.fetchone()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(Decimal(str(row.total_revenue))),
        "currency": "USD",
        "count": row.reservation_count,
    }
