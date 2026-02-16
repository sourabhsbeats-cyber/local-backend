from django.db import models

class Warehouse(models.Model):
    warehouse_id = models.AutoField(primary_key=True, db_column="warehouse_id")
    warehouse_name = models.CharField(max_length=150, db_column="warehouse_name")
    location = models.CharField(max_length=200, null=True, blank=True, db_column="location")
    status = models.IntegerField(null=True, blank=True, db_column="status")

    '''
    CharField(
        max_length=10,
        choices=[
            ('ACTIVE', 'Active'), 1
            ('INACTIVE', 'Inactive'), 0
            ('ARCHIVED', 'Archived') -1
        ],
        default='ACTIVE',
        db_column="status"
    )'''

    is_default = models.PositiveIntegerField(default=0, db_column="is_default")
    created_by = models.IntegerField(null=True, blank=True, db_column="created_by")
    created_at = models.DateTimeField(auto_now=True, db_column="created_at")

    class Meta:
        db_table = "store_admin_warehouse"

