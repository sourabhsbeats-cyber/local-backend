from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import connection


User = get_user_model()

class CustomDBAuth(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, email, password FROM store_admin_storeuser where email=%s LIMIT 1", [username])
            row = cursor.fetchone()
            if not row:
                return None

            user_id, email, pw_hash = row[0], row[1], row[2]
            print(user_id)
            if not check_password(password, pw_hash):
                return None

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = User.objects.create(username=email, email=email, is_active=True)
                user.set_unusable_password()
                user.save()
            return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
