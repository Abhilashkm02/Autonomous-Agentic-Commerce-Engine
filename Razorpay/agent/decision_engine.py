"""Decision engine for the autonomous buyer agent."""

from dataclasses import dataclass
from typing import Any

@dataclass
class PurchaseIntent:
    sku: str
    quantity: int
    reason: str
    price_paise: int

class DecisionEngine:
    """Evaluates product catalog to make purchasing decisions."""

    def __init__(self) -> None:
        """Initialize the decision engine with empty price history."""
        self._price_history: dict[str, list[int]] = {}
        self.SPENDING_LIMIT = 500000  # 500000 paise = 5000 INR

    def evaluate_catalog(self, products: list[dict[str, Any]]) -> list[PurchaseIntent]:
        """
        Evaluate the catalog and generate purchase intents based on:
        1. Low stock triggers
        2. Price drop triggers
        Ensures total cost doesn't exceed spending limit.
        """
        intents: list[PurchaseIntent] = []

        for product in products:
            sku = product['sku']
            stock = product['stock']
            reorder_threshold = product['reorder_threshold']
            current_price = product['price_paise']

            # Update price history
            if sku not in self._price_history:
                self._price_history[sku] = []
            self._price_history[sku].append(current_price)

            # Trigger 1: Low stock
            if stock <= reorder_threshold:
                reorder_qty = max((reorder_threshold * 2) - stock, 1)
                intents.append(
                    PurchaseIntent(
                        sku=sku,
                        quantity=reorder_qty,
                        reason=f'Low stock: {stock}/{reorder_threshold}',
                        price_paise=current_price
                    )
                )

            # Trigger 2: Price drop
            history = self._price_history[sku]
            if len(history) >= 2:
                prev_price = history[-2]
                if current_price < prev_price:
                    pct_drop = ((prev_price - current_price) / prev_price) * 100
                    if pct_drop >= 10.0:
                        intents.append(
                            PurchaseIntent(
                                sku=sku,
                                quantity=1,
                                reason=f'Price drop: {prev_price} -> {current_price} paise (-{pct_drop:.1f}%)',
                                price_paise=current_price
                            )
                        )

        # Pre-check against spending limit
        return self._trim_intents_to_budget(intents)

    def _trim_intents_to_budget(self, intents: list[PurchaseIntent]) -> list[PurchaseIntent]:
        """Trim intents if total cost exceeds budget."""
        total_cost = sum(intent.price_paise * intent.quantity for intent in intents)
        
        if total_cost <= self.SPENDING_LIMIT:
            return intents
            
        # Priority: Keep low stock reorders over price drops.
        # We sort intents: price drops (quantity=1 usually but we check reason)
        # We will sort by 'Low stock' in reason (False is 0, True is 1)
        sorted_intents = sorted(
            intents,
            key=lambda x: (
                'Low stock' in x.reason,  # 0 for price drop, 1 for low stock
                x.price_paise * x.quantity # Then by total cost (highest cost first to remove)
            )
        )
        
        trimmed_intents = sorted_intents.copy()
        while total_cost > self.SPENDING_LIMIT and trimmed_intents:
            removed = trimmed_intents.pop(0) # Remove lowest priority
            total_cost -= removed.price_paise * removed.quantity
            
        return trimmed_intents

    def reset_history(self) -> None:
        """Clear price history."""
        self._price_history.clear()
