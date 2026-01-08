import json

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.http import JsonResponse

@api_view(['POST'])
@permission_classes([AllowAny]) # Idhu dhaan Anonymous access allow pannum
@csrf_exempt  # React API call-ukku CSRF bypass panna idhu venum
def api_login(request):
    if request.method == 'POST':
        try:
            # React
            data = json.loads(request.body)
            username = data.get("username")
            password = data.get("password")

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                # Success Response - JSON-ah anuppuvom
                return JsonResponse({
                    'status': 'success',
                    'message': f"Welcome back, {user.name}!",
                    'redirect_url': '/dashboard'
                }, status=200)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid username or password'
                }, status=401)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'message': 'Only POST method allowed'}, status=405)



# Create your views here.
def login_view(request):
    if request.user.is_authenticated:
        return redirect(reverse('dashboard'))

    if request.method == 'POST':
        username = request.POST.get("username")
        password = request.POST.get("password")
        # Get 'next' from POST or GET to ensure it persists through the form submission
        next_url = request.POST.get('next') or request.GET.get('next')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.name}!")

            # 2. HANDLE REDIRECT LOGIC
            if next_url:
                return redirect(next_url)
            return redirect(reverse('dashboard'))

        else:
            messages.error(request, "Invalid username or password")
            return render(request, 'sbadmin/pages/login.html', {'error': 'Invalid username or password'})

    return render(request, 'sbadmin/pages/login.html')

@login_required
def logout_view(request):
    for key in list(request.session.keys()):
        del request.session[key]
    logout(request)
    request.session.flush()
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')

from django.urls import reverse
@login_required
def get_user_navigations(request):
    menu_item = [
        {
            "label": "Dashboard",
            "icon": "fas fa-th",
            "match": "/app/",
            "url": reverse("dashboard"),
        },
        {
            "label": "Vendor",
            "icon": "fas fa-file",
            "match": "/vendor/",
            "url": reverse("vendor_listing"),
        },
        {
            "label": "Purchases",
            "icon": "fas fa-shopping-bag",
            "match": "/purchaseorder/",
            "children": [
                {
                    "label": "Purchase Order",
                    "url": reverse("po_listing"),
                    "match": "/purchaseorder/",
                },
                {
                    "label": "Purchase Receives",
                    "url": reverse("po_order_receives"),
                    "match": "/purchaseorder/poreceives/",
                },
                {
                    "label": "Bills",
                    "url": reverse("po_bills_listing"),
                    "match": "/purchaseorder/bill/",
                },
                {
                    "label": "Payments Made",
                    "url": reverse("payments_listing"),
                    "match": "/purchaseorder/payments/",
                },
            ],
        },
        {
            "label": "Product",
            "icon": "fas fa-shopping-bag",
            "match": "/product/",
            "children": [
                {"label": "All Products", "url": reverse("all_products")},
                {"label": "Brands", "url": reverse("manage_product_brands")},
                {"label": "Category", "url": reverse("manage_product_categories")},
                {"label": "Manufactures", "url": reverse("manage_product_manufacturers")},
                {"label": "Attributes", "url": reverse("manage_product_attributes")},
                {"label": "Unit Of Measurements", "url": reverse("manage_unit_of_measures")},
            ],
        },
        {
            "label": "Security",
            "icon": "fas fa-shield-alt",
            "match": "/auth/",
            "children": [
                {"label": "Users", "url": reverse("manage_users")},
                {"label": "Roles", "url": reverse("manage_user_roles")},
            ],
        },
        {
            "label": "Settings",
            "icon": "fas fa-cog",
            "match": "/settings/",
            "children": [
                {"label": "Country", "url": reverse("all_countries")},
                {"label": "Payment Terms", "url": reverse("payment_terms")},
                {"label": "Warehouse", "url": reverse("manage_warehouse_listings")},
                {"label": "Shipping Providers", "url": reverse("manage_shipping_providers_listing")},
            ],
        },


    ]
    return JsonResponse({"status": "success", "menus":menu_item })