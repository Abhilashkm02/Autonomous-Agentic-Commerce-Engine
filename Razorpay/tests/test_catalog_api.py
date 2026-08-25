"""Tests for the catalog/inventory API endpoints."""

import pytest


class TestInventoryEndpoint:
    """Test suite for GET /api/inventory."""

    def test_inventory_returns_json(self, test_client):
        """Assert response Content-Type is application/json."""
        response = test_client.get("/api/inventory")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_inventory_schema(self, test_client):
        """Validate response matches CatalogResponse schema."""
        response = test_client.get("/api/inventory")
        data = response.json()

        # Must have required top-level keys
        assert "products" in data
        assert "timestamp" in data
        assert "agent_version" in data
        assert data["agent_version"] == "1.0"

    def test_inventory_contains_products(self, test_client):
        """Assert catalog contains at least 1 product with required fields."""
        response = test_client.get("/api/inventory")
        data = response.json()

        assert len(data["products"]) >= 1

        # Validate each product has the required fields
        required_fields = {"id", "sku", "name", "price_paise", "stock",
                           "reorder_threshold", "category"}
        for product in data["products"]:
            assert required_fields.issubset(product.keys()), \
                f"Product missing fields: {required_fields - set(product.keys())}"

    def test_inventory_product_count(self, test_client):
        """Assert catalog contains exactly 10 seeded products."""
        response = test_client.get("/api/inventory")
        data = response.json()
        assert len(data["products"]) == 10

    def test_inventory_prices_are_positive(self, test_client):
        """Assert all product prices are positive integers (in paise)."""
        response = test_client.get("/api/inventory")
        data = response.json()
        for product in data["products"]:
            assert isinstance(product["price_paise"], int)
            assert product["price_paise"] > 0


class TestSingleProductLookup:
    """Test suite for GET /api/inventory/{sku}."""

    def test_single_product_lookup(self, test_client):
        """Lookup a known SKU returns the correct product."""
        response = test_client.get("/api/inventory/SKU-ELEC-001")
        assert response.status_code == 200
        data = response.json()
        assert data["sku"] == "SKU-ELEC-001"
        assert data["name"] == "Wireless Mouse"
        assert data["price_paise"] == 59900

    def test_unknown_sku_returns_404(self, test_client):
        """Lookup a non-existent SKU returns 404."""
        response = test_client.get("/api/inventory/SKU-FAKE-999")
        assert response.status_code == 404


class TestRootEndpoint:
    """Test suite for GET /api."""

    def test_root_returns_service_info(self, test_client):
        """API root endpoint returns service metadata."""
        response = test_client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["service"] == "Autonomous Agentic Commerce Engine"
        assert "endpoints" in data

    def test_dashboard_serves_html(self, test_client):
        """Root / serves the frontend dashboard HTML."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
