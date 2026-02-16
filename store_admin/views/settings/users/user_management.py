from django.contrib.auth.models import User, Group
from django.contrib import messages
import json

from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view

from store_admin.models.store_user import StoreUser
from django.contrib.auth.hashers import make_password

#role mgnt
@api_view(["GET"])
def list_user_roles(request):
    # 1. Fetch the groups (Roles)
    roles_queryset = Group.objects.all().order_by("name")

    # 2. Manual Serialization: Convert model instances to a list of dictionaries
    roles_list = []
    for role in roles_queryset:
        roles_list.append({
            "id": role.id,
            "name": role.name,
            # You can also count how many users are in this role
            "user_count": role.user_set.count()
        })

    # 3. Return the JSON response
    return JsonResponse({
        "status": True,
        "message": "Roles fetched successfully",
        "data": roles_list
    })

@api_view(["POST"])
def create_user_roles(request):
    data = request.data
    try:
        name = data.get("name")
        if not Group.objects.filter(name=name).exists():
            Group.objects.create(name=name)
            return JsonResponse({"status":True, "message":f"Role '{name}' created successfully." })
        else:
            return JsonResponse({"status":False, "message": f"Role '{name}' already exists." })
    except Exception as e:
        return JsonResponse({"status": True, "message": f"{str(e)}"})

@api_view(["PUT"])
def update_user_roles(request, role_id):
    data = request.data
    try:
        name = data.get("name")
        role = get_object_or_404(Group, id=role_id)
        role.name = name
        role.save()
        return JsonResponse({"status": True, "message": f"Role '{name}' updated successfully."})

    except Exception as e:
        return JsonResponse({"status": True, "message": f"{str(e)}"})

@api_view(["DELETE"])
def delete_user_roles(request, role_id):
    try:
        # 1. Get the role or return 404
        role = get_object_or_404(Group, id=role_id)

        # 2. Check user count
        user_count = role.user_set.count()

        if user_count > 0:
            return JsonResponse({
                "status": False,
                "message": f"Cannot delete '{role.name}'. It is assigned to {user_count} user(s)."
            }, status=400)  # 400 Bad Request

        # 3. Perform deletion
        role_name = role.name
        role.delete()

        return JsonResponse({
            "status": True,
            "message": f"Role '{role_name}' removed successfully."
        })

    except Exception as e:
        # Changed status to False here to correctly signal an error to the frontend
        return JsonResponse({
            "status": False,
            "message": f"An error occurred: {str(e)}"
        }, status=500)

#role mgnt

#users
@api_view(["GET"])
def list_users(request):
    # 1. Fetch Users with Roles
    users_qs = StoreUser.objects.prefetch_related("groups").all().order_by("email")

    # 2. Filtering Logic (if search query 'q' is passed)
    search_query = request.GET.get("q", "").strip()
    if search_query:
        users_qs = users_qs.filter(name__icontains=search_query) | users_qs.filter(email__icontains=search_query)

    # 3. Pagination for Tabulator
    page_size = request.GET.get("size", 10)
    page_number = request.GET.get("page", 1)
    paginator = Paginator(users_qs, page_size)
    page_obj = paginator.get_page(page_number)

    # 4. Serialize User Data
    user_list = []
    for user in page_obj:
        user_list.append({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            # Join multiple roles into a single string for the table display
            "role": ", ".join([g.name for g in user.groups.all()]),
            # IDs list for the "Edit" modal to pre-select checkboxes/select
            "role_ids": list(user.groups.values_list('id', flat=True)),
            "status": 1 if user.is_active else 0,
            "is_system": 1 if user.is_system_user else 0,
        })

    # 5. Fetch all available roles for the Modal dropdown
    roles_qs = Group.objects.all().order_by("name")
    roles_list = [{"id": r.id, "name": r.name} for r in roles_qs]

    return JsonResponse({
        "status": True,
        "data": user_list,
        "roles": roles_list,
        "last_page": paginator.num_pages,
        "total": paginator.count
    })

@api_view(["POST"])
def create_user(request):
    data = request.data
    name = data.get("name", "").strip()
    email = data.get("email", "").lower().strip()
    password = data.get("password")
    is_active = data.get("status") == 1
    is_system = data.get("is_system") == 1
    group_ids = data.get("roles", [])  # Expecting list of IDs

    # 1. Validation
    if not email or not password:
        return JsonResponse({"status": False, "message": "Email and password are required."}, status=400)

    # 2. Check duplicate (Fix: status should be False)
    if StoreUser.objects.filter(email=email).exists():
        return JsonResponse({
            "status": False,
            "message": f"A user with email '{email}' already exists."
        })

    try:
        # Use a transaction to ensure user and groups are saved together
        with transaction.atomic():
            # 3. Create user instance
            # Note: create_user helper usually handles hashing,
            # but we explicitly set attributes from your model
            user = StoreUser.objects.create_user(
                email=email,
                name=name,
                password=password
            )

            # 4. Set custom fields
            user.is_active = is_active
            user.is_system_user = is_system

            # 5. Assign Roles (Groups)
            if group_ids:
                user.groups.set(group_ids)

            user.save()

        return JsonResponse({
            "status": True,
            "message": f"User '{name}' created successfully."
        })

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": f"Server Error: {str(e)}"
        }, status=500)

import logging
@api_view(["POST"])
def reset_user_password(request, user_id):
    try:
        # 1. Fetch user or return 404
        user = get_object_or_404(StoreUser, id=user_id)

        # 2. Extract password from request
        # In your React Modal, you send JSON: { "password": passwords.p1 }
        data = request.data
        new_password = data.get("password")

        # 3. Validation
        if not new_password:
            return JsonResponse({
                "status": False,
                "message": "Password cannot be empty."
            }, status=400)

        if len(new_password) < 8:
            return JsonResponse({
                "status": False,
                "message": "Password must be at least 8 characters long."
            }, status=400)

        # 4. Update Password using hashing
        user.password = make_password(new_password)
        user.save()

        # 5. Optional: Log the activity
        #logger.info(f"Password reset successful for user ID: {user_id} by {request.user}")

        return JsonResponse({
            "status": True,
            "message": f"Password for '{user.name}' has been updated successfully."
        })

    except Exception as e:
        # Log the actual error for the developer
        #logger.error(f"Error resetting password for user {user_id}: {str(e)}")

        # Return a clean error to the React frontend
        return JsonResponse({
            "status": False,
            "message": "An internal server error occurred. Please try again later."
        }, status=500)


@api_view(["PUT", "POST"])
def update_user_details(request, user_id):
    user = get_object_or_404(StoreUser, id=user_id)
    data = request.data

    # 1. Extract and sanitize data
    new_email = data.get("email", "").lower().strip()
    new_name = data.get("name", "").strip()

    # 2. Unique Email Validation (Exclude current user)
    if StoreUser.objects.filter(email=new_email).exclude(id=user_id).exists():
        return JsonResponse({
            "status": False,
            "message": f"The email '{new_email}' is already in use by another account."
        }, status=400)

    try:
        with transaction.atomic():
            # 3. Update Basic Info
            user.name = new_name
            user.email = new_email

            # 4. Handle Booleans (mapping 1/0 from React to True/False)
            user.is_active = data.get("status") == 1
            user.is_system_user = data.get("is_system") == 1

            # 5. Update Roles (Many-to-Many)
            group_ids = data.get("roles", [])
            user.groups.set(group_ids)

            # 6. Save
            user.save()

        return JsonResponse({
            "status": True,
            "message": f"User '{user.name}' updated successfully."
        })

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": f"Internal Server Error: {str(e)}"
        }, status=500)
