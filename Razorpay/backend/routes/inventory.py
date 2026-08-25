from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from backend.database import get_db, get_all_products, get_product_by_sku
from backend.models import CatalogResponse, Product

router = APIRouter(prefix="/api")

@router.get("/inventory", response_model=CatalogResponse)
def get_inventory():
    """Returns the catalog of all products as sanitized JSON."""
    with get_db() as conn:
        products = get_all_products(conn)
        return CatalogResponse(
            products=products,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

@router.get("/inventory/{sku}", response_model=Product)
def get_inventory_item(sku: str):
    """Returns a single product by SKU."""
    with get_db() as conn:
        product = get_product_by_sku(conn, sku)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
