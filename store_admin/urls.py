from django.urls import path, include
from .views import dashboard_views, auth_views
from .views.settings.organization import organization_settings
from .views.settings.shipping_providers import manage_shipping_view
from .views.vendors import vendor_views, bulk_import_view
from .views.settings.countries import countries_view
from .views.settings.payment_terms import payment_terms
from .views.settings.users import user_management
from django.shortcuts import redirect
from .views.products import product_view, bulk_import_product_view
from .views.settings.product_settings import product_settings
from .views.settings.warehouse import warehouse_settings
from .views import app_api_view
from . import vendor_urls, product_urls
urlpatterns = [
    #path('', views.test, name='test'),
    #path('', lambda request: redirect('login')),
    path('', auth_views.test_view),
    path('api/login', auth_views.api_login),
    path('api/refresh/', auth_views.api_refresh_token),
    path('api/me/', auth_views.api_me),
    path('api/logout/', auth_views.api_logout, name='logout'),
    #path('app/dashboard/', dashboard_views.dashboard, name='dashboard'),
    # vendor management
    path("vendor/", include("store_admin.vendor_urls")),
    path("product/", include("store_admin.product_urls")),
    path("purchaseorder/", include("store_admin.purchase_order_urls")),
    #user menu item
    #path('api/getnavigation', auth_views.get_user_navigations, name='get_user_navigation'),

    #User management
    #UPDATED API
    path("api/users", user_management.list_users),
    path("api/users/create", user_management.create_user),
    path("api/users/reset-password/<int:user_id>", user_management.reset_user_password),
    path("api/users/update/<int:user_id>", user_management.update_user_details),

    path("api/roles", user_management.list_user_roles),
    path("api/roles/create", user_management.create_user_roles),
    path("api/roles/update/<int:role_id>", user_management.update_user_roles),
    path("api/roles/delete/<int:role_id>", user_management.delete_user_roles),

    path('product_api/api/categories', product_settings.all_product_categories, name=''),
    path('product_api/product_categories/create', product_settings.add_new_category, name=''),
    path('product_api/product_categories/delete/<int:category_id>', product_settings.delete_category, name=''),
    path('product_api/product_categories/update/<int:category_id>', product_settings.update_category, name=''),

    path('product_api/product_brands/all', product_settings.api_all_brands, name=''),
    path('product_api/api/brands', product_settings.api_manage_brands, name=''),
    path('product_api/api/brands/create', product_settings.api_create_brands, name=''),
    path('product_api/api/brands/update/<int:brand_id>', product_settings.update_brand, name=''),
    path('product_api/api/brands/delete/<int:brand_id>', product_settings.delete_brand, name=''),

    path('product_api/api/manufacturers', product_settings.list_manufacturers, name=''),
    path('product_api/product_manufacturers/all', product_settings.api_list_all_manufacturers, name=''),
    path('product_api/api/manufacturers/create', product_settings.create_manufacturer, name=''),
    path('product_api/api/manufacturers/update/<int:manufacturer_id>', product_settings.update_manufacturers, name=''),
    path('product_api/api/manufacturers/delete/<int:manufacturer_id>', product_settings.delete_manufacturers, name=''),
    #product/api/manufacturers/update/53

    #path('product/product_uom', product_settings.list_uoms),
    path('product_api/api/uom', product_settings.list_uoms),
    path('product_api/product_uom/update/<int:uom_id>', product_settings.update_uom),
    path('product_api/product_uom/create', product_settings.create_uom),
    path('product_api/product_uom/delete/<int:uom_id>', product_settings.delete_uom),
    path("product_api/api/attributes/listing", product_settings.list_attributes),
    path("product_api/api/attributes/create", product_settings.create_attribute),
    path("product_api/api/attributes/update/<int:attribute_id>", product_settings.update_attribute),
    path("product_api/api/attributes/delete/<int:attribute_id>", product_settings.delete_attribute),


    path("common/api/attributes/bulk_delete_attributes", product_settings.delete_product_attributes),

    path("api/shipping_providers/lists", app_api_view.api_all_shipping_providers), #master_data
    path("api/shipping-providers", manage_shipping_view.api_all_shipping_providers),
    path("api/shipping-providers/create", manage_shipping_view.add_new_shipping_providers),
    path("api/shipping-providers/update/<int:carrier_id>", manage_shipping_view.save_shipping_details),
    path("api/shipping-providers/delete/<int:carrier_id>", manage_shipping_view.delete_shipping_details),
    path("api/shipping-providers/toggle-status/<int:carrier_id>", manage_shipping_view.toggle_shipping_status),
    # EOF UPDATED API

    path("api/inventory-locations", warehouse_settings.all_inventory_locations),
    path("api/inventory-locations/create", warehouse_settings.add_new_inventory_locations),
    path("api/inventory-locations/update/<int:warehouse_id>", warehouse_settings.save_inventory_location),
    path("api/inventory-locations/delete/<int:warehouse_id>", warehouse_settings.delete_inventory_location),
    #api/inventory-locations

    path("api/payment-terms", payment_terms.get_all_payment_terms),
    path("api/payment-terms/update/<int:payment_term_id>", payment_terms.update_payment_terms),
    path("api/payment-terms/delete/<int:payment_term_id>", payment_terms.delete_payment_term),
    path("api/payment-terms/create", payment_terms.create_payment_term),

    path('api/countries', countries_view.api_all_listings),
    path("api/countries/<int:country_id>", countries_view.get_country_details),
    path("api/countries/update/<int:country_id>", countries_view.update_country_details),
    path("api/states/update/<int:state_id>", countries_view.update_state_details),
    path("api/states/delete/<int:state_id>", countries_view.delete_state_details),
    path("api/countries/<int:country_id>/states/create", countries_view.create_state_details),


    #master data calls
    path("api/countries/lists", countries_view.get_countries), #allcountres master data
    path("api/sb_warehouses/lists", warehouse_settings.all_sb_api_listing), # master data


    #path("settings/countries/<int:country_id>/states/", countries_view.state_list, name="state_list"),
    path("get-states/<int:country_id>/", countries_view.get_states, name="get_states"),

    path("common/list_states/", countries_view.get_states_by_country, name="get_states_by_country"),
    #path("common/list_countries/", countries_view.get_countries, name="get_countries"),
    path("api/vendor_api/lists", vendor_views.api_all_vendors), #master data
    path("api/vendor_details", vendor_views.get_vendor_details),
    path("api/payment_terms/lists", app_api_view.api_all_payment_terms, name="api_all_payment_terms"), #master data

    path("organizations/view", organization_settings.view_organization_details),
    path("organizations/update", organization_settings.update_organization),
    path("organizations/locations/detail/<int:loc_id>", organization_settings.get_location_detail,
         name="get_org_location_details"),
    path("organizations/locations/update/<int:loc_id>", organization_settings.update_location),
    path("organizations/locations/add/", organization_settings.save_location),
    path("organizations/locations/delete/<int:loc_id>", organization_settings.delete_location),





    #API Master data Json

]