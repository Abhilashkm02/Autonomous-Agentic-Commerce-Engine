"""Razorpay SDK wrapper for order creation."""

import razorpay
from razorpay.errors import BadRequestError, GatewayError, ServerError
from backend.config import get_settings


class RazorpayService:
    """Thin wrapper around the Razorpay SDK."""

    def __init__(self, key_id: str, key_secret: str):
        """Initialize with Razorpay API credentials."""
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(self, amount_paise: int, receipt: str, notes: dict = None) -> dict:
        """Create an order in Razorpay.

        Args:
            amount_paise: Order amount in paise (₹1 = 100 paise).
            receipt: Unique receipt identifier.
            notes: Optional metadata notes.

        Returns:
            Razorpay order response dict with id, amount, currency, status.

        Raises:
            Exception: On Razorpay API errors.
        """
        try:
            order_data = {
                'amount': amount_paise,
                'currency': 'INR',
                'receipt': receipt,
                'notes': notes or {}
            }
            order = self.client.order.create(data=order_data)
            return order
        except (BadRequestError, GatewayError, ServerError) as e:
            raise Exception(f"Razorpay API Error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to create Razorpay order: {str(e)}")


def get_razorpay_service() -> RazorpayService:
    """Creates a configured instance of RazorpayService."""
    settings = get_settings()
    return RazorpayService(
        key_id=settings.RAZORPAY_KEY_ID,
        key_secret=settings.RAZORPAY_KEY_SECRET
    )
