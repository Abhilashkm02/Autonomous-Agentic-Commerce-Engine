"""Tests for financial guardrails and spending boundary enforcement."""

import pytest
from unittest.mock import patch, MagicMock


class TestSpendingBoundaries:
    """Test the hard stop-loss spending limits."""

    def test_order_within_limit(self, test_client):
        """A ₹599 order (single Wireless Mouse) should succeed."""
        payload = {
            "items": [{"sku": "SKU-ELEC-001", "quantity": 1}],
            "trigger_reason": "test_within_limit"
        }
        response = test_client.post("/api/checkout", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == "order_test_123456"
        assert data["amount_paise"] == 59900
        assert data["status"] == "created"

    def test_order_exceeds_limit(self, test_client):
        """An order exceeding ₹5,000 should be rejected with HTTP 422."""
        # 3x Mechanical Keyboard = 3 * ₹2,499 = ₹7,497 > ₹5,000
        payload = {
            "items": [{"sku": "SKU-ELEC-002", "quantity": 3}],
            "trigger_reason": "test_exceeds_limit"
        }
        response = test_client.post("/api/checkout", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "SpendingLimitExceeded"
        assert data["max_allowed_paise"] == 500000
        assert data["attempted_paise"] == 749700

    def test_order_at_exact_limit(self, test_client, mock_razorpay):
        """An order at exactly ₹5,000 (500000 paise) should succeed."""
        # Mock the Razorpay response for this specific amount
        mock_razorpay.create_order.return_value = {
            'id': 'order_at_limit_test',
            'amount': 500000,
            'currency': 'INR',
            'status': 'created',
            'receipt': 'rcpt_limit_test'
        }

        # We need a product that costs exactly 500000 paise
        # Use a patched product price for this boundary test
        with patch('backend.routes.checkout.get_product_by_sku') as mock_product:
            mock_product.return_value = MagicMock(
                price_paise=500000, sku='SKU-BOUNDARY'
            )
            with patch('backend.routes.checkout.validate_cart_items'):
                with patch('backend.routes.checkout.update_stock'):
                    payload = {
                        "items": [{"sku": "SKU-BOUNDARY", "quantity": 1}],
                        "trigger_reason": "test_exact_limit"
                    }
                    response = test_client.post("/api/checkout", json=payload)
                    assert response.status_code == 200

    def test_empty_cart_rejected(self, test_client):
        """An empty items list should return 422 (Pydantic validation)."""
        payload = {"items": []}
        response = test_client.post("/api/checkout", json=payload)
        assert response.status_code == 422

    def test_invalid_sku_returns_400(self, test_client):
        """A non-existent SKU should return 400."""
        payload = {
            "items": [{"sku": "SKU-FAKE-999", "quantity": 1}],
            "trigger_reason": "test_invalid_sku"
        }
        response = test_client.post("/api/checkout", json=payload)
        assert response.status_code == 400

    def test_insufficient_stock_returns_400(self, test_client):
        """Ordering more than available stock should return 400."""
        # SKU-ELEC-004 has stock=2, try ordering 100
        payload = {
            "items": [{"sku": "SKU-ELEC-004", "quantity": 100}],
            "trigger_reason": "test_insufficient_stock"
        }
        response = test_client.post("/api/checkout", json=payload)
        assert response.status_code == 400


class TestGuardrailsUnit:
    """Unit tests for the guardrails module directly."""

    def test_enforce_limits_passes_within_limit(self):
        """enforce_limits should not raise for amounts within limit."""
        from backend.services.guardrails import enforce_limits
        # Should not raise
        enforce_limits(400000, max_paise=500000)

    def test_enforce_limits_raises_over_limit(self):
        """enforce_limits should raise SpendingLimitExceeded for amounts over limit."""
        from backend.services.guardrails import enforce_limits, SpendingLimitExceeded
        with pytest.raises(SpendingLimitExceeded) as exc_info:
            enforce_limits(600000, max_paise=500000)
        assert exc_info.value.amount_paise == 600000
        assert exc_info.value.max_paise == 500000

    def test_enforce_limits_passes_at_exact_limit(self):
        """enforce_limits should not raise for amounts exactly at the limit."""
        from backend.services.guardrails import enforce_limits
        # Should not raise
        enforce_limits(500000, max_paise=500000)
