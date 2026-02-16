from django.urls import path
from .views import dashboard_views, auth_views
from .views.vendors import vendor_views, bulk_import_view
from .views.settings.countries import countries_view
from .views.settings.payment_terms import payment_terms
from .views.settings.users import user_management
from django.shortcuts import redirect
from .views.products import product_view, bulk_import_product_view, product_inventory_view, bulk_export_product_view
from .views.settings.product_settings import product_settings


urlpatterns = [
    # Product Management
    #path('addproduct/', product_view.add_new, name='add_new_product'),
    path('create', product_view.api_create_product),
    path('details/<int:product_id>/', product_view.get_product_details_api),
    path('update/<int:product_id>/', product_view.save, name='update_product'),


    path('save_new_product/', product_view.create_product, name='save_new_product'),

    path('download_sample/<str:file_type>/<str:file_format>', bulk_import_product_view.download_product_template, name='download_product_template'),

    path("delete/<int:product_id>/", product_view.delete_product, name="delete_product_single"),
    path('api/allproducts', product_view.products_json, name='all_products_json'),
    path('api/get_all_product_types', product_view.get_all_product_types),

    #bulk upload
    # stage 1 - Form
    path("delete_bulk/", product_view.delete_product_bulk, name="delete_products_bulk"),
    path('import_product', bulk_import_product_view.import_product, name='import_product'),
    # stage 2 import_vendor_file_upload
    path('import_product/uploadfile_and_validate', bulk_import_product_view.import_product_validate,
         name='import_product_file_upload'),
    #stage3
    path('import_product/importpreview/<str:cleaned_filename>/<str:dup_option>/<str:uploaded_filename>', bulk_import_product_view.preview_import, name='preview_product_import'),
    #stage4
    path('import_product/importvendor_/', bulk_import_product_view.final_product_import, name='final_product_import'),
    # EOF products

    #product custom attributes  add_dynamic_attribute
    path('attribute/add_dynamic_attribute', product_view.add_dynamic_attribute, name='add_dynamic_attribute'),
    path('attribute/list_dynamic_attributes', product_view.list_dynamic_attributes, name='list_dynamic_attributes'),
    path('productinventoryinventory/update_qty', product_inventory_view.update_product_warehouse,
         name='update_product_warehouse'),
    path('attribute/update_dynamic_attribute/', product_view.update_dynamic_attribute, name='update_dynamic_attribute'),
    path('attribute/remove_dynamic_attribute/', product_view.remove_dynamic_attribute, name='remove_dynamic_attribute'),
    # stage 3
    #EOF product custom attributes
    path('bulk_export_xls', bulk_export_product_view.export_products_xlsx, name="export_products_xlsx"),
    path("save-image", product_view.save_product_image, name="save_product_image"),
    path("<int:product_id>/images", product_view.list_product_images, name="product_image_list"),
    path("images/<int:product_image_id>/delete", product_view.delete_product_image, name="image_delete"),
    path("api/search-products/", product_view.api_product_search, name="api_product_search"),
]
'''
path('import_product/_linkfields/<str:cleaned_filename>/<str:dup_option>/<str:uploaded_filename>',
     bulk_import_product_view.link_fields, name='import_product_stage_map'),
 '''
