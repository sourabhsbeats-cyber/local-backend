from django.urls import path
from .views import dashboard_views, auth_views
from .views.vendors import vendor_views
from .views.settings.countries import countries_view
from .views.settings.payment_terms import payment_terms
from .views.settings.users import user_management
from django.shortcuts import redirect
from .views.products import product_view
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
    #eof vendor

    #Product Management
    path('addproduct/', product_view.add_new, name='add_new_product'),
    path('product/create/', product_view.add_new, name='create_new_product'),
    path('allproducts/', product_view.listing, name='all_products'),

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