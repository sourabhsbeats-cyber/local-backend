from rest_framework import serializers

class LineItemSerializer(serializers.Serializer):
    row_item = serializers.DictField()
    qty = serializers.FloatField()
    price = serializers.FloatField()
    discount = serializers.FloatField()
    tax = serializers.FloatField()
    subtotal = serializers.FloatField()
    taxAmount = serializers.FloatField()
    actual_total = serializers.FloatField()


class PurchaseOrderSerializer(serializers.Serializer):
    vendor_code = serializers.CharField()
    vendor_name = serializers.CharField()
    currency_code = serializers.CharField()
    vendor_reference = serializers.CharField()
    invoice_date = serializers.DateField()
    warehouse = serializers.CharField()
    order_date = serializers.DateField()
    delivery_date = serializers.DateField()
    payment_term_id = serializers.CharField()
    delivery_name = serializers.CharField()
    address_line1 = serializers.CharField()
    address_line2 = serializers.CharField()
    suburb = serializers.CharField()
    state = serializers.CharField()
    post_code = serializers.CharField()
    country = serializers.CharField()
    tax_percentage = serializers.FloatField()

    # NESTED JSON LIST
    lineItems = LineItemSerializer(many=True)
