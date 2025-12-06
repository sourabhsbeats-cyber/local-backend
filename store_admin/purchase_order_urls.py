from django.urls import path
from .views import dashboard_views, auth_views
from .views.vendors import vendor_views, bulk_import_view
from .views.settings.countries import countries_view
from .views.settings.payment_terms import payment_terms
from .views.settings.users import user_management
from django.shortcuts import redirect
from .views.purchase_orders import purchase_orders_view
from .views.settings.product_settings import product_settings


urlpatterns = [
    #path('download_sample/<str:file_type>/<str:file_format>', bulk_import_product_view.download_product_template, name='download_product_template'),
   # path("delete_bulk/", product_view.delete_product_bulk, name="delete_products_bulk"),
    #path("delete/<int:product_id>/", product_view.delete_product, name="delete_product_single"),
    path('create/', purchase_orders_view.create_order, name='create_order'),                 # no ID → create new draft PO
    path('create/<int:po_id>/', purchase_orders_view.create_order, name='create_order'),    # with ID → edit PO
    path('save', purchase_orders_view.save_po, name='save_po_order'),

    path('listing', purchase_orders_view.listing, name='po_listing'),
    #path('api/allproducts', product_view.products_json, name='all_products_json'),
]

