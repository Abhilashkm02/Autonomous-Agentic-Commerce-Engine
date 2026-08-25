"""Checkout and ledger API routes."""

import uuid
import json
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException

from backend.database import get_db, update_stock, get_product_by_sku
from backend.models import CheckoutRequest, CheckoutResponse, LedgerEntry, ErrorResponse
from backend.services.guardrails import enforce_limits, validate_cart_items, SpendingLimitExceeded
from backend.services.razorpay_client import get_razorpay_service
from backend.services.ledger import log_transaction, get_all_transactions

router = APIRouter(prefix="/api")


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(request: CheckoutRequest):
    """Executes a purchase transaction within guardrails.

    Flow:
    1. Validate all SKUs exist and have sufficient stock
    2. Calculate total in paise
    3. Enforce spending limits (hard stop-loss before Razorpay)
    4. Create Razorpay order
    5. Deduct stock
    6. Log to audit ledger
    7. Return order confirmation
    """
    razorpay_service = get_razorpay_service()
    skus_list: list[str] = []

    with get_db() as conn:
        total_paise = 0
        try:
            # 1. Validate cart items
            validate_cart_items(request.items, conn)

            # 2. Calculate total_paise
            for item in request.items:
                product = get_product_by_sku(conn, item.sku)
                total_paise += product.price_paise * item.quantity
                skus_list.append(item.sku)

            # 3. Enforce spending limits — HARD STOP-LOSS
            enforce_limits(total_paise)

            # 4. Generate receipt string
            receipt = f"rcpt_{uuid.uuid4().hex[:12]}"

            # 5. Create Razorpay order
            notes = {'skus': json.dumps(skus_list)}
            order = razorpay_service.create_order(total_paise, receipt, notes)

            # 6. Deduct stock
            for item in request.items:
                update_stock(conn, item.sku, item.quantity)

            # 7. Log success to ledger
            trigger_reason = request.trigger_reason or 'manual_checkout'
            entry = LedgerEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                trigger_reason=trigger_reason,
                skus=skus_list,
                cart_value_paise=total_paise,
                razorpay_order_id=order['id'],
                status="success",
                error_message=None
            )
            log_transaction(entry, conn)

            # 8. Return response
            return CheckoutResponse(
                order_id=order['id'],
                amount_paise=total_paise,
                currency=order.get('currency', 'INR'),
                receipt=receipt,
                status=order.get('status', 'created')
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except SpendingLimitExceeded:
            # Re-raise to be handled by the app-level exception handler
            raise
        except Exception as e:
            # Log failure to ledger
            trigger_reason = request.trigger_reason or 'manual_checkout'
            entry = LedgerEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                trigger_reason=trigger_reason,
                skus=skus_list,
                cart_value_paise=total_paise,
                razorpay_order_id=None,
                status="failed",
                error_message=str(e)
            )
            try:
                log_transaction(entry, conn)
            except Exception:
                pass  # Don't crash on ledger write failure

            # 502 for Razorpay errors, 500 for general
            error_str = str(e).lower()
            if "razorpay" in error_str or "network" in error_str:
                raise HTTPException(
                    status_code=502,
                    detail=f"Payment gateway error: {str(e)}"
                )

            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )


@router.get("/ledger", response_model=List[LedgerEntry])
def get_ledger():
    """Returns all ledger entries for real-time audit trail viewing."""
    with get_db() as conn:
        transactions = get_all_transactions(conn)
        return transactions
