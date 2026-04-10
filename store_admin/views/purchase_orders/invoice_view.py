
from store_admin.helpers import getUserName, getCountryById, getStateById, \
    getPaymentTermName, safe_df
from store_admin.models.payment_models.payment_models import VendorPaymentLog, VendorPaymentLogItem, PaymentStatus
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from store_admin.models.po_models.po_models import (PurchaseOrder, PurchaseOrderItem,
                                                    PurchaseOrderInvoiceDetails,
                                                    PurchaseOrderVendorDetails)
from store_admin.models.po_models.po_receipt_model import PurchaseReceiptItem, PurchaseReceipt
from store_admin.models.product_model import Product
from store_admin.models.vendor_models import Vendor, VendorAddress
from django.http import JsonResponse
from django.db.models import OuterRef, Subquery, Q, Sum
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
import math

@api_view(["GET"])
def get_line_items(request, po_id):
    po = PurchaseOrder.objects.filter(po_id=po_id).first()
    if not po:
        return JsonResponse({"status": False, "message": "Purchase order not found."}, status=404)

    po_items = PurchaseOrderItem.objects.filter(po_id=po_id)

    data = []

    total_subtotal = Decimal(po.sub_total or 0)
    total_extra = Decimal(po.surcharge_total or 0) + Decimal(po.shipping_charge or 0)

    for item in po_items:

        item_subtotal = Decimal(item.subtotal or 0)

        #  Avoid division error
        if total_subtotal > 0:
            proportion = item_subtotal / total_subtotal
        else:
            proportion = Decimal(0)

        #  Distribute freight + surcharge
        extra_share = (total_extra * proportion).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        # Excl GST landed subtotal
        landed_excl_gst = item_subtotal + extra_share

        # Calculate GST (using item's tax percentage)
        tax_pct = Decimal(item.tax_percentage or 0)
        gst_amount = (landed_excl_gst * tax_pct / Decimal(100)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        #  Final landed total (Incl GST)
        landed_incl_gst = (landed_excl_gst + gst_amount).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        #  Per unit landed cost
        qty = Decimal(item.qty or 1)
        cost_per_unit = (landed_incl_gst / qty).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        product = Product.objects.filter(product_id=item.product_id).first()
        data.append({
            "product_id": item.product_id,
            "title":product.title if product else "",
            "sku":product.sku if product else "",
            "qty": item.qty,
            "delivery_date": item.delivery_date,
            "landed_cost_total_incl_gst": float(landed_incl_gst),
            "landed_cost_per_unit_incl_gst": float(cost_per_unit),
        })

    return JsonResponse({
        "data": data,
        "summary_total": float(po.summary_total),
        "sub_total": float(po.sub_total),
        "tax_total": float(po.tax_total),
        "surcharge_total": float(po.surcharge_total),
        "shipping_charge": float(po.shipping_charge),
    })

@api_view(["GET"])
def get_invoice_detail(request, invoice_id):
    try:
        # -------------------------------------------------
        # FETCH HEADER
        # -------------------------------------------------
        invoice = PurchaseOrderInvoiceDetails.objects.filter(
            po_invoice_id=invoice_id
        ).first()

        if not invoice:
            return JsonResponse({"status": False, "message": "Invoice not found"})

        po_detail = PurchaseOrder.objects.filter(
            po_id=invoice.po_id
        ).first()

        if not po_detail:
            return JsonResponse({"status": False, "message": "PO not found"})

        # BILLING ADDRESS
        # -------------------------------------------------
        billing_address = None

        po_vendor = Vendor.objects.filter(
            id=po_detail.vendor_id
        ).first()

        if po_vendor:
            vendor_address = VendorAddress.objects.filter(
                vendor_id=po_vendor.id,
                address_type="billing"
            ).first()

            if vendor_address:
                address_detail = Addresses.objects.filter(
                    id=vendor_address.address_id
                ).first()

                if address_detail:
                    billing_address = {
                        "delivery_name": address_detail.attention_name,
                        "address_line1": address_detail.street1,
                        "address_line2": address_detail.street2,
                        "country": getCountryById(address_detail.country),
                        "state": getStateById(address_detail.state),
                        "city": address_detail.city,
                        "zip": address_detail.zip,
                    }

        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------
        inv_data = {
            "invoice_number": invoice.invoice_number,
            "invoice_amount": invoice.invoice_total,
            "po_number": po_detail.po_number,
            "po_id": po_detail.po_id,

            #"order_date": invoice.order_date,
            "payment_status_id": invoice.payment_status_id,
            #"order_no": invoice.order_no,
            #"vendor_ref_no": invoice.vendor_ref_no,
            #"delivery_ref": invoice.delivery_ref,
            "invoice_date": invoice.invoice_date,
            "payment_term_id": invoice.payment_term_id,
            "payment_term_name": getPaymentTermName(invoice.payment_term_id),
            "due_date": invoice.due_date,
            #"paid_date": invoice.paid_date,
            "created_at": safe_df(invoice.created_at,'d M Y h:i A') ,
            "created_by": getUserName(invoice.created_by),

            "shipping": {
                "delivery_name": po_detail.delivery_name,
                "address_line1": po_detail.address_line1,
                "address_line2": po_detail.address_line2,
                "country_name": getCountryById(po_detail.country_id),
                "state_name": getStateById(po_detail.state),
                "city": po_detail.city,
                "zip": po_detail.post_code,
            },

            "billing": billing_address,
        }

        return JsonResponse({"status": True, "data": inv_data})

    except Exception as err:
        return JsonResponse(
            {"status": False, "error": str(err), "data": []},
            status=500
        )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_invoices(request):

    po_sub = PurchaseOrder.objects.filter(
        po_id=OuterRef("po_id")
    )

    payment_term_sub = PaymentTerm.objects.filter(
        id=OuterRef("payment_term_id")
    ).values("name")[:1]

    vendor_po_sub = PurchaseOrderVendorDetails.objects.filter(
        po_id=OuterRef("po_id"),
        is_primary=1
    )

    qs = PurchaseOrderInvoiceDetails.objects.annotate(
        sb_po_number=Subquery(po_sub.values("po_number")[:1]),
        vendor_name=Subquery(po_sub.values("vendor_name")[:1]),
        vendor_id=Subquery(po_sub.values("vendor_id")[:1]),
        vendor_code=Subquery(po_sub.values("vendor_code")[:1]),
        payment_term_name=Subquery(payment_term_sub),

        vendor_po_number=Subquery(vendor_po_sub.values("vendor_po_number")[:1]),
        vendor_po_order_number=Subquery(vendor_po_sub.values("order_number")[:1]),
        vendor_po_order_date=Subquery(vendor_po_sub.values("order_date")[:1]),
    )

    vendor_search = request.GET.get("vendor_search", "").strip()
    status_filter = request.GET.get("status")
    due_date_from = request.GET.get("due_date_from")
    due_date_to = request.GET.get("due_date_to")
    invoice_date_from = request.GET.get("invoice_date_from")
    invoice_date_to = request.GET.get("invoice_date_to")
    payment_term_id = request.GET.get("payment_term_id")

    if vendor_search:
        qs = qs.filter(
            Q(vendor_code__icontains=vendor_search) |
            Q(vendor_name__icontains=vendor_search) |
            Q(invoice_number__icontains=vendor_search) |
            Q(vendor_po_number__icontains=vendor_search) |
            Q(sb_po_number__icontains=vendor_search)
        )

    if status_filter:
        try:
            qs = qs.filter(payment_status_id=int(status_filter))
        except ValueError:
            pass

    if due_date_from and due_date_to:
        qs = qs.filter(due_date__range=[due_date_from, due_date_to])
    elif due_date_from:
        qs = qs.filter(due_date__gte=due_date_from)
    elif due_date_to:
        qs = qs.filter(due_date__lte=due_date_to)

    if invoice_date_from and invoice_date_to:
        qs = qs.filter(invoice_date__range=[invoice_date_from, invoice_date_to])
    elif invoice_date_from:
        qs = qs.filter(invoice_date__gte=invoice_date_from)
    elif invoice_date_to:
        qs = qs.filter(invoice_date__lte=invoice_date_to)

    if payment_term_id:
        qs = qs.filter(payment_term_id=payment_term_id)

    # =====================================
    # SUMMARY (COUNT + AMOUNT)
    # =====================================

    today = timezone.now().date()

    paid_qs = qs.filter(payment_status_id=1)
    paid_count = paid_qs.count()
    paid_total = paid_qs.aggregate(total=Sum("invoice_total"))["total"] or 0

    cancelled_qs = qs.filter(payment_status_id=3)
    cancelled_count = cancelled_qs.count()
    cancelled_total = cancelled_qs.aggregate(total=Sum("invoice_total"))["total"] or 0

    unpaid_qs = qs.exclude(payment_status_id__in=[1, 3])
    unpaid_count = unpaid_qs.count()
    unpaid_total = unpaid_qs.aggregate(total=Sum("invoice_total"))["total"] or 0

    overdue_qs = unpaid_qs.filter(
        due_date__isnull=False,
        due_date__lt=today
    )
    overdue_count = overdue_qs.count()
    overdue_total = overdue_qs.aggregate(total=Sum("invoice_total"))["total"] or 0

    pending_qs = unpaid_qs.filter(
        Q(due_date__isnull=True) | Q(due_date__gte=today)
    )
    pending_count = pending_qs.count()
    pending_total = pending_qs.aggregate(total=Sum("invoice_total"))["total"] or 0

    # =====================================
    # SORTING
    # =====================================

    sort_by = request.GET.get("sort_by")
    sort_dir = request.GET.get("sort_dir", "asc")

    allowed_sort_fields = {
        "invoice_number": "invoice_number",
        "sb_po_number": "sb_po_number",
        "vendor_name": "vendor_name",
    }

    if sort_by in allowed_sort_fields:
        field = allowed_sort_fields[sort_by]
        if sort_dir == "desc":
            field = f"-{field}"
        qs = qs.order_by(field)
    else:
        qs = qs.order_by("-created_at")

    # =====================================
    # PAGINATION
    # =====================================

    try:
        page = int(request.GET.get("page", 1))
        size = min(int(request.GET.get("size", 20)), 50)
    except (ValueError, TypeError):
        page, size = 1, 20

    total_records = qs.count()
    start = (page - 1) * size
    end = start + size

    data_list = list(qs[start:end].values(
        "po_invoice_id",
        "po_id",
        "sb_po_number",
        "vendor_name",
        "vendor_code",
        "invoice_number",
        "invoice_date",
        "invoice_total",
        "vendor_id",
        "due_date",
        "payment_term_id",
        "payment_term_name",
        "payment_status_id",

        "vendor_po_number",
        "vendor_po_order_number",
        "vendor_po_order_date",
    ))

    status_map = {
        1: "Paid",
        2: "Unpaid",
        3: "Cancelled",
        4: "On Hold"
    }

    for item in data_list:
        status_id = item.get("payment_status_id")
        item["status_display"] = status_map.get(status_id, "Unknown")
        item["invoice_amount"] = float(item.get("invoice_total") or 0)

    last_page = math.ceil(total_records / size) if total_records else 1

    total_count = qs.count()
    total_amount = qs.aggregate(total=Sum("invoice_total"))["total"] or 0

    return JsonResponse({
        "data": data_list,
        "last_page": last_page,
        "total": total_records,
        "summary": {
            "total": {
                "count": total_count,
                "amount": total_amount
            },
            "paid": {
                "count": paid_count,
                "amount": paid_total
            },
            "unpaid": {
                "count": unpaid_count,
                "amount": unpaid_total
            },
            "overdue": {
                "count": overdue_count,
                "amount": overdue_total
            },
            "pending": {
                "count": pending_count,
                "amount": pending_total
            },
            "cancelled": {
                "count": cancelled_count,
                "amount": cancelled_total
            }
        }
    })

@api_view(["GET"])
def all_pending_invoices(request):
    today = timezone.now().date()
    due_date_from = request.GET.get("due_date_from", "")
    due_date_to = request.GET.get("due_date_to", "")
    vendor_search = request.GET.get("vendor_search", "").strip()
    payment_term_id = request.GET.get("payment_term_id", "")
    pos = PurchaseOrder.objects.all()

    # Vendor / invoice filter
    if vendor_search:
        matching_vendor_ids = Vendor.objects.filter(
            Q(vendor_name__icontains=vendor_search) |
            Q(vendor_code__icontains=vendor_search)
        ).values_list("id", flat=True)

        invoice_po_ids = PurchaseOrderInvoiceDetails.objects.filter(
            invoice_number__icontains=vendor_search
        ).values_list("po_id", flat=True)

        pos = pos.filter(
            Q(vendor_id__in=matching_vendor_ids) |
            Q(po_id__in=invoice_po_ids)
        )

    if payment_term_id:
        pt_vendor_ids  = Vendor.objects.filter(
            payment_term=payment_term_id
        ).values_list("id", flat=True)
        # pos filter-ல use பண்ணு
        pos = pos.filter(vendor_id__in=pt_vendor_ids)

    po_ids = list(pos.values_list("po_id", flat=True))
    # Invoice filter
    inv_filters = {
        "po_id__in": po_ids,
        "payment_status_id": 2, # unpaid only
    }
    if due_date_from and due_date_to:
        inv_filters["due_date__range"] = (due_date_from, due_date_to)
    elif due_date_from:
        inv_filters["due_date__gte"] = due_date_from
    elif due_date_to:
        inv_filters["due_date__lte"] = due_date_to

    all_invoices = PurchaseOrderInvoiceDetails.objects.filter(**inv_filters)

    invoices_by_po = {}
    for inv in all_invoices:
        invoices_by_po.setdefault(inv.po_id, []).append(inv)

    invoice_ids = [inv.po_invoice_id for inv in all_invoices]
    all_receipts = PurchaseReceipt.objects.filter(po_invoice_id__in=invoice_ids)
    receipts_by_invoice = {}
    for r in all_receipts:
        receipts_by_invoice.setdefault(r.po_invoice_id, []).append(r)

    receipt_ids = [r.po_receipt_id for r in all_receipts]
    all_items = PurchaseReceiptItem.objects.filter(po_receipt_id__in=receipt_ids)
    items_by_receipt = {}
    for item in all_items:
        items_by_receipt.setdefault(item.po_receipt_id, []).append(item)

    product_ids = [item.product_id for item in all_items]
    products = {p.product_id: p for p in Product.objects.filter(product_id__in=product_ids)}

    po_item_keys = set()
    for item in all_items:
        po_item_keys.add(item.product_id)
    all_po_items_qs = PurchaseOrderItem.objects.filter(po_id__in=po_ids, product_id__in=product_ids)
    po_items_map = {}
    for pi in all_po_items_qs:
        po_items_map[(pi.po_id, pi.product_id)] = pi

    vendor_ids = list(set(po.vendor_id for po in pos))
    vendors_map = {v.id: v for v in Vendor.objects.filter(id__in=vendor_ids)}

    data = []
    for po in pos:
        invoices = invoices_by_po.get(po.po_id, [])
        if not invoices:
            continue

        vendor = vendors_map.get(po.vendor_id)
        if not vendor:
            continue

        inv_total = Decimal("0.0")
        invoice_list = []

        for invoice in invoices:
            inv_total += invoice.invoice_total
            receipt_products = []

            for receipt in receipts_by_invoice.get(invoice.po_invoice_id, []):
                for item in items_by_receipt.get(receipt.po_receipt_id, []):
                    product = products.get(item.product_id)
                    po_item = po_items_map.get((invoice.po_id, item.product_id))
                    if product and po_item:
                        receipt_products.append({
                            "product_name": product.title,
                            "received_qty": item.received_qty,
                            "landed_cost": po_item.landed_cost,
                            "cost_per_item": po_item.cost_per_item,
                            "price": po_item.price,
                            "line_total": po_item.line_total,
                        })
            po_number = None
            po_detail = PurchaseOrder.objects.filter(po_id=invoice.po_id).exists()
            if po_detail:
                po_number =  PurchaseOrder.objects.filter(po_id=invoice.po_id).first().po_number
            invoice_list.append({
                "po_invoice_id": invoice.po_invoice_id,
                "po_number": po_number,
                "invoice_number": invoice.invoice_number,
                "invoice_date": str(invoice.invoice_date),
                "invoice_due_date": str(invoice.due_date),
                "invoice_amount": round(float(invoice.invoice_total), 2),
                "invoice_payment_status": invoice.payment_status_id,
                "receipt_products": receipt_products,
            })
        raw_mpaytype = (vendor.mode_of_payment or "").strip()
        data.append({
            "po_id": po.po_id,
            "vendor_id": vendor.id,
            "vendor_name": vendor.vendor_name,
            "vendor_code": vendor.vendor_code,
            "vendor_type": vendor.vendor_model,
            "vendor_currency": vendor.currency,
            "mode_of_payment": [m.strip().replace("_", " ").title() for m in raw_mpaytype.split(",") if m.strip()] if raw_mpaytype else [],
            "inv_total": round(float(inv_total), 2),
            "payment_term_id": vendor.payment_term,
            "payment_term_name": getPaymentTermName(vendor.payment_term),
            "po_invoices": invoice_list,
        })

    overdue_invoices = PurchaseOrderInvoiceDetails.objects.filter(
        po_id__in=po_ids,
        payment_status_id=2,
        due_date__lt=today,  # strictly before today
    )
    summary = {
        "total_vendors": len(data),
        "total_due": {
            "amount": round(sum(d["inv_total"] for d in data), 2),
            "count": sum(len(d["po_invoices"]) for d in data),
        },
        "total_invoices": sum(len(d["po_invoices"]) for d in data),
        "overdue": {
            "count": len(overdue_invoices),
            "amount": round(float(
                overdue_invoices.aggregate(t=Sum("invoice_total"))["t"] or 0
            ), 2),
        },
    }
    return JsonResponse({"data": data, "summary": summary})


@api_view(["POST"])
def mark_invoices_paid(request):
    from django.db import transaction

    data        = request.data
    invoice_ids = data.get("invoice_ids", [])
    vendor_id   = data.get("vendor_id")
    invoice_amount = float(data.get("total", 0))
    surcharge = float(data.get("surcharge") or 0)
    conversion_charge = float(data.get("conversion_charge") or 0)
    total_paid = round(invoice_amount + surcharge + conversion_charge, 2)
    if not invoice_ids:
        return JsonResponse({"error": "No invoices"}, status=400)

    if not vendor_id:
        return JsonResponse({"error": "No vendor"}, status=400)

    try:
        with transaction.atomic():

            # Already paid check
            already_paid = PurchaseOrderInvoiceDetails.objects.filter(
                po_invoice_id__in=invoice_ids,
                payment_status_id=1
            ).count()

            if already_paid > 0:
                return JsonResponse({
                    "error": f"{already_paid} invoice(s) already paid. Please refresh."
                }, status=400)

            # Invoice status update
            updated = PurchaseOrderInvoiceDetails.objects.filter(
                po_invoice_id__in=invoice_ids
            ).update(payment_status_id=1)

            if updated == 0:
                return JsonResponse({"error": "No invoices updated"}, status=400)

            # Payment log — INITIATED
            log = VendorPaymentLog.objects.create(
                vendor_id=vendor_id,
                payment_mode=data.get("payment_mode", ""),
                amount_paid=invoice_amount,
                surcharge=surcharge,
                conversion_charge=conversion_charge,
                total_paid=total_paid,
                currency=data.get("currency", ""),
                payment_date=data.get("payment_date"),
                reference_number=data.get("reference_number", ""),
                bank_name=data.get("bank_name", ""),
                account_number=data.get("account_number", ""),
                card_holder=data.get("card_holder", ""),
                wallet_confirmation=data.get("wallet_confirmation", ""),
                notes=data.get("notes", ""),
                status=PaymentStatus.INITIATED,
                created_by=request.user.id if request.user.is_authenticated else None,
            )

            VendorPaymentLogItem.objects.bulk_create([
                VendorPaymentLogItem(payment_id=log.payment_id, invoice_id=inv_id)
                for inv_id in invoice_ids
            ])

            log.status = PaymentStatus.COMPLETED
            log.save()

        return JsonResponse({
            "success": True,
            "payment_id": log.payment_id,
            "total_paid": total_paid,
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
