from rest_framework import serializers
from store_admin.models.vendor_models import VendorContact

class VendorContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorContact
        fields = '__all__'