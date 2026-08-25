"""Tests for graceful failure handling — Razorpay timeout and declined card simulation.

This is a strict judging requirement: the agent must handle failures gracefully,
halt retry loops to prevent duplicate charges, log failures to the audit ledger,
and safely shut down without crashing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from agent.buyer import AutonomousBuyer
from agent.states import AgentState
from agent.decision_engine import PurchaseIntent


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def buyer():
    """Create a buyer agent for testing."""
    return AutonomousBuyer(
        base_url='http://localhost:8000',
        poll_interval=0,  # No delay in tests
        max_failures=3
    )


@pytest.fixture
def sample_intents():
    """Sample purchase intents for testing."""
    return [
        PurchaseIntent(
            sku='SKU-ELEC-001',
            quantity=5,
            reason='Low stock: 5/10',
            price_paise=59900
        )
    ]


@pytest.fixture
def sample_catalog():
    """Sample catalog response for testing."""
    return {
        'products': [
            {
                'id': 1, 'sku': 'SKU-ELEC-001', 'name': 'Wireless Mouse',
                'price_paise': 59900, 'stock': 5, 'reorder_threshold': 10,
                'category': 'Electronics'
            }
        ],
        'timestamp': '2025-01-01T00:00:00',
        'agent_version': '1.0'
    }


# ──────────────────────────────────────────────
# Razorpay Timeout Simulation
# ──────────────────────────────────────────────

class TestRazorpayTimeout:
    """Simulate a Razorpay timeout during order creation."""

    @pytest.mark.asyncio
    async def test_timeout_does_not_crash(self, buyer, sample_intents):
        """Agent catches timeout exception without crashing."""
        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)

        # Mock httpx POST to raise TimeoutException
        buyer._client = AsyncMock()
        buyer._client.post.side_effect = httpx.TimeoutException("Connection timed out")

        # Should not raise
        result = await buyer.purchase(sample_intents)
        assert result == {}

    @pytest.mark.asyncio
    async def test_timeout_logs_failure_message(self, buyer, sample_intents, caplog):
        """Agent logs 'Transaction Failed - Timeout' on timeout."""
        import logging
        buyer.logger.setLevel(logging.ERROR)

        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)

        buyer._client = AsyncMock()
        buyer._client.post.side_effect = httpx.TimeoutException("Connection timed out")

        with caplog.at_level(logging.ERROR, logger='AutonomousBuyer'):
            await buyer.purchase(sample_intents)

        assert any("Transaction Failed - Timeout" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_timeout_transitions_to_failed(self, buyer, sample_intents):
        """Agent transitions to FAILED state on timeout."""
        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)

        buyer._client = AsyncMock()
        buyer._client.post.side_effect = httpx.TimeoutException("Connection timed out")

        await buyer.purchase(sample_intents)
        assert buyer.state in (AgentState.FAILED, AgentState.SHUTDOWN)

    @pytest.mark.asyncio
    async def test_timeout_no_retry(self, buyer, sample_intents):
        """Agent does NOT retry after timeout — prevents duplicate charges."""
        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)

        buyer._client = AsyncMock()
        buyer._client.post.side_effect = httpx.TimeoutException("Connection timed out")

        await buyer.purchase(sample_intents)

        # post should be called exactly once — no retry
        assert buyer._client.post.call_count == 1


# ──────────────────────────────────────────────
# Declined Card / Razorpay Error Simulation
# ──────────────────────────────────────────────

class TestDeclinedCard:
    """Simulate a Razorpay BAD_REQUEST_ERROR (declined card)."""

    @pytest.mark.asyncio
    async def test_declined_card_handled_gracefully(self, buyer, sample_intents):
        """Agent handles a 502 (Razorpay error) without crashing."""
        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)

        # Mock a 502 response
        mock_response = AsyncMock()
        mock_response.status_code = 502
        mock_response.text = '{"error": "BAD_REQUEST_ERROR", "detail": "Card declined"}'

        buyer._client = AsyncMock()
        buyer._client.post.return_value = mock_response

        result = await buyer.purchase(sample_intents)
        assert result == {}

    @pytest.mark.asyncio
    async def test_declined_card_transitions_to_failed(self, buyer, sample_intents):
        """Agent transitions to FAILED on declined card."""
        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)

        mock_response = AsyncMock()
        mock_response.status_code = 502
        mock_response.text = '{"error": "BAD_REQUEST_ERROR"}'

        buyer._client = AsyncMock()
        buyer._client.post.return_value = mock_response

        await buyer.purchase(sample_intents)
        assert buyer.state in (AgentState.FAILED, AgentState.SHUTDOWN)

    @pytest.mark.asyncio
    async def test_declined_card_increments_failure_count(self, buyer, sample_intents):
        """Consecutive failure counter increments on Razorpay error."""
        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)

        mock_response = AsyncMock()
        mock_response.status_code = 502
        mock_response.text = '{"error": "BAD_REQUEST_ERROR"}'

        buyer._client = AsyncMock()
        buyer._client.post.return_value = mock_response

        initial_failures = buyer.consecutive_failures
        await buyer.purchase(sample_intents)
        assert buyer.consecutive_failures == initial_failures + 1


# ──────────────────────────────────────────────
# Retry Halt & Shutdown After Max Failures
# ──────────────────────────────────────────────

class TestRetryHaltAndShutdown:
    """After max_consecutive_failures, agent enters SHUTDOWN state."""

    @pytest.mark.asyncio
    async def test_shutdown_after_max_failures(self, buyer, sample_intents):
        """Agent shuts down after 3 consecutive failures."""
        buyer.max_failures = 3

        for i in range(3):
            # Reset state for each purchase attempt
            buyer.state = AgentState.IDLE
            buyer._transition(AgentState.SCANNING)
            buyer._transition(AgentState.EVALUATING)

            buyer._client = AsyncMock()
            buyer._client.post.side_effect = httpx.TimeoutException("timeout")

            await buyer.purchase(sample_intents)

        assert buyer.state == AgentState.SHUTDOWN
        assert buyer.consecutive_failures >= 3

    @pytest.mark.asyncio
    async def test_successful_purchase_resets_failure_count(self, buyer, sample_intents):
        """A successful purchase resets the consecutive failure counter."""
        buyer.state = AgentState.IDLE
        buyer._transition(AgentState.SCANNING)
        buyer._transition(AgentState.EVALUATING)
        buyer.consecutive_failures = 2  # Nearly at max

        # Mock a successful response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'order_id': 'order_success_123',
            'amount_paise': 59900,
            'currency': 'INR',
            'status': 'created',
            'receipt': 'rcpt_test'
        }

        buyer._client = AsyncMock()
        buyer._client.post.return_value = mock_response

        await buyer.purchase(sample_intents)
        assert buyer.consecutive_failures == 0
        assert buyer.state == AgentState.COMPLETED


# ──────────────────────────────────────────────
# Full Cycle Graceful Failure
# ──────────────────────────────────────────────

class TestFullCycleFailure:
    """Test the full run_cycle with simulated backend failures."""

    @pytest.mark.asyncio
    async def test_cycle_with_backend_down(self, buyer):
        """Agent handles a backend connection error gracefully during scan."""
        buyer._client = AsyncMock()
        buyer._client.get.side_effect = httpx.ConnectError("Connection refused")

        # Should not crash
        await buyer.run_cycle()
        assert buyer.state in (AgentState.FAILED, AgentState.IDLE, AgentState.SHUTDOWN)
        assert buyer.cycle_count == 1

    @pytest.mark.asyncio
    async def test_run_exits_after_max_cycles(self, buyer, sample_catalog):
        """Agent exits cleanly after max_cycles even with no purchases."""
        # Mock catalog with products that don't trigger a buy (stock above threshold)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            'products': [
                {
                    'id': 1, 'sku': 'SKU-TEST-001', 'name': 'Test Product',
                    'price_paise': 10000, 'stock': 100, 'reorder_threshold': 5,
                    'category': 'Test'
                }
            ],
            'timestamp': '2025-01-01T00:00:00',
            'agent_version': '1.0'
        }

        buyer._client = AsyncMock()
        buyer._client.get.return_value = mock_response
        buyer._client.aclose = AsyncMock()

        await buyer.run(max_cycles=2)
        assert buyer.cycle_count == 2
        assert buyer.state == AgentState.SHUTDOWN


# ──────────────────────────────────────────────
# Decision Engine Tests
# ──────────────────────────────────────────────

class TestDecisionEngine:
    """Test the decision engine's evaluation logic."""

    def test_low_stock_triggers_purchase(self):
        """Products below reorder threshold trigger a purchase intent."""
        from agent.decision_engine import DecisionEngine

        engine = DecisionEngine()
        products = [{
            'sku': 'SKU-TEST', 'stock': 3, 'reorder_threshold': 10,
            'price_paise': 10000, 'name': 'Test', 'category': 'Test'
        }]

        intents = engine.evaluate_catalog(products)
        assert len(intents) == 1
        assert intents[0].sku == 'SKU-TEST'
        assert intents[0].quantity == 17  # (10 * 2) - 3
        assert 'Low stock' in intents[0].reason

    def test_no_trigger_when_stock_above_threshold(self):
        """Products with stock above threshold do not trigger purchase."""
        from agent.decision_engine import DecisionEngine

        engine = DecisionEngine()
        products = [{
            'sku': 'SKU-TEST', 'stock': 50, 'reorder_threshold': 10,
            'price_paise': 10000, 'name': 'Test', 'category': 'Test'
        }]

        intents = engine.evaluate_catalog(products)
        assert len(intents) == 0

    def test_price_drop_triggers_purchase(self):
        """A 10%+ price drop triggers a purchase intent."""
        from agent.decision_engine import DecisionEngine

        engine = DecisionEngine()

        # First scan — establish price history
        products_before = [{
            'sku': 'SKU-DROP', 'stock': 50, 'reorder_threshold': 10,
            'price_paise': 10000, 'name': 'Test', 'category': 'Test'
        }]
        engine.evaluate_catalog(products_before)

        # Second scan — price dropped 20%
        products_after = [{
            'sku': 'SKU-DROP', 'stock': 50, 'reorder_threshold': 10,
            'price_paise': 8000, 'name': 'Test', 'category': 'Test'
        }]
        intents = engine.evaluate_catalog(products_after)
        assert len(intents) == 1
        assert 'Price drop' in intents[0].reason

    def test_budget_trimming(self):
        """Intents exceeding the spending limit are trimmed."""
        from agent.decision_engine import DecisionEngine

        engine = DecisionEngine()
        # Product with high price * high reorder = over budget
        products = [{
            'sku': 'SKU-EXPENSIVE', 'stock': 0, 'reorder_threshold': 100,
            'price_paise': 100000, 'name': 'Expensive', 'category': 'Test'
        }]

        intents = engine.evaluate_catalog(products)
        # Total would be 200 * 100000 = 20,000,000 paise — way over 500,000
        # Engine should trim or the single intent cost should be checked
        total_cost = sum(i.price_paise * i.quantity for i in intents)
        assert total_cost <= engine.SPENDING_LIMIT or len(intents) == 0
