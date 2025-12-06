from django.urls import path, include
from .views import dashboard_views, auth_views
from .views.vendors import vendor_views, bulk_import_view
from .views.settings.countries import countries_view
from .views.settings.payment_terms import payment_terms
from .views.settings.users import user_management
from django.shortcuts import redirect
from .views.products import product_view, bulk_import_product_view
from .views.settings.product_settings import product_settings
from .views.settings.warehouse import warehouse_settings
from . import vendor_urls, product_urls
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
    path("vendor/", include("store_admin.vendor_urls")),
    path("product/", include("store_admin.product_urls")),
    #eof vendor
    # purchase order management
    path("purchaseorder/", include("store_admin.purchase_order_urls")),
    # eof purchase order
    path('all_countries/', countries_view.all_listings, name='all_countries'),
    path("countries/<int:country_id>/edit/", countries_view.edit_country, name="edit_country"),
    path("countries/<int:country_id>/states/", countries_view.state_list, name="state_list"),
    path("get-states/<int:country_id>/", countries_view.get_states, name="get_states"),

    path('product_categories/', product_settings.manage_product_categories, name='manage_product_categories'),
    path('product_brands/', product_settings.manage_product_brands, name='manage_product_brands'),
    path('product_manufacturers/', product_settings.manage_product_manufacturers, name='manage_product_manufacturers'),
    path('product_uom', product_settings.manage_unit_of_measures, name='manage_unit_of_measures'),


    path('add_product_brand/', product_settings.add_new_brand, name='add_new_brand'),
    path('add_product_manufacturer/', product_settings.add_new_manufacturer, name='add_new_manufacturer'),

    path('payment_terms/', payment_terms.manage_payment_terms, name='payment_terms'),
    path('departments/', vendor_views.add_new_vendor, name='departments'),

    path("common/list_states/", countries_view.get_states_by_country, name="get_states_by_country"),
    path("common/list_countries/", countries_view.get_countries, name="get_countries"),
    #Custom attribute settings
    path("common/all_attributes", product_settings.manage_product_attributes, name="manage_product_attributes"),
    path("common/bulk_delete_attributes", product_settings.delete_product_attributes, name="delete_attributes_bulk"),

    path("warehouse/all_listing", warehouse_settings.all_listing,
         name="manage_warehouse_listings"),
    path("warehouse/bulk_delete_warehouse", warehouse_settings.delete_locations,
         name="delete_warehouse_listings"),
]