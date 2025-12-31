from django.contrib.admindocs.utils import ROLES
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from store_admin.auth_backend import User
from store_admin.models import Country, State
from store_admin.models.organization_model import Organization, OrganizationInventoryLocation
from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

from store_admin.models.product_model import ProductStaticAttributes
from store_admin.models.setting_model import Manufacturer, Brand, Category, AttributeDefinition
from store_admin.models.warehouse_setting_model import Warehouse
from django.db import transaction

@login_required
def view_organization_details(request):
    countries = Country.objects.all()
    users_cnt = User.objects.filter(is_active=True).count()
    roles_cnt = Group.objects.count()
    organization_detail = Organization.objects.first()
    org_locations = OrganizationInventoryLocation.objects.filter(organization=organization_detail)
    states_list = []
    if organization_detail.country_id is not None:
        states_list = State.objects.filter(country_id=int(organization_detail.country_id)).values('id', 'name')
    context = {
        "org":organization_detail,
        "countries":countries,
        "org_locations":org_locations,
        "states_list":states_list,
        "roles_cnt":roles_cnt,
        "users_cnt":users_cnt,
    }
    return render(request,
                  "sbadmin/pages/settings/organization/view_organization_details.html",
                  context)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_organization(request):
    try:
        # Get the first record or create a new one (Singleton Pattern)
        org, created = Organization.objects.get_or_create(id=1)
        # Map text fields from request.POST
        org.company_name = request.POST.get('company_name')
        org.contact_email = request.POST.get('contact_email')
        org.website_url = request.POST.get('website_url')
        org.contact_phone = request.POST.get('contact_phone')

        # Address fields
        org.country_id = request.POST.get('country')
        org.street_address = request.POST.get('street_address')
        org.city = request.POST.get('city')
        org.state_id = request.POST.get('state')
        org.zip_code = request.POST.get('zip_code')

        # Handle File Upload
        if 'logo' in request.FILES:
            org.logo = request.FILES['logo']

        org.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Organization profile updated successfully!'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_location(request):
    try:
        location_id = request.POST.get('location_id')
        org = Organization.objects.first()

        if location_id:
            count = OrganizationInventoryLocation.objects.filter(organization=org).count()
            if count >= 5:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Maximum limit of 5 locations reached. Please delete an existing location to add a new one.'
                }, status=400)

            loc = OrganizationInventoryLocation.objects.get(id=location_id, organization=org)
        else:
            loc = OrganizationInventoryLocation(organization=org)

        # Name is the only guaranteed field
        loc.name = request.POST.get('name')

        # All others use .get() and can be null/empty
        loc.parent_location_id = int(request.POST.get('parent_location', None) or 0)
        loc.attention = request.POST.get('attention', '')
        loc.address_line1 = request.POST.get('address_line1', '')
        loc.address_line2 = request.POST.get('address_line2', '')
        loc.city = request.POST.get('city', '')
        loc.zip_code = request.POST.get('zip_code', '')
        loc.country_name = request.POST.get('loc_country_name', '')
        loc.state_name = request.POST.get('loc_state_name', '')
        loc.phone = request.POST.get('phone', '')
        loc.fax = request.POST.get('fax', '')
        loc.website_url = request.POST.get('website_url', '')

        loc.save()
        return JsonResponse({'status': 'success', 'message': 'Location saved successfully!'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_location_detail(request, loc_id):
    try:
        loc = OrganizationInventoryLocation.objects.get(id=loc_id)
        return JsonResponse({
            'status': 'success',
            'id': loc.id,
            'name': loc.name,
            'parent_location_id': loc.parent_location_id,
            'attention': loc.attention,
            'address_line1': loc.address_line1,
            'address_line2': loc.address_line2,
            'city': loc.city,
            'zip_code': loc.zip_code,
            'phone': loc.phone,
            'fax': loc.fax,
            'website_url': loc.website_url,
            'country_name': loc.country_name,
            'state_name': loc.state_name
        })
    except OrganizationInventoryLocation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Location not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_location(request):
    try:
        loc_id = request.POST.get('location_id')
        # Ensure we only delete locations belonging to the main organization
        org = Organization.objects.get(id=1)
        location = OrganizationInventoryLocation.objects.get(id=loc_id, organization=org)

        location.delete()

        return JsonResponse({'status': 'success', 'message': 'Location deleted successfully.'})
    except OrganizationInventoryLocation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Location not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)




