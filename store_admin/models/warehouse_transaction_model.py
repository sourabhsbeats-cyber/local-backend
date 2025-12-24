from django.db import models

from django.db import models

class ProductWarehouse(models.Model):
    product_wh_id = models.AutoField(primary_key=True, db_column="product_wh_id")
    product_id = models.PositiveBigIntegerField(db_column="product_id")  # UNSIGNED INT
    warehouse_id = models.PositiveBigIntegerField(db_column="warehouse_id")  # UNSIGNED INT
    stock = models.PositiveIntegerField(default=0, db_column="stock")  # UNSIGNED INT
    stock_previous = models.PositiveIntegerField(default=0, db_column="stock_previous")
    created_by = models.IntegerField(null=True, blank=True, db_column="created_by")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, db_column="created_at")

    class Meta:
        db_table = "store_admin_product_warehouse"


class ProductWarehouseTransaction(models.Model):
    wh_txn_id = models.AutoField(primary_key=True, db_column="wh_txn_id")
    product_id = models.PositiveBigIntegerField(db_column="product_id")  # UNSIGNED INT
    warehouse_id = models.PositiveBigIntegerField(db_column="warehouse_id")  # UNSIGNED INT
    change_qty = models.IntegerField(db_column="change_qty")
    action = models.CharField(max_length=10, db_column="action")  # stores ADD, REMOVE, ADJUST
    stock_before = models.PositiveIntegerField(db_column="stock_before")
    stock_after = models.PositiveIntegerField(db_column="stock_after")
    reference_note = models.CharField(max_length=200, null=True, blank=True, db_column="reference_note")
    created_by = models.IntegerField(null=True, blank=True, db_column="created_by")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, db_column="created_at")

    class Meta:
        db_table = "store_admin_product_warehouse_transaction"
        indexes = [
            models.Index(fields=["product_id"], name="idx_wh_txn_product"),
            models.Index(fields=["warehouse_id"], name="idx_wh_txn_wh"),
        ]

