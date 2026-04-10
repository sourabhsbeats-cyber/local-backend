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

    name = models.CharField(max_length=100, unique=True)
    frequency = models.PositiveIntegerField(help_text="Enter number of days (e.g., 30 = Net 30)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    type = models.PositiveIntegerField(choices=PAYMENT_TYPES, default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.frequency})"

    def clean(self):
        errors = {}

        if not self.name or not str(self.name).strip():
            errors['name'] = "Name is required."

        try:
            frequency_value = int(self.frequency)
            if frequency_value <= 0:
                errors['frequency'] = "Frequency must be a positive integer."
            else:
                self.frequency = frequency_value
        except (TypeError, ValueError):
            errors['frequency'] = "Frequency must be a valid integer."

        try:
            type_value = int(self.type)
            if type_value not in dict(self.PAYMENT_TYPES):
                errors['type'] = "Invalid payment type."
            else:
                self.type = type_value
        except (TypeError, ValueError):
            errors['type'] = "Type must be a valid integer."

        if not self.status or str(self.status).strip() not in dict(self.STATUS_CHOICES):
            errors['status'] = "Status must be Active or Inactive."

        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'store_admin_payment_terms'
        verbose_name = 'Payment Term'
        verbose_name_plural = 'Payment Terms'
        ordering = ['frequency']

# -------------------------
# Pre-populated Payment Terms
# -------------------------
def create_default_payment_terms():
    terms = [
        {'name': 'Last date of next to next month (Forcetech)', 'frequency': 60, 'type': 2},  # Postpaid
        {'name': 'Last date of next month (Bambury)', 'frequency': 30, 'type': 2},           # Postpaid
        {'name': '14th of next month (Ingram)', 'frequency': 30, 'type': 2},                # Postpaid
    ]
    for term in terms:
        PaymentTerm.objects.get_or_create(name=term['name'], defaults=term)