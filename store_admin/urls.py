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
    #path('', views.test, name='test'),
    path('', lambda request: redirect('login')),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),

    path('dashboard/', dashboard_views.dashboard, name='dashboard'),

    #User management
    path("users/", user_management.manage_users, name="manage_users"),
    path("roles/", user_management.manage_user_roles, name="manage_user_roles"),

    #vendor management
    path('vendors/', vendor_views.all_vendors, name='vendor_listing'),
    path('addvendor/', vendor_views.add_new_vendor, name='add_new_vendor'),
    path('editvendor/<int:vendor_id>', vendor_views.edit_vendor, name='edit_vendor'),
    path("vendor/contact/delete/<int:contact_id>/", vendor_views.delete_vendor_contact, name="delete_vendor_contact"),
    path("vendor/bank/delete/<int:bank_id>/", vendor_views.delete_vendor_bank, name="delete_vendor_contact"),
    path("vendor/delete/<int:vendor_id>/", vendor_views.delete_vendor, name="delete_vendor_contact"),
    path('savevendor/', vendor_views.save_vendor, name='save_vendor'),
    path('vendor/import_vendor/', bulk_import_view.import_vendor, name='import_vendor'),
    path('vendor/import_vendor/_linkfields', bulk_import_view.import_vendor_validate, name='import_vendor_stage_map'),
    path('vendor/download_sample/<str:file_type>/<str:file_format>/', bulk_import_view.download_vendor_template, name='download_vendor_template'),
    path('vendor/import_vendor/importpreview/', bulk_import_view.preview_import, name='preview_import'),
    path('vendor/import_vendor/importvendor_/', bulk_import_view.final_vendor_import, name='final_vendor_import'),
    path("vendor/delete_bulk/", vendor_views.delete_vendors_bulk, name="delete_vendors_bulk"),
    #eof vendor

    #Product Management
    path('addproduct/', product_view.add_new, name='add_new_product'),
    path('product/create/', product_view.add_new, name='create_new_product'),
    path('product/update/', product_view.save, name='update_product'),

    path('product/<int:product_id>/edit', product_view.edit_product, name='edit_product'),
    path('product/download_sample/<str:file_type>/<str:file_format>/',
         bulk_import_product_view.download_product_template,
         name='download_product_template'),
    path('allproducts/', product_view.listing, name='all_products'),

    path('product/import_product/', bulk_import_product_view.import_product,
         name='import_product'), #stage 1
    path('product/import_product/importpreview/', bulk_import_product_view.preview_import,
         name='preview_product_import'),
    path('product/import_product/_linkfields', bulk_import_product_view.import_product_validate,
         name='import_product_stage_map'),#stage 2
    path('product/import_product/importproduct_/', bulk_import_product_view.final_product_import,
         name='final_product_import'), #stage 3

    path("product/delete_bulk/", product_view.delete_product_bulk, name="delete_products_bulk"),
    path("product/delete/<int:product_id>/", product_view.delete_product, name="delete_vendor_contact"),
    #EOF products


    path('all_countries/', countries_view.all_listings, name='all_countries'),
    path("countries/<int:country_id>/edit/", countries_view.edit_country, name="edit_country"),
    path("countries/<int:country_id>/states/", countries_view.state_list, name="state_list"),
    path("get-states/<int:country_id>/", countries_view.get_states, name="get_states"),

    path('product_categories/', product_settings.manage_product_categories, name='manage_product_categories'),
    path('product_brands/', product_settings.manage_product_brands, name='manage_product_brands'),
    path('product_manufacturers/', product_settings.manage_product_manufacturers, name='manage_product_manufacturers'),

    path('payment_terms/', payment_terms.manage_payment_terms, name='payment_terms'),
    path('departments/', vendor_views.add_new_vendor, name='departments'),

    path("common/list_states/", countries_view.get_states_by_country, name="get_states_by_country"),
    path("common/list_countries/", countries_view.get_countries, name="get_countries"),
]