import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        # Never fall back to a shared/default tenant for financial data.
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id)
    except Exception as e:
        logger.error(f"Revenue lookup failed for {property_id} (tenant: {tenant_id}): {e}")
        raise HTTPException(status_code=503, detail="Revenue data temporarily unavailable")

    # Keep money as Decimal end to end; round once, half-up, to cents.
    # Converting to float here caused the "off by a few cents" totals.
    total = Decimal(revenue_data['total']).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": str(total),
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
