from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import models
from django.db.models import IntegerField


class POStatus(models.IntegerChoices):
    DRAFT = -1, "Draft"
    PARKED = 0, "Parked"
    PLACED = 1, "Placed"
    COSTED = 2, "Costed"
    RECEIPTED = 3, "Receipted"
    COMPLETED = 4, "Completed"

    PARTIALLY_DELIVERED = 5, "Partially Delivered"
    DELIVERED = 6, "Delivered"
    CLOSED = 7, "Closed"
    CANCELLED = 8, "Cancelled"

class POShippingStatus(models.IntegerChoices):
    PENDING = -1, "Pending"
    SHIPPED = 2, "Shipped"
    BACK_ORDER = 3, "Back Order"
    PARTIALLY_DELIVERED = 4, "Partially Delivered"
    ALL_RECEIVED = 6, "All stock received"
    DELIVERED = 5, "Delivered"

class POPaymentStatus(models.IntegerChoices):
    PAID = 1, "Paid"
    UNPAID = 2, "Unpaid"
    CANCELED = 3, "Cancelled"
    ON_HOLD = 4, "On Hold"

class POBillingStatus(models.IntegerChoices):
    CREATED = 0, "Created"
    NOT_BILLED = 1, "Not Billed"
    PARTIALLY_BILLED = 2, "Partially Billed"
    BILLED = 3, "Billed"

class LedgerEntryType(models.IntegerChoices):
    DEBIT = 1, "Debit"
    CREDIT = 2, "Credit"

po_status_list = [
    {"id": -1, "purchase_status": "Draft", "tracking_status": "Pending", "description": "Draft PO created by the team"},
    {"id": 0, "purchase_status": "Parked", "tracking_status": "Pending", "description": "Draft PO created by the team"},
    {"id": 1, "purchase_status": "Placed", "tracking_status": "Pending", "description": "PO sent to supplier; no dispatch yet"},
    {"id": 2, "purchase_status": "Placed", "tracking_status": "Shipped", "description": "PO sent; supplier has shipped goods"},
    {"id": 3, "purchase_status": "Placed", "tracking_status": "Back Order", "description": "PO sent; item is on back-order"},
    {"id": 4, "purchase_status": "Partially Delivered", "tracking_status": "Partially Delivered", "description": "Partial stock received"},
    {"id": 5, "purchase_status": "Delivered", "tracking_status": "Delivered", "description": "All stock received"},
    {"id": 6, "purchase_status": "Closed", "tracking_status": "Delivered", "description": "Fully locked and tracking must be Delivered"},
    {"id": 7, "purchase_status": "Cancelled", "tracking_status": "N/A", "description": "Cancelled PO"}
]
