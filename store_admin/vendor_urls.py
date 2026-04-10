# store_admin/vendor_urls.py
from django.urls import path
from .views.vendors import (
    vendor_views,
    bulk_import_view,
    pre_import_vendor,
    confirm_import_vendor,
    vendor_payment_views  # Newly added for payments
)
from .views.vendors.vendor_views import get_vendor_details  # <- Add this line
urlpatterns = [

    path('vendor_details', get_vendor_details, name='vendor_details'),
    # -------------------------
    # Vendor Management
    # -------------------------
    path('vendors_list', vendor_views.all_vendors, name='vendors_list'),
    path('api/vendorsearch', vendor_views.api_vendor_search, name='api_vendor_search'),
    path('api/addvendor/', vendor_views.api_add_new_vendor, name='api_add_new_vendor'),
    # Add this line for the frontend
    path('vendor_api_lists', vendor_views.vendor_api_lists, name='vendor_api_lists'),
    path("api/delete/<int:vendor_id>", vendor_views.delete_vendor, name="delete_vendor"),
    path('api/save_vendor_details', vendor_views.api_save_vendor, name="save_vendor_details"),

    # -------------------------
    # Vendor Warehouse
    # -------------------------
    path('api/vendor_warehouse/get_all/<int:vendor_id>', vendor_views.api_vendor_warehouses, name="vendor_warehouses_get"),
    path('api/vendor_warehouse/addNew/<int:vendor_id>', vendor_views.WarehouseDetailManager.as_view(), name="vendor_warehouses_add"),
    path('api/vendor_warehouse/update/<int:warehouse_id>', vendor_views.WarehouseDetailManager.as_view(), name="vendor_warehouses_update"),
    path('api/vendor_warehouse/delete/<int:warehouse_id>/<int:vendor_id>', vendor_views.WarehouseDetailManager.as_view(), name="vendor_warehouses_delete"),

    # -------------------------
    # Vendor Import / Export
    # -------------------------
    path('api/pre-import-check', pre_import_vendor.pre_import_check, name='pre_import_check'),
    path('api/download-template', vendor_views.download_import_template, name='download_template'),
    path('api/export-vendors', vendor_views.download_export_vendors, name='export_vendors'),
    path('api/confirm-import/', confirm_import_vendor.confirm_import_vendor, name='confirm_import'),

    path('import_vendor/', bulk_import_view.import_vendor, name='import_vendor'),
    path('import_vendor/validate', bulk_import_view.import_vendor_validate, name='import_vendor_validate'),
    path('import_vendor/_linkfields/<str:cleaned_filename>/<str:dup_option>/<str:uploaded_filename>',
         bulk_import_view.link_fields, name='import_vendor_stage_map'),
    path('import_vendor/importpreview/', bulk_import_view.preview_import, name='import_preview'),
    path('import_vendor/importvendor_/', bulk_import_view.final_vendor_import, name='final_vendor_import'),

    path('download_sample/<str:file_type>/<str:file_format>/', bulk_import_view.download_vendor_template, name='download_vendor_template'),
    path("delete_bulk/", vendor_views.delete_vendors_bulk, name="delete_vendors_bulk"),

    # -------------------------
    # Vendor Documents
    # -------------------------
    path('api/delete-document/<int:file_id>/', vendor_views.delete_vendor_document, name="delete_vendor_document"),
    path('api/upload-document/', vendor_views.upload_vendor_files, name="upload_vendor_file"),

    # -------------------------
    # Vendor Contacts
    # -------------------------
    path("contact/delete/<int:contact_id>/<int:vendor_id>", vendor_views.delete_vendor_contact, name="delete_vendor_contact"),
    path("contact/addNew/<int:vendor_id>", vendor_views.add_newvendor_contact, name="add_newvendor_contact"),
    path("contact/getall/<int:vendor_id>", vendor_views.get_all_vendor_contacts, name="get_all_vendor_contacts"),
    path("contact/getsingle/<int:vendor_id>/<int:contact_id>", vendor_views.get_single_vendor_contact, name="get_single_vendor_contact"),
    path("contact/update/<int:contact_id>", vendor_views.update_vendor_contact, name="update_vendor_contact"),

    # -------------------------
    # Vendor Banks
    # -------------------------
    path("bank/getall/<int:vendor_id>", vendor_views.get_all_vendor_banks, name="get_all_vendor_banks"),
    path("bank/addNew/<int:vendor_id>", vendor_views.add_new_vendor_bank, name="add_new_vendor_bank"),
    path("bank/getsingle/<int:vendor_id>/<int:bank_id>", vendor_views.get_single_vendor_bank, name="get_single_vendor_bank"),
    path("bank/update/<int:bank_id>", vendor_views.update_vendor_bank, name="update_vendor_bank"),
    path("bank/delete/<int:bank_id>/<int:vendor_id>", vendor_views.delete_vendor_bank, name="delete_vendor_bank"),

    # -------------------------
    # Vendor Payments (New)
    # -------------------------
    path("<int:vendor_id>/payments/", vendor_payment_views.get_vendor_payments, name="get_vendor_payments"),
    path("payment/add/", vendor_payment_views.add_vendor_payment, name="add_vendor_payment"),
    path("payment/<int:payment_id>/update/", vendor_payment_views.update_vendor_payment, name="update_vendor_payment"),
    path("payment/<int:payment_id>/delete/", vendor_payment_views.delete_vendor_payment, name="delete_vendor_payment"),
    path("payment/item/add/", vendor_payment_views.add_vendor_payment_item, name="add_vendor_payment_item"),
]