from django.db import models
from store_admin.models import State,Country


class Addresses(models.Model):
    id = models.AutoField(primary_key=True)
    attention_name = models.CharField(max_length=255, blank=True)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, db_column="country_id",
    )
    street1 = models.CharField(max_length=255, blank=True)
    street2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, db_column="state_id",
    )
    zip = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    created_by  = models.PositiveIntegerField(default=0)
    #class Meta:
     #   db_table = "addresses"
    class Meta:
        managed = False
