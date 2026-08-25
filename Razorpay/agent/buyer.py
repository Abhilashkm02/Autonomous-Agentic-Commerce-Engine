"""Autonomous buyer agent implementation."""

import asyncio
import json
import logging
from typing import Any

import httpx

from agent.states import AgentState, validate_transition, InvalidStateTransition
from agent.decision_engine import DecisionEngine, PurchaseIntent

class AutonomousBuyer:
    """The autonomous AI buyer agent."""

    def __init__(
        self,
        base_url: str = 'http://localhost:8000',
        poll_interval: int = 10,
        max_failures: int = 3
    ) -> None:
        """Initialize the autonomous buyer."""
        self.state = AgentState.IDLE
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.max_failures = max_failures
        self.consecutive_failures = 0
        self.decision_engine = DecisionEngine()
        self.cycle_count = 0
        self._shutdown_requested = False
        self.logger = logging.getLogger('AutonomousBuyer')
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    def _transition(self, target: AgentState) -> None:
        """Safely transition between states."""
        if not validate_transition(self.state, target):
            self.logger.error(f'Invalid state transition attempted: {self.state} -> {target}')
            raise InvalidStateTransition(self.state, target)
        self.logger.info(f'State transition: {self.state} -> {target}')
        self.state = target

    async def scan_catalog(self) -> list[dict[str, Any]]:
        """Fetch inventory from backend."""
        self._transition(AgentState.SCANNING)
        self.logger.info('Scanning catalog...')
        try:
            response = await self._client.get('/api/inventory')
            response.raise_for_status()
            data = response.json()
            products = data.get('products', [])
            self.logger.info(f'Found {len(products)} products in catalog.')
            return products
        except httpx.HTTPError as e:
            self.logger.error(f'Failed to scan catalog: {e}')
            raise

    async def evaluate(self, products: list[dict[str, Any]]) -> list[PurchaseIntent]:
        """Evaluate catalog and generate purchase intents."""
        self._transition(AgentState.EVALUATING)
        self.logger.info('Evaluating catalog...')
        intents = self.decision_engine.evaluate_catalog(products)
        
        for intent in intents:
            self.logger.info(f'Purchase intent: {intent.quantity}x {intent.sku} - {intent.reason}')
            
        if not intents:
            self.logger.info('No purchase intents generated.')
            self._transition(AgentState.IDLE)
            return []
            
        return intents

    async def purchase(self, intents: list[PurchaseIntent]) -> dict[str, Any]:
        """Execute purchases via the backend."""
        self._transition(AgentState.PURCHASING)
        
        items = [{'sku': intent.sku, 'quantity': intent.quantity} for intent in intents]
        reasons = '; '.join(set(intent.reason for intent in intents))
        
        payload = {
            'items': items,
            'trigger_reason': reasons
        }
        
        self.logger.info(f'Initiating purchase for {len(items)} items...')
        
        try:
            response = await self._client.post('/api/checkout', json=payload)
            
            if response.status_code == 200:
                self.logger.info('Purchase successful.')
                self._transition(AgentState.COMPLETED)
                self.consecutive_failures = 0
                return response.json()
            elif response.status_code == 422:
                self.logger.warning(f'Spending limit hit or validation error: {response.text}')
                self._transition(AgentState.FAILED)
                # DO NOT RETRY for 422, so we don't increment failures
            elif response.status_code == 502:
                self.logger.error('Transaction Failed - Razorpay Error')
                self._transition(AgentState.FAILED)
                self.consecutive_failures += 1
            else:
                self.logger.error(f'Purchase failed with status {response.status_code}: {response.text}')
                self._transition(AgentState.FAILED)
                self.consecutive_failures += 1
                
        except httpx.TimeoutException:
            self.logger.error('Transaction Failed - Timeout')
            self._transition(AgentState.FAILED)
            self.consecutive_failures += 1
        except Exception as e:
            self.logger.error(f'Transaction Failed - {type(e).__name__}: {e}')
            self._transition(AgentState.FAILED)
            self.consecutive_failures += 1

        if self.consecutive_failures >= self.max_failures:
            self.logger.error(f'Max consecutive failures ({self.max_failures}) reached. Initiating shutdown.')
            self._transition(AgentState.SHUTDOWN)

        return {}

    async def run_cycle(self) -> None:
        """Run a single scan-evaluate-purchase cycle."""
        self.logger.info(f'Starting cycle {self.cycle_count + 1}')
        try:
            products = await self.scan_catalog()
            intents = await self.evaluate(products)
            if intents:
                await self.purchase(intents)
            else:
                self.logger.info('No purchase triggers found')
        except Exception as e:
            self.logger.error(f'Error during cycle: {e}')
            if self.state != AgentState.SHUTDOWN:
                if validate_transition(self.state, AgentState.FAILED):
                    self._transition(AgentState.FAILED)
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_failures:
                        self.logger.error(
                            f'Max consecutive failures ({self.max_failures}) reached. Initiating shutdown.'
                        )
                        self._transition(AgentState.SHUTDOWN)
                elif validate_transition(self.state, AgentState.IDLE):
                    self._transition(AgentState.IDLE)
        finally:
            self.cycle_count += 1

    async def run(self, max_cycles: int | None = None) -> None:
        """Run the autonomous buyer loop."""
        self.logger.info('====================================')
        self.logger.info('  AUTONOMOUS BUYER AGENT STARTING')
        self.logger.info('====================================')
        self.logger.info(f'Base URL:      {self.base_url}')
        self.logger.info(f'Poll Interval: {self.poll_interval}s')
        self.logger.info(f'Max Failures:  {self.max_failures}')
        self.logger.info(f'Max Cycles:    {max_cycles if max_cycles else "Infinite"}')
        self.logger.info('====================================')

        try:
            while not self._shutdown_requested and (max_cycles is None or self.cycle_count < max_cycles):
                await self.run_cycle()
                
                if self.state == AgentState.SHUTDOWN:
                    break
                    
                if self.state in (AgentState.COMPLETED, AgentState.FAILED, AgentState.IDLE):
                    if validate_transition(self.state, AgentState.IDLE):
                        self._transition(AgentState.IDLE)
                        
                if not self._shutdown_requested and (max_cycles is None or self.cycle_count < max_cycles):
                    self.logger.info(f'Sleeping for {self.poll_interval} seconds...')
                    await asyncio.sleep(self.poll_interval)
                    
        finally:
            if self.state != AgentState.SHUTDOWN and validate_transition(self.state, AgentState.SHUTDOWN):
                self._transition(AgentState.SHUTDOWN)
            self.logger.info('====================================')
            self.logger.info('  AUTONOMOUS BUYER AGENT SHUTDOWN')
            self.logger.info('====================================')
            self.logger.info(f'Total Cycles: {self.cycle_count}')
            self.logger.info(f'Final State:  {self.state}')
            self.logger.info('====================================')
            await self._client.aclose()

    def request_shutdown(self) -> None:
        """Request the agent to shut down gracefully."""
        self.logger.info('Shutdown requested...')
        self._shutdown_requested = True
