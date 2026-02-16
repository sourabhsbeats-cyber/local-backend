from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from store_admin.models import StoreAdminSession

User = get_user_model()


class JWTCookieAuthentication(BaseAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get("access")
        if not raw_token:
            return None

        try:
            validated_token = AccessToken(raw_token)
            user = User.objects.get(id=validated_token["user_id"])
        except Exception:
            raise AuthenticationFailed("Invalid or expired token")

        return user, validated_token


class StrictJWTCookieAuthentication(JWTCookieAuthentication):
    def authenticate(self, request):
        try:
            result = super().authenticate(request)
        except AuthenticationFailed:
            # Access token expired → allow refresh flow
            return None

        if not result:
            return None

        user, validated_token = result

        logout_at = StoreAdminSession.objects.filter(
            user_id=user.id
        ).values_list("last_logout_at", flat=True).first()

        if logout_at:
            token_issued_at = datetime.fromtimestamp(
                validated_token["iat"],
                tz=dt_timezone.utc
            )

            if token_issued_at < logout_at:
                raise AuthenticationFailed("Session expired")

        return user, validated_token
