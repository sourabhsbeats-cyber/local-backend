from django.db import models

class Country(models.Model):
    id = models.PositiveIntegerField(primary_key=True)  # MEDIUMINT UNSIGNED
    name = models.CharField(max_length=100)
    iso3 = models.CharField(max_length=3, blank=True, null=True)
    iso2 = models.CharField(max_length=2, blank=True, null=True)
    currency = models.CharField(max_length=255, blank=True, null=True)
    currency_name = models.CharField(max_length=255, blank=True, null=True)
    currency_symbol = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False     # 🔥 IMPORTANT
        db_table = 'store_admin_countries'

    def __str__(self):
        return self.name


class State(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    country = models.ForeignKey(
        Country,
        on_delete=models.DO_NOTHING,
        db_column='country_id',
        related_name='states'
    )
    country_code = models.CharField(max_length=2)
    fips_code = models.CharField(max_length=255, null=True, blank=True)
    iso2 = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=191, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
       managed = False
       db_table = 'store_admin_states'

    def __str__(self):
        return self.name
