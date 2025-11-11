from django.urls import path
from . import views
from .views import vendor_views, dashboard_views, auth_views

urlpatterns = [
    #path('', views.test, name='test'),
    path('login/', auth_views.login_view, name='login'),
    path('dashboard/', dashboard_views.dashboard, name='dashboard'),
    path('newvendor/', vendor_views.add_new_vendor, name='add_new_vendor'),
    path('vendors/', vendor_views.all_vendors, name='vendor_listing'),
    path('addvendor/', vendor_views.add_new_vendor, name='add_new_vendor'),

    path('all_countries/', vendor_views.add_new_vendor, name='all_countries'),
    path('payment_terms/', vendor_views.add_new_vendor, name='payment_terms'),
    path('departments/', vendor_views.add_new_vendor, name='departments'),
    path('logout/', auth_views.logout_view, name='logout'),
]