from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import LoginSerializer, RegisterSerializer, UserSerializer
from core.response import api_response


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = {"user": UserSerializer(user).data, "tokens": _tokens_for(user)}
        return api_response(data=data, message="Registered successfully", status_code=201)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        data = {"user": UserSerializer(user).data, "tokens": _tokens_for(user)}
        return api_response(data=data, message="Logged in successfully")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_response(data=UserSerializer(request.user).data)
