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
    brand_id = models.PositiveIntegerField(default=0, null=True)
    manufacturer_id = models.PositiveIntegerField(default=0, null=True)
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
    status_condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default="new")

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

    preferred_vendor = models.IntegerField(blank=True, null=True)
    amazon_size = models.CharField(max_length=50)
    vendor_sku = models.CharField(max_length=50)
    sbau = models.CharField(max_length=50)

    # SYSTEM
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.PositiveIntegerField(default=0)
    updated_by = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.sku} - {self.title}"


class ProductImage(models.Model):
    product_id = models.PositiveIntegerField()
    #image = models.ImageField(upload_to="product_images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for product {self.product_id}"



class ProductShippingDetails(models.Model):
    shipping_details_id = models.AutoField(primary_key=True)
    product_id = models.IntegerField(null=True, blank=True)
    fast_dispatch = models.IntegerField(null=True, blank=True)
    free_shipping = models.IntegerField(null=True, blank=True)
    bulky_product = models.CharField(max_length=45, null=True, blank=True)
    international_note = models.CharField(max_length=120, null=True, blank=True)
    example_reference = models.CharField(max_length=50, null=True, blank=True)
    ships_from = models.CharField(max_length=50, null=True, blank=True)
    handling_time_days = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'store_admin_product_shipping_details'


class ProductPriceDetails(models.Model):
    # price_id is the auto-created primary key
    product_id = models.IntegerField(null=True, blank=True)
    price_id = models.AutoField(primary_key=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_per_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    margin_percent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    profit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.IntegerField(null=True)

    class Meta:
        db_table = 'store_admin_product_price_details'



