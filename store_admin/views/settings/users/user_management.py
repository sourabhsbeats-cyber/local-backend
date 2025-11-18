from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from store_admin.models.store_user import StoreUser
from django.contrib.auth.hashers import make_password

@login_required
def manage_user_roles(request):
    if request.method == "POST":
        action = request.POST.get("action")
        name = request.POST.get("name")
        role_id = request.POST.get("role_id")
        try:
            if action == "create":
                if not Group.objects.filter(name=name).exists():
                    Group.objects.create(name=name)
                    messages.success(request, f"Role '{name}' created successfully.")
                else:
                    messages.warning(request, f"Role '{name}' already exists.")

            elif action == "edit":
                role = get_object_or_404(Group, id=role_id)
                role.name = name
                role.save()
                messages.info(request, f"Role '{name}' updated successfully.")

            elif action == "delete":
                role = get_object_or_404(Group, id=role_id)
                role_name = role.name
                role.delete()
                messages.warning(request, f"Role '{role_name}' deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect("manage_user_roles")

    roles = Group.objects.all().order_by("name")
    return render(request, "sbadmin/pages/settings/users/manage_user_roles.html", {"roles": roles})

@login_required
def manage_users(request):
    """
    Manage users: create, edit, and delete from one unified endpoint.
    Works with modal-based form submissions.
    """
    if request.method == "POST":
        action = request.POST.get("action")

        # CREATE USER
        if action == "create":
            name = request.POST.get("name")
            email = request.POST.get("email")
            password = request.POST.get("password")
            is_active = request.POST.get("is_active") == "on"
            group_ids = request.POST.getlist("groups")

            # Check duplicate
            if StoreUser.objects.filter(email=email).exists():
                messages.error(request, f"A user with email '{email}' already exists.")
            else:
                user = StoreUser.objects.create_user(
                    email=email,
                    name=name,
                    password=password,
                    is_active=is_active
                )
                user.groups.set(group_ids)
                user.save()
                messages.success(request, f"User '{name}' created successfully.")

        # EDIT USER
        elif action == "edit":
            user_id = request.POST.get("user_id")
            user = get_object_or_404(StoreUser, id=user_id)
            user.name = request.POST.get("name")
            user.email = request.POST.get("email")
            user.is_active = request.POST.get("is_active") == "on"
            user.groups.set(request.POST.getlist("groups"))
            user.save()
            messages.info(request, f"User '{user.name}' updated successfully.")


        elif action == "reset_password":
            user = get_object_or_404(StoreUser, id=request.POST.get("user_id"))
            new_password = request.POST.get("new_password")
            confirm_password = request.POST.get("confirm_password")

            if not new_password or new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
            else:
                user.password = make_password(new_password)
                user.save()
                #user.email_user("Password Reset", "Your new password has been set successfully.")
                messages.success(request, f"Password for '{user.name}' has been reset successfully.")
        # DELETE USER
        elif action == "delete":
            user_id = request.POST.get("user_id")
            user = get_object_or_404(StoreUser, id=user_id)

            if getattr(user, "is_system_user", False):
                messages.error(request, "System users cannot be deleted.")
            else:
                user_name = user.name
                user.delete()
                messages.warning(request, f"User '{user_name}' deleted successfully.")

        return redirect("manage_users")

    # GET — List users
    users = StoreUser.objects.prefetch_related("groups").order_by("email")
    roles = Group.objects.all().order_by("name")

    return render(request, "sbadmin/pages/settings/users/manage_users.html", {
        "users": users,
        "roles": roles
    })