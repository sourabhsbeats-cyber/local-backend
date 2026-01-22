from django.urls import path
from .views.purchase_orders import (
    purchase_orders_view,
    purchase_recieve_view,
    po_bills_view,
    bulk_export_po_orders,
    bulk_import_po_orders
)
from .views.payments import payments_view

urlpatterns = [
    # ==========================================
    # 1. CORE PURCHASE ORDERS (PO)
    # ==========================================
    path('listing', purchase_orders_view.listing, name='po_listing'),
    path('create/', purchase_orders_view.create_order, name='create_order'),
    path('create/<int:po_id>/', purchase_orders_view.create_order, name='create_order'),
    path('view/<int:po_id>', purchase_orders_view.view_po_order, name='view_po_order'),
    path('save', purchase_orders_view.save_po, name='save_po_order'),
    path('delete/<int:po_id>/', purchase_orders_view.delete_po, name="delete_po_single"),
    path('generatepdf', purchase_orders_view.generate_po_pdf, name='generate_po_order'),

    # PO Workflow Actions
    path('approve_po_order/<int:po_id>', purchase_orders_view.approve_po_order, name='approve_po_order'),
    path('approve_and_create_receive/<int:po_id>', purchase_orders_view.approve_and_create_receive,
         name='approve_and_create_receive'),

    # ==========================================
    # 2. BULK OPERATIONS (Import/Export)
    # ==========================================
    # Import Process
    path('import_po_orders', bulk_import_po_orders.import_purchase_order, name='import_po_orders'),
    path('import_po_orders/uploadfile_and_validate', bulk_import_po_orders.import_po_validate,
         name='import_po_file_upload'),
    path('import_po_orders/importpreview/<str:cleaned_filename>/<str:dup_option>/<str:uploaded_filename>',
         bulk_import_po_orders.preview_import, name='preview_po_import'),
    path('import_po_orders/importvendor_/', bulk_import_po_orders.final_po_import, name='final_po_import'),
    path('download_po_sample/<str:file_type>/<str:file_format>', bulk_import_po_orders.download_po_template,
         name='download_po_template'),

    # Export
    path('export_po_orders', bulk_export_po_orders.export_po_orders_xlsx, name='export_po_orders'),

    # ==========================================
    # 3. PURCHASE RECEIVING & IN-TRANSIT
    # ==========================================
    path('poreceives/', purchase_recieve_view.listing, name='po_order_receives'),
    path('poreceives/create', purchase_recieve_view.create_po_order_receive, name='create_po_order_receive'),
    path('poreceives/view/<int:po_receive_id>', purchase_recieve_view.view_po_receive, name='view_po_receive_order'),
    path('poreceives/edit/<int:po_receive_id>', purchase_recieve_view.edit_po_receive, name='edit_po_receive_order'),
    path('poreceives/save', purchase_recieve_view.save_po_order_receive, name='save_po_receive'),
    path('poreceives/place_po', purchase_recieve_view.place_po, name='place_po'),
    path('poreceives/delete/<int:po_receive_id>', purchase_recieve_view.delete_po_receive, name='delete_po_receive'),

    # Split Receiving
    path('poreceives/save_split_receive', purchase_recieve_view.save_po_receive, name='save_po_receive_split'),
    path('poreceives/save_split_receive_complete', purchase_recieve_view.save_po_receive_split_complete,
         name='save_po_receive_split_complete'),

    # Logistics / In-Transit
    path('intransit/listing', purchase_recieve_view.intransit_listing, name='po_intransit_listing'),
    path('po-tracking/lists', purchase_recieve_view.po_tracking_listing, name='po_tracking_lists'),

    # ==========================================
    # 4. BILLS (INVOICES)
    # ==========================================
    path('bills/listing', po_bills_view.bills_listing, name='po_bills_listing'),
    path('bills/createnew', po_bills_view.create_po_bill, name='create_po_bill'),
    path('bills/savebill', po_bills_view.save_po_bill, name='save_po_bill'),
    path('bills/<int:bill_id>/view/', po_bills_view.view_po_bill, name="view_po_bill"),
    path('bills/delete/<int:bill_id>', purchase_recieve_view.delete_po_bill, name='delete_po_bill'),

    # ==========================================
    # 5. PAYMENTS
    # ==========================================
    path('payments/listing', payments_view.payments_listing, name='payments_listing'),
    path('payments/createnew', payments_view.create_new_bill, name='create_payment'),
    path('payments/capturepayment', payments_view.save_purchase_payment, name='save_purchase_payment'),
    path('payments/view/<int:payment_id>/', payments_view.view_purchase_payment, name='view_purchase_payment'),
    path('payments/delete/<int:payment_id>', purchase_recieve_view.delete_payment, name='delete_payment'),

    # ==========================================
    # 6. API & JSON DATA ENDPOINTS
    # ==========================================
    # Masters / Lookups
    path('api/list_vendors_po', purchase_orders_view.get_vendors_po, name='api_get_vendors_po'),
    path('api/list_vendors_ps_receives/<int:vendor_id>', po_bills_view.get_vendors_ps,
         name='api_get_vendors_ps_receives'),

    # List Aggregators (JSON)
    path('api/allpurchases', purchase_orders_view.all_purchases, name='all_purchases_json'),
    path('api/allpurchasereceives', purchase_orders_view.all_purchase_receives, name='all_purchase_receives_json'),
    path('api/intransit/listing_json', purchase_recieve_view.intransit_po_listing_json,
         name='po_intransit_api_listing'),
    path('api/bills/listing_json', po_bills_view.po_invoice_listing_json, name='po_bills_listing_json'),
    path('api/bills/listing_vendor_bills_json', po_bills_view.vendor_bills_listing_json, name='api_get_vendors_bills'),
    path('payments/list_payments_json', payments_view.all_purchase_payments, name='list_payments_json'),

    # Line Items & Details
    path('api/listitems', purchase_orders_view.list_po_line_items, name='list_po_line_items'),
    path('api/ps_receives/listlineitems/<int:po_receive_id>', po_bills_view.list_ps_receive_line_items,
         name='list_ps_receive_line_items'),
    path('api/bills/listing_bill_line_items', po_bills_view.listing_bill_line_items, name='list_bill_line_items'),

    # Shipping & Tracking API
    path('api/purchase-order/<int:po_id>/get_shipping_rows', purchase_orders_view.get_shipping_rows,
         name='get_shipping_rows'),
    path('api/purchase-order/<int:po_id>/shipping/alltracking', purchase_recieve_view.get_shipping_details,
         name='all_shipping_details'),
    path('api/purchase-order/save_item_shipping/', purchase_orders_view.save_shipping_details,
         name='save_item_shipping_details'),
    path('api/purchase-order/delete_shipment/', purchase_orders_view.delete_po_shipment, name='delete_po_shipment'),
    path('api/purchase-order/<int:po_id>/<int:product_id>/<int:receive_id>/shipments/',
         purchase_orders_view.all_po_shipments, name='all_po_shipments'),

    # Invoice API
    path('api/purchase-order/<int:po_id>/get_invoice_rows', purchase_orders_view.get_invoice_rows,
         name='get_invoice_rows'),
    path('api/purchase-order/<int:po_id>/invoice/alltracking', purchase_recieve_view.get_po_invoice_details,
         name='all_invoice_details'),
    path('api/purchase-order/<int:po_id>/<int:product_id>/<int:receive_id>/invoices/',
         purchase_orders_view.all_po_invoices, name='all_purchase_receives_json1'),
    path('api/purchase-order/save_purchase_invoice/', purchase_orders_view.save_purchase_invoice,
         name='save_purchase_invoice'),
    path('api/purchase-order/delete_invoice/', purchase_orders_view.delete_invoice, name='delete_invoice'),
]