from django.contrib.auth.backends import BaseBackebd
from django.contrib.auth.models import User
from django.db import connection

class CustomDBAuth(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, email, password FROM store_login where email=%s ", [username])
            row = cursor.fetchone()
            if row and password == row[2]:
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    user = User(username=username)
                    user.save()
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
