from rest_framework import serializers
from store_admin.models.vendor_models import Vendor
from store_admin.models.vendor_models import VendorStatus, PaymentTerms
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

class LineItemSerializer(serializers.Serializer):
    row_item = serializers.DictField(required=False)
    qty = serializers.FloatField(required=False, default=0)
    price = serializers.FloatField(required=False, default=0)
    discount = serializers.FloatField(required=False, default=0)
    tax = serializers.FloatField(required=False, default=0)
    subtotal = serializers.FloatField(required=False, default=0)
    taxAmount = serializers.FloatField(required=False, default=0)
    actual_total = serializers.FloatField(required=False, default=0)

class PurchaseOrderSerializer(serializers.Serializer):
    # Vendor Info
    vendor_code = serializers.CharField(max_length=50)
    vendor_name = serializers.CharField(max_length=120)
    vendor_company_name = serializers.CharField(max_length=120)  # Ensure it's included in creation
    currency_code = serializers.CharField(required=False, allow_blank=True, max_length=10)
    vendor_reference = serializers.CharField(required=False, allow_blank=True, max_length=200)

    invoice_date = serializers.DateField(required=False, allow_null=True)
    order_date = serializers.DateField(required=False, allow_null=True)
    delivery_date = serializers.DateField(required=False, allow_null=True)

    warehouse = serializers.CharField(required=False, allow_blank=True, max_length=100)
    payment_term_id = serializers.CharField(required=False, allow_blank=True, max_length=5)

    # Address Info
    delivery_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    address_line1 = serializers.CharField(required=False, allow_blank=True, max_length=255)
    address_line2 = serializers.CharField(required=False, allow_blank=True, max_length=255)
    suburb = serializers.CharField(required=False, allow_blank=True, max_length=100)
    state = serializers.CharField(required=False, allow_blank=True, max_length=100)
    post_code = serializers.CharField(required=False, allow_blank=True, max_length=20)
    country = serializers.CharField(required=False, allow_blank=True, max_length=100)

    # Financials
    tax_percentage = serializers.FloatField(required=False, default=0)

    # Bank / Company
    account_number = serializers.CharField(required=False, allow_blank=True, max_length=50, label="Bank Account Number")
    company_acc_no = serializers.CharField(required=False, allow_blank=True, max_length=50)
    company_abn = serializers.CharField(required=False, allow_blank=True, max_length=15)
    company_acn = serializers.CharField(required=False, allow_blank=True, max_length=15)

    # Line items
    lineItems = LineItemSerializer(many=True, required=False)

    def validate_payment_term_id(self, value):
        """Ensure the provided payment_term_id is valid."""
        if value and int(value) not in dict(PaymentTerms.choices):
            raise ValidationError("Invalid payment term ID.")
        return value

    def create(self, validated_data):
        line_items_data = validated_data.pop('lineItems', [])
        vendor_code = validated_data.get('vendor_code')

        # Check if vendor exists
        vendor = Vendor.objects.filter(vendor_code=vendor_code).first()

        payment_term_id = validated_data.get('payment_term_id')
        # Convert payment_term_id to integer and validate it
        if payment_term_id:
            try:
                payment_term_id = int(payment_term_id)
                if payment_term_id not in dict(PaymentTerms.choices):
                    payment_term_id = Vendor.payment_term.field.default
            except ValueError:
                payment_term_id = Vendor.payment_term.field.default
        else:
            payment_term_id = Vendor.payment_term.field.default

        try:
            if vendor:
                # Update existing vendor details
                vendor.vendor_name = validated_data.get('vendor_name', vendor.vendor_name)
                vendor.vendor_company_name = validated_data.get('vendor_company_name', vendor.vendor_company_name)
                vendor.company_acc_no = validated_data.get('company_acc_no', vendor.company_acc_no)
                vendor.account_number = validated_data.get('account_number', vendor.account_number)
                vendor.company_abn = validated_data.get('company_abn', vendor.company_abn)
                vendor.company_acn = validated_data.get('company_acn', vendor.company_acn)
                vendor.payment_term = payment_term_id
                vendor.save()
            else:
                # Create new vendor safely
                vendor = Vendor.objects.create(
                    vendor_code=vendor_code,
                    vendor_name=validated_data.get('vendor_name', ''),
                    vendor_company_name=validated_data.get('vendor_company_name', ''),
                    company_acc_no=validated_data.get('company_acc_no', ''),
                    account_number=validated_data.get('account_number', ''),
                    company_abn=validated_data.get('company_abn', ''),
                    company_acn=validated_data.get('company_acn', ''),
                    payment_term=payment_term_id
                )
        except IntegrityError as e:
            raise ValidationError({"vendor_code": "Vendor code already exists."})
        except Exception as e:
            raise ValidationError({"detail": str(e)})

        # Process line items (if any) here, e.g., save them in related models
        if line_items_data:
            # Save line items logic can go here (for example: create related models)

            pass  # Add line items processing logic as needed

        return vendor