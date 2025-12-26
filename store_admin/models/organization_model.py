from django.db import models

# Optional reference tables
class Organization(models.Model):
    company_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='org_logos/', null=True, blank=True)

    # Official Contact Details
    contact_email = models.EmailField(null=True, blank=True)
    website_url = models.URLField(null=True, blank=True)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)

    # Physical Address
    country_id = models.IntegerField(null=True, blank=True)
    street_address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state_id = models.IntegerField(null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return self.company_name

    class Meta:
        managed = False  # 🔥 IMPORTANT
        db_table = 'store_admin_organization_settings'

class OrganizationLocation(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=255)
    parent_location_name = models.CharField(max_length=255, null=True, blank=True) # Stored as text

    # Address Fields as plain text
    attention = models.CharField(max_length=255, null=True, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country_name = models.CharField(max_length=255) # Plain text instead of FK
    state_name = models.CharField(max_length=255)   # Plain text instead of FK
    phone = models.CharField(max_length=50, null=True, blank=True)
    fax = models.CharField(max_length=50, null=True, blank=True)
    website_url = models.URLField(null=True, blank=True)

    class Meta:
        db_table = 'store_admin_organization_locations'