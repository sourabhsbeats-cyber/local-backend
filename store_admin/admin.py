# store_admin/admin.py
from django.contrib import admin
from .models.vendor_models import Vendor
from .models.payment_terms_model import PaymentTerm
from .models.payment_models.payment_models import VendorPaymentLog, VendorPaymentLogItem

# -------------------------
# Vendor Admin
# -------------------------
class VendorAdmin(admin.ModelAdmin):
    list_display = ['vendor_company_name', 'vendor_name', 'payment_term']
    fields = ['vendor_company_name', 'vendor_name', 'payment_term']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "payment_term":
            try:
                # Filter for active payment terms (case-insensitive)
                kwargs['queryset'] = PaymentTerm.objects.filter(
                    status__iexact='active'
                ).order_by('name')
            except Exception:
                # Fallback if status field doesn't exist or query fails
                kwargs['queryset'] = PaymentTerm.objects.all().order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# -------------------------
# Vendor Payment Log Admin
# -------------------------
class VendorPaymentLogAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'vendor', 'payment_mode', 'amount_paid', 'currency', 'payment_date', 'status', 'created_by']
    list_filter = ['payment_mode', 'status', 'currency', 'payment_date']
    search_fields = ['vendor__vendor_name', 'vendor__vendor_company_name', 'reference_number']

# -------------------------
# Vendor Payment Log Item Admin
# -------------------------
class VendorPaymentLogItemAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'payment', 'invoice_id']
    search_fields = ['payment__payment_id', 'invoice_id']

# -------------------------
# Register models
# -------------------------
admin.site.register(Vendor, VendorAdmin)
admin.site.register(VendorPaymentLog, VendorPaymentLogAdmin)
admin.site.register(VendorPaymentLogItem, VendorPaymentLogItemAdmin)