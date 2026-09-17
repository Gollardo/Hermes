"""Module-owned persistence surface for Backup only."""

from app.modules.depreciation.calculation import inflation_target
from app.modules.depreciation.models import DepreciationPurchase, DepreciationReceipt
from app.modules.depreciation.schemas import PurchaseCreate

__all__ = ["DepreciationPurchase", "DepreciationReceipt", "PurchaseCreate", "inflation_target"]
