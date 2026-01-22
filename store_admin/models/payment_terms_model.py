from django.db import models
class PaymentTerm(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    PAYMENT_TYPES = [
        (1, 'Prepaid'),
        (2, 'Postpaid'),
    ]

    #id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    frequency = models.PositiveIntegerField(help_text="Enter number of days (e.g., 30 = Net 30)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    type = models.PositiveIntegerField( choices=PAYMENT_TYPES, default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.frequency})"

    class Meta:
        db_table = 'store_admin_payment_terms'  # ✅ use your actual SQL table
        verbose_name = 'Payment Term'
        verbose_name_plural = 'Payment Terms'
        ordering = ['frequency']
        #managed = False