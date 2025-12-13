from rest_framework import serializers
from store_admin.models.product_model import ProductImages

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImages
        fields = ["product_image_id", "product_id", "image_path", "cdn_url", "uploaded_at"]

