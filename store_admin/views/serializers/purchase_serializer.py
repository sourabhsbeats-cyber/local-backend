from rest_framework import serializers

class PurchaseReceiveSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    po_number = serializers.CharField(max_length=50)
    po_receive_number = serializers.CharField(max_length=50)
    received_date = serializers.DateField()
    comments = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )