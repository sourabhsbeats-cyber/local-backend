# store_admin/serializers/payment_serializers.py
from rest_framework import serializers
from store_admin.models.payment_models.payment_models import VendorPaymentLog, VendorPaymentLogItem
from store_admin.models.vendor_models import Vendor

# -------------------------
# Vendor Payment Log Serializer
# Supports Bank, Card, and Wallet payments
# -------------------------
class VendorPaymentLogSerializer(serializers.ModelSerializer):
    vendor_id = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.all(),
        source='vendor'
    )
    account_number = serializers.CharField(label="Bank Account Number")  # <-- Fixed label

    class Meta:
        model = VendorPaymentLog
        fields = [
            'payment_id',
            'vendor',
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
            'account_number',  # will now use label above
            'card_holder',
            'wallet_confirmation',
            'notes',
            'status',
            'created_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['total_paid', 'created_at', 'updated_at']

    # -------------------------
    # Custom Validation for Payment Modes
    # -------------------------
    def validate(self, data):
        payment_mode = data.get('payment_mode')

        if payment_mode == 'bank':
            required_fields = [
                'bank_name', 'account_number'
            ]
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
        queryset=VendorPaymentLog.objects.all(),
        source='payment'
    )

    class Meta:
        model = VendorPaymentLogItem
        fields = [
            'item_id',
            'payment',
            'payment_id',
            'invoice_id'
        ]