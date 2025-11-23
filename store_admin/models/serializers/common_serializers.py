
from store_admin.models.vendor_models import VendorContact, VendorBank
from rest_framework import serializers

class VendorContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorContact
        fields = ['department', 'vendor_id',
                  'email', 'id',
                  'phone',
                  'first_name',
                  'last_name',
                  'role',
                  'description',]

class VendorBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBank
        # Include all fields for simple read/write operations
        fields = '__all__'
