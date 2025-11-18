from django.db import models

# Optional reference tables
class Brand(models.Model):
    brand_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)
    status = models.PositiveIntegerField(default=0)
    created_at = models.PositiveIntegerField(max_length=120)
    created_by = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_brand'  # ✅ use your actual SQL table
        managed = False

    def __str__(self):
        return self.name

class Manufacturer(models.Model):
    manufacturer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)
    status = models.PositiveIntegerField(default=0)
    created_at = models.PositiveIntegerField(max_length=120)
    created_by = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_manufacturer'  # ✅ use your actual SQL table
        managed = False

    def __str__(self):
        return self.name
