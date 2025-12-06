from sys import get_int_max_str_digits
from xmlrpc.client import Boolean
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.urls import reverse
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from store_admin.models.product_model import Product, ProductShippingDetails, ProductPriceDetails, \
    ProductStaticAttributes, ProductDynamicAttributes
from store_admin.models.setting_model import Category, Brand, Manufacturer, AttributeDefinition
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from django.db.models import Min
from django.db import IntegrityError
from django.db.models import Subquery, OuterRef, Value, CharField, When, Case
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from store_admin.models import Country, State
from store_admin.models.warehouse_setting_model import Warehouse

import json
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from store_admin.models.warehouse_transaction_model import ProductWarehouse, ProductWarehouseTransaction


#
#edit form save action
@login_required
def update_product_warehouse(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"})

    try:
        data = json.loads(request.body)
        items = data.get("items", [])
    except:
        return JsonResponse({"status": False, "message": "Invalid JSON"})

    if not items:
        return JsonResponse({"status": False, "message": "No records sent"})

    user_id = request.user.id

    try:
        with transaction.atomic():

            for it in items:
                pid = int(it.get("product_id"))
                wid = int(it.get("warehouse_id"))
                qty = int(it.get("change_qty", 0))

                wh = ProductWarehouse.objects.filter(
                    product_id=pid, warehouse_id=wid
                ).select_for_update().first()

                # ----- ENABLE (INSERT mapping) -----
                if qty > 0 and not wh:
                    ProductWarehouse.objects.create(
                        product_id=pid,
                        warehouse_id=wid,
                        stock=qty,
                        stock_previous=0,  # initial previous is 0
                        created_by=user_id,
                        created_at=timezone.now()
                    )
                    ProductWarehouseTransaction.objects.create(
                        product_id=pid,
                        warehouse_id=wid,
                        change_qty=qty,
                        stock_before=0,
                        stock_after=qty,
                        action="ADD",
                        reference_note="Warehouse enabled, initial stock added",
                        created_by=user_id,
                        created_at=timezone.now()
                    )

                # ----- UPDATE STOCK -----
                elif qty > 0 and wh:
                    before = wh.stock
                    after = qty  # new entered value (replace)

                    # If no real change, skip both update and stock_previous modification
                    if before == after:
                        continue  # → skip this iteration, nothing updated, nothing logged

                    # Only update when changed
                    wh.stock_previous = before
                    wh.stock = after
                    wh.save()

                    ProductWarehouseTransaction.objects.create(
                        product_id=pid,
                        warehouse_id=wid,
                        change_qty=qty,
                        stock_before=before,
                        stock_after=after,
                        action="ADD",
                        reference_note="Stock replaced",
                        created_by=user_id,
                        created_at=timezone.now()
                    )

                # ----- REMOVE mapping -----
                elif wh:
                    before = wh.stock
                    wh.delete()  # delete mapping row
                    ProductWarehouseTransaction.objects.create(
                        product_id=pid,
                        warehouse_id=wid,
                        change_qty=0,
                        stock_before=before,
                        stock_after=0,
                        action="REMOVE",
                        reference_note="Warehouse mapping removed",
                        created_by=user_id,
                        created_at=timezone.now()
                    )

        return JsonResponse({"status": True, "message": "Processed"})
    except Exception as ex:
        return JsonResponse({"status": False, "message": str(ex)})



