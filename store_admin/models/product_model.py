from django.db import models

from django.db import models


class Product(models.Model):
    product_id = models.AutoField(primary_key=True)

    # PRODUCT TYPE
    product_type = models.CharField(max_length=120, blank=True, null=True)
    parent_sku = models.CharField(max_length=120, blank=True, null=True)
    bundle_sku = models.CharField(max_length=120, blank=True, null=True)
    is_alias = models.BooleanField(default=False)

    # BASIC INFO
    sku = models.CharField(max_length=120, unique=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    short_description = models.TextField(blank=True, null=True)

    # IDENTIFIERS
    brand_id = models.PositiveIntegerField(default=0)
    manufacturer_id = models.PositiveIntegerField(default=0)
    ean = models.CharField(max_length=50, blank=True, null=True)
    upc = models.CharField(max_length=50, blank=True, null=True)
    isbn = models.CharField(max_length=50, blank=True, null=True)
    mpn = models.CharField(max_length=120, blank=True, null=True)
    country_origin_id = models.PositiveIntegerField(default=0)

    CONDITION_CHOICES = [
        ("new", "New"),
        ("used", "Used"),
        ("refurbished", "Refurbished"),
        ("open_box", "Open Box"),
    ]
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="new")

    # AMAZON IDENTIFIERS
    asin = models.CharField(max_length=50, blank=True, null=True)
    fnsku = models.CharField(max_length=50, blank=True, null=True)
    fba_sku = models.CharField(max_length=50, blank=True, null=True)
    is_fba = models.BooleanField(default=False)

    ISBN_TYPE_CHOICES = [
        ("standard", "Standard"),
        ("oversize", "Oversize"),
    ]
    isbn_type = models.CharField(max_length=20, choices=ISBN_TYPE_CHOICES, blank=True, null=True)

    BARCODE_TYPE_CHOICES = [
        ("manufacturer", "Manufacturer Barcode"),
        ("amazon_barcode", "Amazon Barcode"),
    ]
    barcode_label_type = models.CharField(max_length=20, choices=BARCODE_TYPE_CHOICES, blank=True, null=True)

    PREP_TYPE_CHOICES = [
        ("no_prep_needed", "No Prep Needed"),
        ("polybag", "Polybagging"),
        ("bubble_wrap", "Bubble Wrap"),
        ("labeling", "Labeling"),
    ]
    prep_type = models.CharField(max_length=20, choices=PREP_TYPE_CHOICES, default="no_prep_needed")

    # INVENTORY
    STOCK_STATUS_CHOICES = [
        (1, "In Stock"),
        (2, "Out of Stock"),
        (3, "Preorder"),
        (4, "Discontinued"),
    ]
    stock_status = models.PositiveSmallIntegerField(choices=STOCK_STATUS_CHOICES, default=1)

    STATUS_CHOICES = [
        (1, "Active"),
        (2, "Draft"),
        (3, "Discontinued"),
        (4, "Archived"),
    ]
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=1)

    PUBLISH_CHOICES = [
        (1, "Yes"),
        (0, "No"),
    ]
    publish_status = models.PositiveIntegerField(choices=PUBLISH_CHOICES, default=1)

    # OTHER
    warranty = models.IntegerField(blank=True, null=True)
    product_tags = models.TextField(blank=True, null=True)

    # SYSTEM
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.PositiveIntegerField(default=0)
    updated_by = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.sku} - {self.title}"


class ProductImage(models.Model):
    product_id = models.PositiveIntegerField()
    image = models.ImageField(upload_to="product_images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for product {self.product_id}"

