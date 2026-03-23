from django.urls import path
from .views.purchase_orders import (
    purchase_orders_view,
    purchase_recieve_view,
    export_po_orders,
    bulk_import_po_orders, invoice_view, shipments_view
)
from .views.payments import payments_view

urlpatterns = [
    # ==========================================
    # 1. CORE PURCHASE ORDERS (PO)
    # ==========================================
    path('listing', purchase_orders_view.listing, name='po_listing'),
    path('api/create', purchase_orders_view.create_po_api_order, name='create_po_api_order'),
    path('api/get_po_details/<int:po_id>', purchase_orders_view.get_po_details),
    path('api/save_po_details', purchase_orders_view.save_po_details),
    path('api/get_po_receive_details/<int:po_receive_id>', purchase_recieve_view.get_po_receive_details),


    path('view/<int:po_id>', purchase_orders_view.view_po_order, name='view_po_order'),
    path('save', purchase_orders_view.save_po, name='save_po_order'),
    path('delete/<int:po_id>/', purchase_orders_view.delete_po, name="delete_po_single"),
    path('generatepdf', purchase_orders_view.generate_po_pdf, name='generate_po_order'),

    path('api/export-po', export_po_orders.export_po_orders),
    path('api/download-template', purchase_orders_view.download_import_template),
    #path('export_po_orders', bulk_export_po_orders.export_po_orders_xlsx, name='export_po_orders'),

    # PO Workflow Actions
    path('approve_po_order/<int:po_id>', purchase_orders_view.approve_po_order, name='approve_po_order'),
    path('approve_and_create_receive/<int:po_id>', purchase_orders_view.approve_and_create_receive),
    path('api/get_po_receive_details', purchase_recieve_view.get_api_po_receive,
         name='get_api_po_receive_details'),
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

    # ==========================================
    # 3. PURCHASE RECEIVING & IN-TRANSIT
    # ==========================================
    path('poreceives/', purchase_recieve_view.listing, name='po_order_receives'),
   # path('poreceives/save', purchase_recieve_view.save_po_order_receive, name='save_po_receive'),
    path('poreceives/place_po', purchase_recieve_view.place_po, name='place_po'),
    #path('poreceives/delete/<int:po_receive_id>', purchase_recieve_view.delete_po_receive, name='delete_po_receive'),

    #po receipt
    #save_po_receipt


    # Logistics / In-Transit
    path('intransit/listing', purchase_recieve_view.intransit_listing, name='po_intransit_listing'),
    path('po-tracking/lists', purchase_recieve_view.po_tracking_listing, name='po_tracking_lists'),

    # ==========================================
    # 4. BILLS (INVOICES)
    # ==========================================
    #path('bills/delete/<int:bill_id>', purchase_recieve_view.delete_po_bill, name='delete_po_bill'),

    # ==========================================
    # 6. API & JSON DATA ENDPOINTS
    # ==========================================
    # Masters / Lookups
    path('api/list_vendors_po', purchase_orders_view.get_vendors_po, name='api_get_vendors_po'),
    path("api/kanbanlist/get-config-layout", purchase_orders_view.get_kanban_layout),
    path("api/kanbanlist/save-config-layout", purchase_orders_view.save_kanban_layout),
    # List Aggregators (JSON)
    path('api/allpurchases', purchase_orders_view.all_purchases),
    path('api/allpurchasereceives', purchase_orders_view.all_purchase_receives, name='all_purchase_receives_json'),
    path('api/update_po_status', purchase_orders_view.update_po_status),
    path('api/intransit/listing_json', purchase_recieve_view.intransit_po_listing_json,
         name='po_intransit_api_listing'),
    path('payments/list_payments_json', payments_view.all_purchase_payments, name='list_payments_json'),

    # Line Items & Details
    path('api/listitems', purchase_orders_view.list_po_line_items, name='list_po_line_items'),

    # Shipping & Tracking API
    path('api/purchase-order/get_shipping_rows/<int:po_id>', purchase_orders_view.get_shipping_rows),
    path('api/purchase-order/<int:po_id>/shipping/alltracking', purchase_recieve_view.get_shipping_details,
         name='all_shipping_details'),
    path('api/purchase-order/save_item_shipping', purchase_orders_view.save_shipping_details),
    path('api/purchase-order/delete_shipment/', purchase_orders_view.delete_po_shipment, name='delete_po_shipment'),
    path('api/purchase-order/<int:po_id>/<int:product_id>/<int:receive_id>/shipments/',
         purchase_orders_view.all_po_shipments, name='all_po_shipments'),

    # Invoice API
    path('api/purchase-order/get_invoice_rows/<int:po_id>', purchase_orders_view.get_invoice_rows,
         name='get_invoice_rows'),
    path('api/purchase-order/<int:po_id>/invoice/alltracking', purchase_recieve_view.get_po_invoice_details,
         name='all_invoice_details'),
    path('api/purchase-order/<int:po_id>/<int:product_id>/<int:receive_id>/invoices/',
         purchase_orders_view.all_po_invoices, name='all_purchase_receives_json1'),


    path('api/purchase-order/invoices/getpolineitems/<int:po_id>', invoice_view.get_line_items),
    path('api/purchase-order/invoices/details/view/<int:invoice_id>', invoice_view.get_invoice_detail),

    path('api/purchase-order/save_purchase_invoice', purchase_orders_view.save_purchase_invoice),
    path('api/purchase-order/save_purchase_invoice/<int:invoice_id>', purchase_orders_view.update_purchase_invoice),
    path('api/purchase-order/delete_invoice/<int:po_invoice_id>', purchase_orders_view.delete_invoice, name='delete_invoice'),

    path('api/purchase-order/shipments/listing', shipments_view.all_shipments),
    path('api/purchase-order/invoices/listing', invoice_view.all_invoices),
    path('api/purchase-order/invoices/pending_lists', invoice_view.all_pending_invoices),
    path('api/purchase-order/invoices/mark-paid', invoice_view.mark_invoices_paid),
    # Split Receiving
    #path("invoices/mark-paid", mark_invoices_paid),
    #save_complete_received
    path('api/purchase-order/get_all_receipts/<int:po_id>', purchase_recieve_view.get_all_receipts),
    path('poreceives/save_po_receipt', purchase_recieve_view.save_po_receipt),
    path('poreceives/save_complete_received', purchase_recieve_view.save_complete_received),
    path('poreceives/save_split_receive', purchase_recieve_view.save_split_receive),
    path('poreceives/save_receive_complete', purchase_recieve_view.save_po_receive_complete),

]