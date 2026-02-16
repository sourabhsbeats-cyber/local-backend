from django.contrib.admindocs.utils import ROLES
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
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

@api_view(["GET"])
def view_organization_details(request):
    # 1. Fetch Core Data
    countries = Country.objects.filter(name="Australia").values('id', 'name', 'iso2')
    users_cnt = User.objects.filter(is_active=True).count()
    roles_cnt = Group.objects.count()

    # 2. Get Organization & Related Data
    organization_detail = Organization.objects.first()
    org_locations = OrganizationInventoryLocation.objects.filter(
        organization=organization_detail
    )
    # 3. Handle States logic based on Org Country
    states_list = []
    if organization_detail and organization_detail.country_id:
        states_list = State.objects.filter(
            country_id=int(organization_detail.country_id)
        ).values('id', 'name')

    # 4. Serialize for JSON
    # Mapping Organization fields to match your React form expectations
    logo_url = None
    if organization_detail and organization_detail.logo:
        # build_absolute_uri attaches the protocol and host (e.g., http://localhost:8000)
        logo_url = request.build_absolute_uri(organization_detail.logo.url)

    org_data = {
        "id": organization_detail.id if organization_detail else None,
        "company_name": organization_detail.company_name if organization_detail else "",
        "email": organization_detail.contact_email if organization_detail else "",
        "website_url": organization_detail.website_url if organization_detail else "",
        "phone": organization_detail.contact_phone if organization_detail else "",
        "logo_url": logo_url,

        # Address Fields
        "country_id": organization_detail.country_id if organization_detail else None,
        "street_address": organization_detail.street_address if organization_detail else "",
        "city": organization_detail.city if organization_detail else "",
        "state_id": organization_detail.state_id if organization_detail else None,
        "zip_code": organization_detail.zip_code if organization_detail else "",
    }

    # Serializing Location List
    locations_data = [
        {
            "id": loc.id,
            "name": loc.name,
            "address": f"{loc.address_line1}, {loc.city}",
            "state_name": loc.state_name,
            "state_id": loc.state_id,
            "country_id": loc.country_id,
            "country_name": loc.country_name,
            "is_primary": getattr(loc, 'is_primary', False)
        } for loc in org_locations
    ]

    return JsonResponse({
        "status": True,
        "data": {
            "organization": org_data,
            "locations": locations_data,
            "countries": list(countries),
            "states": list(states_list),
            "stats": {
                "active_users": users_cnt,
                "total_roles": roles_cnt
            }
        }
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_location_detail(request, loc_id):
    try:
        # 1. Fetch Location or return 404
        loc = get_object_or_404(OrganizationInventoryLocation, id=loc_id)

        country_id = None
        states_list = []

        # 2. Logic for Country and States mapping
        if loc.country_name:
            try:
                country = Country.objects.get(name=loc.country_name)
                country_id = country.id
                # Serialize states to a list of dicts
                states_list = list(State.objects.filter(country=country).values('id', 'name'))
            except Country.DoesNotExist:
                pass

        # 3. Return Structured Response
        return JsonResponse({
            'status': True,
            'data': {
                'id': loc.id,
                'name': loc.name,
                'parent_location_id': loc.parent_location_id,
                'attention': loc.attention or "",
                'address_line1': loc.address_line1 or "",
                'address_line2': loc.address_line2 or "",
                'city': loc.city or "",
                'zip_code': loc.zip_code or "",
                'phone': loc.phone or "",
                'fax': loc.fax or "",
                'website_url': loc.website_url or "",
                'country_id': country_id,
                'country_name': loc.country_name,
                'state_name': loc.state_name,
                'states_list': states_list  # Useful for populating the state dropdown in React
            }
        })

    except Exception as e:
        return JsonResponse({
            'status': False,
            'message': str(e)
        }, status=400)


@api_view(['PUT'])
def update_location(request, loc_id):
    try:
        location_id = loc_id
        org = Organization.objects.first()
        data = request.data

        count = OrganizationInventoryLocation.objects.filter(organization=org).count()
        if count >= 10:
            return JsonResponse({
                'status': 'error',
                'message': 'Maximum limit of 5 locations reached. Please delete an existing location to add a new one.'
            }, status=400)

        loc = OrganizationInventoryLocation.objects.get(id=location_id, organization=org)

        # Name is the only guaranteed field
        loc.name = data.get('name')

        # All others use .get() and can be null/empty
        loc_country = data.get('country_id', '')
        loc_state = data.get('state_name', '')
        loc_country_obj = None
        loc_state_obj = None
        if loc_country:
            loc_country_obj = Country.objects.filter(id=loc_country).first()
            if loc_state:
                loc_state_obj = State.objects.filter(name=loc_state).first()


        loc.state_id = loc_state_obj.id if loc_state_obj else None
        loc.country_id = loc_country_obj.id if loc_country_obj else None
        loc.country_name = loc_country_obj.name if loc_country_obj else None
        loc.state_name = loc_state_obj.name if loc_state_obj else None

        loc.parent_location_id = int(data.get('parent_location', None) or 0)
        loc.attention = data.get('attention', '')
        loc.address_line1 = data.get('address_line1', '')
        loc.address_line2 = data.get('address_line2', '')
        loc.city = data.get('city', '')
        loc.zip_code = data.get('zip_code', '')

        loc.phone = data.get('phone', '')
        loc.fax = data.get('fax', '')
        loc.website_url = data.get('website_url', '')

        loc.save()
        return JsonResponse({'status': 'success', 'message': 'Location saved successfully!'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)



@api_view(['POST'])
def save_location(request):
    try:
        org = Organization.objects.first()
        data = request.data
        count = OrganizationInventoryLocation.objects.filter(organization=org).count()
        if count >= 5:
            return JsonResponse({
                'status': 'error',
                'message': 'Maximum limit of 5 locations reached. Please delete an existing location to add a new one.'
            }, status=400)

        loc = OrganizationInventoryLocation(organization=org)

        # Name is the only guaranteed field
        loc.name = data.get('name')

        # All others use .get() and can be null/empty
        loc.parent_location_id = int(data.get('parent_location', None) or 0)
        loc.attention = data.get('attention', '')
        loc.address_line1 = data.get('address_line1', '')
        loc.address_line2 = data.get('address_line2', '')
        loc.city = data.get('city', '')
        loc.zip_code = data.get('zip_code', '')
        loc.country_name = data.get('loc_country_name', '')
        loc.state_name = data.get('loc_state_name', '')
        loc.phone = data.get('phone', '')
        loc.fax = data.get('fax', '')
        loc.website_url = data.get('website_url', '')

        loc.save()
        return JsonResponse({'status': 'success', 'message': 'Location added successfully!'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)



@api_view(['DELETE'])
def delete_location(request, loc_id):
    try:
        loc_id = loc_id
        # Ensure we only delete locations belonging to the main organization
        org = Organization.objects.get(id=1)
        location = OrganizationInventoryLocation.objects.get(id=loc_id, organization=org)

        location.delete()

        return JsonResponse({'status': 'success', 'message': 'Location deleted successfully.'})
    except OrganizationInventoryLocation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Location not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser]) # Enables handling files and text together
def update_organization(request):
    try:
        # 1. Fetch the singleton record
        org, created = Organization.objects.get_or_create(id=1)
        data = request.data

        # 2. Map Text Fields (Matching React formData keys)
        org.company_name = data.get('company_name', org.company_name)
        org.contact_email = data.get('email', org.contact_email)
        org.website_url = data.get('website_url', org.website_url)
        org.contact_phone = data.get('phone', org.contact_phone)

        # 3. Address Fields (Matching React formData keys)
        # We use .get(key, org.field) to keep existing value if field is missing in request
        org.country_id = data.get('country_id', org.country_id)
        org.state_id = data.get('state_id', org.state_id)
        org.street_address = data.get('street_address', org.street_address)
        org.city = data.get('city', org.city)
        org.zip_code = data.get('zip_code', org.zip_code)

        # 4. Handle Logo File Upload
        if 'logo' in request.FILES:
            org.logo = request.FILES['logo']

        org.save()

        return JsonResponse({
            'status': True,
            'message': 'Organization profile updated successfully!'
        })

    except Exception as e:
        return JsonResponse({
            'status': False,
            'message': f"Error: {str(e)}"
        }, status=400)







