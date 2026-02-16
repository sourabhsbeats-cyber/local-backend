from django.db import models
from django.contrib.auth.models import User

from django.db import models


class UserPreference(models.Model):
    user_id = models.BigIntegerField(unique=True, help_text="Manual link to auth_user table ID")
    settings = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_user_preference'

    def __str__(self):
        return f"Pref for User ID: {self.user_id}"