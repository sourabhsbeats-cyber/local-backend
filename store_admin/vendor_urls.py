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
    #vendor management
    path('vendors/', vendor_views.all_vendors, name='vendor_listing'),
    path('api/getsingle_vendor/<int:vendor_id>', vendor_views.api_get_vendor_by_id, name='get_single_vendor'),
    path('api/vendorsearch', vendor_views.api_vendor_search, name='api_vendor_search'),
   
    path('addvendor/', vendor_views.add_new_vendor, name='add_new_vendor'),
    path('editvendor/<int:vendor_id>', vendor_views.edit_vendor, name='edit_vendor'),
    path("delete/<int:vendor_id>/", vendor_views.delete_vendor, name="delete_vendor_contact"),
    path('savevendor/', vendor_views.save_vendor, name='save_vendor'),
    #stage 1
    path('import_vendor/', bulk_import_view.import_vendor, name='import_vendor'),
    #stage2
    path('import_vendor/validate',bulk_import_view.import_vendor_validate, name='import_vendor_file_upload'),
    #stage3
    path('import_vendor/_linkfields/<str:cleaned_filename>/<str:dup_option>/<str:uploaded_filename>',
         bulk_import_view.link_fields, name='import_vendor_stage_map'),

    path('download_sample/<str:file_type>/<str:file_format>/', bulk_import_view.download_vendor_template, name='download_vendor_template'),
    path('import_vendor/importpreview/', bulk_import_view.preview_import, name='preview_import'),
    path('import_vendor/importvendor_/', bulk_import_view.final_vendor_import, name='final_vendor_import'),
    path("delete_bulk/", vendor_views.delete_vendors_bulk, name="delete_vendors_bulk"),

    path("contact/delete/<int:contact_id>/<int:vendor_id>", vendor_views.delete_vendor_contact, name="delete_vendor_contact"),
    path("contact/addNew/<int:vendor_id>/", vendor_views.add_newvendor_contact, name="add_newvendor_contact"),
    path("contact/getall/<int:vendor_id>/", vendor_views.get_all_vendor_contacts, name="get_all_vendor_contacts"),
    path("contact/getsingle/<int:vendor_id>/<int:contact_id>/", vendor_views.get_single_vendor_contact, name="get_single_vendor_contact"),
    path("contact/update/<int:contact_id>/", vendor_views.update_vendor_contact, name="update_newvendor_contact"),

    path("bank/getall/<int:vendor_id>/", vendor_views.get_all_vendor_banks, name="get_all_vendor_banks"),
    path("bank/addNew/<int:vendor_id>/", vendor_views.add_new_vendor_bank, name="add_new_vendor_bank"),
    path("bank/getsingle/<int:vendor_id>/<int:bank_id>/", vendor_views.get_single_vendor_bank,name="get_single_vendor_bank"),
    path("bank/update/<int:bank_id>/", vendor_views.update_vendor_bank, name="update_vendor_bank"),
    path("bank/delete/<int:bank_id>/<int:vendor_id>", vendor_views.delete_vendor_bank, name="delete_vendor_contact"),
    #eof vendor
]