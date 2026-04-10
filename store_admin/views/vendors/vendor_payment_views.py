# store_admin/views/vendor_payment_views.py
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from store_admin.serializers.payment_serializers import VendorPaymentLogSerializer, VendorPaymentLogItemSerializer
from store_admin.models.payment_models.payment_models import VendorPaymentLog, VendorPaymentLogItem
from store_admin.models.vendor_models import Vendor
from store_admin.AuthHandler import StrictJWTCookieAuthentication
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction

# -------------------------
# Fetch all payments for a vendor
# -------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def get_vendor_payments(request, vendor_id):
    vendor = get_object_or_404(Vendor, pk=vendor_id)
    payments = VendorPaymentLog.objects.filter(vendor_id=vendor_id).order_by("-payment_date")
    serializer = VendorPaymentLogSerializer(payments, many=True)
    return Response({"status": True, "data": serializer.data})

# -------------------------
# Add a new payment
# -------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def add_vendor_payment(request):
    serializer = VendorPaymentLogSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(created_by=request.user.id)
        return Response({"status": True, "message": "Payment recorded successfully"})
    return Response({"status": False, "message": serializer.errors}, status=400)

# -------------------------
# Update a payment
# -------------------------
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def update_vendor_payment(request, payment_id):
    payment = get_object_or_404(VendorPaymentLog, pk=payment_id)
    serializer = VendorPaymentLogSerializer(payment, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({"status": True, "message": "Payment updated successfully"})
    return Response({"status": False, "message": serializer.errors}, status=400)

# -------------------------
# Delete a payment
# -------------------------
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def delete_vendor_payment(request, payment_id):
    payment = get_object_or_404(VendorPaymentLog, pk=payment_id)
    payment.delete()
    return Response({"status": True, "message": "Payment deleted successfully"})

# -------------------------
# Add payment items (linked to invoices)
# -------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def add_vendor_payment_item(request):
    serializer = VendorPaymentLogItemSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"status": True, "message": "Payment item recorded successfully"})
    return Response({"status": False, "message": serializer.errors}, status=400)