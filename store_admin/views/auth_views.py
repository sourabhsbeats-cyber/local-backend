from dj_rest_auth.jwt_auth import JWTCookieAuthentication
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import  authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework import status
from rest_framework.status import HTTP_401_UNAUTHORIZED

from store_admin.AuthHandler import StrictJWTCookieAuthentication
from store_admin.models import StoreAdminSession


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
@csrf_exempt
def api_login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(username=username, password=password)
    if not user:
        return Response(
            {"status": "error", "message": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    refresh = RefreshToken.for_user(user)

    response = Response(
        {"status": "success", "message": f"Welcome back, {user.name}"},
        status=status.HTTP_200_OK
    )

    response.set_cookie(
        key="access",
        value=str(refresh.access_token),
        httponly=True,
        secure=False,     # True in prod
        samesite="Lax",
        path="/",
        max_age=15 * 60,
    )

    response.set_cookie(
        key="refresh",
        value=str(refresh),
        httponly=True,
        secure=False,     # True in prod
        samesite="Lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )

    return response

@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([JWTCookieAuthentication])
def api_logout(request):

    # 1️⃣ Store logout time (instant logout enforcement)
    if request.user.is_authenticated:
        session, _ = StoreAdminSession.objects.get_or_create(
            user_id=request.user.id
        )
        session.last_logout_at = timezone.now()
        session.save(update_fields=["last_logout_at"])

    # 2️⃣ Blacklist refresh token
    refresh_token = request.COOKIES.get("refresh")
    if refresh_token:
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception:
            pass

    # 3️⃣ Build response
    response = Response(
        {"status": "success", "message": "Logged out successfully"},
        status=status.HTTP_200_OK
    )

    # 4️⃣ DELETE COOKIES (VALID DJANGO API)
    response.delete_cookie("access", path="/", samesite="Lax")
    response.delete_cookie("refresh", path="/", samesite="Lax")

    return response

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def api_me(request):
    user = request.user
    return Response({
        "id": user.id,
        "email": user.email,
        "name": user.name,
    })


from rest_framework_simplejwt.tokens import RefreshToken

@api_view(['POST'])
@permission_classes([AllowAny])
def api_refresh_token(request):
    refresh_token = request.COOKIES.get("refresh")
    if not refresh_token:
        return Response({"message": "Session expired"}, status=401)

    try:
        refresh = RefreshToken(refresh_token)

        response = Response({"status": "refreshed"})
        response.set_cookie(
            key="access",
            value=str(refresh.access_token),
            httponly=True,
            secure=False,
            samesite="Lax",
            path="/",
            max_age=15 * 60,
        )

        return response

    except Exception:
        return Response({"message": "Session expired"}, status=401)



def test_view(request):
    return JsonResponse(
        {"message": "Unauthorized","data":"Use http://admin.hansona.com:3000 "},
        status=status.HTTP_401_UNAUTHORIZED
    )