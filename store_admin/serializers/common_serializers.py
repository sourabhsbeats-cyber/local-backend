# store_admin/serializers/common_serializers.py
from rest_framework import serializers
from store_admin.models.vendor_models import Vendor, VendorContact, VendorBank
from store_admin.models.payment_models.payment_models import VendorPaymentLog, VendorPaymentLogItem
from store_admin.models.payment_terms_model import PaymentTerm
# -------------------------
# Vendor Serializer
# -------------------------
class VendorSerializer(serializers.ModelSerializer):
    # Link to payment terms
    payment_term = serializers.PrimaryKeyRelatedField(
        queryset=PaymentTerm.objects.all(),
        required=False,
        allow_null=True
    )
    # Human-readable name for API responses
    payment_term_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vendor
        fields = [
            'id',
            'vendor_name',
            'vendor_code',
            'tax_id',
            'email',
            'phone',
            'address',
            'city',
            'state',
            'country',
            'zipcode',
            'status',
            'payment_term',       # New field
            'payment_term_name',  # Human-readable
            'created_by',
            'created_at',
            'updated_at'
        ]
        extra_kwargs = {
            'vendor_name': {'required': True},
            'tax_id': {'required': True},
            'email': {'required': True},
        }

    def get_payment_term_name(self, obj):
        if obj.payment_term:
            return obj.payment_term.name
        return None

    def create(self, validated_data):
        vendor_code = validated_data.get('vendor_code')
        tax_id = validated_data.get('tax_id')

        existing_vendor = Vendor.objects.filter(vendor_code=vendor_code).first() or \
                          Vendor.objects.filter(tax_id=tax_id).first()
        if existing_vendor:
            for key, value in validated_data.items():
                setattr(existing_vendor, key, value)
            existing_vendor.save()
            return existing_vendor
        return super().create(validated_data)

# -------------------------
# Vendor Contact Serializer
# -------------------------
class VendorContactSerializer(serializers.ModelSerializer):
    vendor_id = serializers.PrimaryKeyRelatedField(
        source='vendor',
        queryset=Vendor.objects.all()
    )

    class Meta:
        model = VendorContact
        fields = [
            'id',
            'vendor_id',
            'department',
            'email',
            'phone',
            'first_name',
            'last_name',
            'role',
            'description'
        ]

# -------------------------
# Vendor Bank Serializer
# -------------------------
class VendorBankSerializer(serializers.ModelSerializer):
    vendor_id = serializers.PrimaryKeyRelatedField(
        source='vendor',
        queryset=Vendor.objects.all()
    )

    class Meta:
        model = VendorBank
        fields = [
            'id',
            'vendor_id',
            'account_holder',
            'bank_name',
            'account_number',
            'bic',
            'bank_branch',
            'bank_country',
            'created_by',
            'created_at'
        ]
        extra_kwargs = {
            'account_number': {'required': False, 'allow_blank': True}
        }

# -------------------------
# Vendor Payment Log Serializer
# Supports Bank, Card, and Wallet payments
# -------------------------
class VendorPaymentLogSerializer(serializers.ModelSerializer):
    vendor_id = serializers.PrimaryKeyRelatedField(
        source='vendor',
        queryset=Vendor.objects.all()
    )
    account_number = serializers.CharField(label="Bank Account Number")

    class Meta:
        model = VendorPaymentLog
        fields = [
            'payment_id',
            'vendor_id',
            'payment_mode',  # bank, card, wallet
            'amount_paid',
            'surcharge',
            'conversion_charge',
            'total_paid',
            'currency',
            'payment_date',
            'reference_number',
            'bank_name',
            'account_number',
            'card_holder',
            'wallet_confirmation',
            'notes',
            'status',
            'created_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['total_paid', 'created_at', 'updated_at']

    def validate(self, data):
        payment_mode = data.get('payment_mode')
        if payment_mode == 'bank':
            required_fields = ['bank_name', 'account_number']
            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                raise serializers.ValidationError(
                    f"Missing required bank fields: {', '.join(missing)}"
                )
        elif payment_mode == 'card':
            required_fields = ['card_holder']
            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                raise serializers.ValidationError(
                    f"Missing required card fields: {', '.join(missing)}"
                )
        elif payment_mode == 'wallet':
            if not data.get('wallet_confirmation'):
                raise serializers.ValidationError(
                    "Wallet confirmation is required for wallet payments."
                )
        return data

# -------------------------
# Vendor Payment Log Item Serializer
# Links payment to invoices
# -------------------------
class VendorPaymentLogItemSerializer(serializers.ModelSerializer):
    payment_id = serializers.PrimaryKeyRelatedField(
        source='payment',
        queryset=VendorPaymentLog.objects.all()
    )

    class Meta:
        model = VendorPaymentLogItem
        fields = [
            'item_id',
            'payment_id',
            'invoice_id'
        ]