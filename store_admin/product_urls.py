from django.urls import path
from .views import dashboard_views, auth_views
from .views.vendors import vendor_views, bulk_import_view
from .views.settings.countries import countries_view
from .views.settings.payment_terms import payment_terms
from .views.settings.users import user_management
from django.shortcuts import redirect
from .views.products import product_view, bulk_import_product_view
from .views.settings.product_settings import product_settings


urlpatterns = [
    # Product Management
    path('addproduct/', product_view.add_new, name='add_new_product'),
    path('create/', product_view.add_new, name='create_new_product'),
    path('save_new_product/', product_view.create_product, name='save_new_product'),
    path('update/', product_view.save, name='update_product'),
    path('<int:product_id>/edit', product_view.edit_product, name='edit_product'),
    path('download_sample/<str:file_type>/<str:file_format>/', bulk_import_product_view.download_product_template, name='download_product_template'),
    path("delete_bulk/", product_view.delete_product_bulk, name="delete_products_bulk"),
    path("delete/<int:product_id>/", product_view.delete_product, name="delete_vendor_contact"),
    path('allproducts/', product_view.listing, name='all_products'),
    path('import_product/', bulk_import_product_view.import_product, name='import_product'),  # stage 1
    path('import_product/_linkfields', bulk_import_product_view.import_product_validate, name='import_product_stage_map'),  # stage 2
    path('import_product/importproduct_/', bulk_import_product_view.final_product_import, name='final_product_import'),  # stage 3
    path('import_product/importpreview/', bulk_import_product_view.preview_import, name='preview_product_import'),
    # EOF products
]