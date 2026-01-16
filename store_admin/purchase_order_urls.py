from django.urls import path
from .views.purchase_orders import (purchase_orders_view,
                                    purchase_recieve_view, po_bills_view, bulk_export_po_orders, bulk_import_po_orders)
from .views.payments import payments_view

urlpatterns = [
    #Render CREATE PO ORDER FORM
    path('create/', purchase_orders_view.create_order, name='create_order'),
    path('create/<int:po_id>/', purchase_orders_view.create_order, name='create_order'),
    path('view/<int:po_id>', purchase_orders_view.view_po_order, name='view_po_order'),    # with ID → edit PO
    path('approve_po_order/<int:po_id>', purchase_orders_view.approve_po_order, name='approve_po_order'),    # with ID → edit PO
    path('approve_and_create_receive/<int:po_id>', purchase_orders_view.approve_and_create_receive, name='approve_and_create_receive'),    # with ID → edit PO

    # bulk upload
    # stage 1 - Form - import_vendor_file_upload - show error
    path('import_po_orders', bulk_import_po_orders.import_purchase_order, name='import_po_orders'),
    # stage 2 - Preview import
    path('import_po_orders/uploadfile_and_validate', bulk_import_po_orders.import_po_validate,
         name='import_po_file_upload'),

    # stage3
    path('import_po_orders/importpreview/<str:cleaned_filename>/<str:dup_option>/<str:uploaded_filename>',
         bulk_import_po_orders.preview_import, name='preview_po_import'),

    # stage4 - - complete import
    path('import_po_orders/importvendor_/', bulk_import_po_orders.final_po_import,
         name='final_po_import'),
    path('download_po_sample/<str:file_type>/<str:file_format>', bulk_import_po_orders.download_po_template,
         name='download_po_template'),

    # EOF PO
    #EOF product custom attributes
    #path('bulk_export_xls', bulk_export_po_orders.export_products_xlsx, name="export_po_orders_xlsx"),
    #path('cancel_po_order/<int:po_id>', purchase_orders_view.cancel_po_order, name='cancel_po_order'),    # with ID → edit PO

    path('save', purchase_orders_view.save_po, name='save_po_order'),
    path('generatepdf', purchase_orders_view.generate_po_pdf, name='generate_po_order'),
    path('api/list_vendors_po', purchase_orders_view.get_vendors_po, name='api_get_vendors_po'),
    path('api/listitems', purchase_orders_view.list_po_line_items, name='list_po_line_items'),
    path('listing', purchase_orders_view.listing, name='po_listing'),
    path('export_po_orders', bulk_export_po_orders.export_po_orders_xlsx, name='export_po_orders'),
    #json listing - Table Listing
    path('api/allpurchases', purchase_orders_view.all_purchases, name='all_purchases_json'),
    path('api/allpurchasereceives', purchase_orders_view.all_purchase_receives, name='all_purchase_receives_json'),
    path('api/purchase-order/<int:po_id>/<int:product_id>/<int:receive_id>/invoices/', purchase_orders_view.all_po_invoices, name='all_purchase_receives_json1'),
    path('api/purchase-order/<int:po_id>/<int:product_id>/<int:receive_id>/shipments/', purchase_orders_view.all_po_shipments, name='all_po_shipments'),
    path('api/purchase-order/save_purchase_invoice/', purchase_orders_view.save_purchase_invoice, name='all_purchase_receives_json2'),
    path('api/purchase-order/save_item_shipping/', purchase_orders_view.save_shipping_details, name='save_item_shipping_details'),
    path('api/purchase-order/delete_shipment/', purchase_orders_view.delete_po_shipment, name='delete_po_shipment'),
    path("delete/<int:po_id>/", purchase_orders_view.delete_po, name="delete_po_single"),

    #api/purchase-order/313/invoices/
    #EOF Purchase Orders

    #purchase received
    path('poreceives/', purchase_recieve_view.listing, name='po_order_receives'),
    path('poreceives/view/<int:po_receive_id>', purchase_recieve_view.view_po_receive, name='view_po_receive_order'),
    path('poreceives/edit/<int:po_receive_id>', purchase_recieve_view.edit_po_receive, name='edit_po_receive_order'),
    #Add new - action - Save PO
    path('poreceives/save', purchase_recieve_view.save_po_order_receive, name='save_po_receive'),

    path('poreceives/create', purchase_recieve_view.create_po_order_receive, name='create_po_order_receive'),
    path('poreceives/delete/<int:po_receive_id>', purchase_recieve_view.delete_po_receive, name='delete_po_receive'),
    path('api/ps_receives/listlineitems/<int:po_receive_id>', po_bills_view.list_ps_receive_line_items, name='list_ps_receive_line_items'),

    path('poreceives/save_split_receive', purchase_recieve_view.save_po_receive, name='save_po_receive_split'),
    path('poreceives/save_split_receive_complete', purchase_recieve_view.save_po_receive_split_complete, name='save_po_receive_split_complete'),

    path('poreceives/save_po_receive_full', purchase_recieve_view.save_po_receive_full, name='save_po_receive_full'),

    #PO Bills
    path('bills/delete/<int:bill_id>', purchase_recieve_view.delete_po_bill, name='delete_po_bill'),
    path('bills/listing', po_bills_view.bills_listing, name='po_bills_listing'),
    #Table listing JSON
    path('api/bills/listing_json', po_bills_view.bills_listing_json, name='po_bills_listing_json'),
    path('bills/createnew', po_bills_view.create_po_bill, name='create_po_bill'),
    path('bills/savebill', po_bills_view.save_po_bill, name='save_po_bill'),
    path('api/list_vendors_ps_receives/<int:vendor_id>', po_bills_view.get_vendors_ps, name='api_get_vendors_ps_receives'),
    #path('api/list_ps_items', po_bills_view.list_po_line_items, name='list_ps_line_items'),
    path("bills/<int:bill_id>/view/", po_bills_view.view_po_bill,name="view_po_bill"),
    path('api/bills/listing_vendor_bills_json', po_bills_view.vendor_bills_listing_json, name='api_get_vendors_bills'),
    path('api/bills/listing_bill_line_items', po_bills_view.listing_bill_line_items, name='list_bill_line_items'),

    #PO payments
    path('payments/listing', payments_view.payments_listing, name='payments_listing'),
    path('payments/createnew', payments_view.create_new_bill, name='create_payment'),
    path('payments/capturepayment', payments_view.save_purchase_payment, name='save_purchase_payment'),
    path('payments/view/<int:payment_id>/', payments_view.view_purchase_payment, name='view_purchase_payment'),

    #Table listing JSON
    path('payments/list_payments_json', payments_view.all_purchase_payments, name='list_payments_json'),
    path('payments/delete/<int:payment_id>', purchase_recieve_view.delete_payment, name='delete_payment'),
]

