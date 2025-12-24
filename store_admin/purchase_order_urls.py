from django.urls import path
from .views.purchase_orders import (purchase_orders_view,
                                    purchase_recieve_view, po_bills_view)
from .views.payments import payments_view

urlpatterns = [
    #Render CREATE PO ORDER FORM
    path('create/', purchase_orders_view.create_order, name='create_order'),
    path('create/<int:po_id>/', purchase_orders_view.create_order, name='create_order'),
    path('view/<int:po_id>', purchase_orders_view.view_po_order, name='view_po_order'),    # with ID → edit PO
    path('approve_po_order/<int:po_id>', purchase_orders_view.approve_po_order, name='approve_po_order'),    # with ID → edit PO
    #path('cancel_po_order/<int:po_id>', purchase_orders_view.cancel_po_order, name='cancel_po_order'),    # with ID → edit PO
    path('save', purchase_orders_view.save_po, name='save_po_order'),
    path('generatepdf', purchase_orders_view.generate_po_pdf, name='generate_po_order'),
    path('api/list_vendors_po', purchase_orders_view.get_vendors_po, name='api_get_vendors_po'),
    path('api/listitems', purchase_orders_view.list_po_line_items, name='list_po_line_items'),
    path('listing', purchase_orders_view.listing, name='po_listing'),
    #json listing - Table Listing
    path('api/allpurchases', purchase_orders_view.all_purchases, name='all_purchases_json'),
    path('api/allpurchasereceives', purchase_orders_view.all_purchase_receives, name='all_purchase_receives_json'),
    path("delete/<int:po_id>/", purchase_orders_view.delete_po, name="delete_po_single"),
    #EOF Purchase Orders

    #purchase received
    path('poreceives', purchase_recieve_view.listing, name='po_order_receives'),
    path('poreceives/view/<int:po_receive_id>', purchase_recieve_view.view_po_receive, name='view_po_receive_order'),
    #Add new - action - Save PO
    path('poreceives/save', purchase_recieve_view.save_po_order_receive, name='save_po_receive'),
    path('poreceives/create', purchase_recieve_view.create_po_order_receive, name='create_po_order_receive'),
    path('poreceives/delete/<int:po_receive_id>', purchase_recieve_view.delete_po_receive, name='delete_po_receive'),
    path('api/ps_receives/listlineitems/<int:po_receive_id>', po_bills_view.list_ps_receive_line_items, name='list_ps_receive_line_items'),

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

