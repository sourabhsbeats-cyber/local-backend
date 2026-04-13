from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from store_admin.models.vendor_models import VendorContact
from store_admin.serializers.common_serializers import VendorContactSerializer


class VendorContactListView(APIView):
    def get(self, request):
        contacts = VendorContact.objects.all()
        serializer = VendorContactSerializer(contacts, many=True)
        return Response(serializer.data)


class VendorContactCreateView(APIView):
    def post(self, request):
        serializer = VendorContactSerializer(data=request.data, many=True)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Vendor contacts created"}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)