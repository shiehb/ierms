# users/urls.py
from django.urls import path
from .views import (
    RegisterView, 
    LoginView,
    ProfileView, 
    UserListView, 
    LogoutView, 
    UserUpdateView,
    send_otp,
    verify_otp_view,
    reset_password_with_otp,
    toggle_user_active,
    change_password,
    first_time_change_password,
    user_search
)
from .serializers import MyTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/', TokenObtainPairView.as_view(serializer_class=MyTokenObtainPairSerializer), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', ProfileView.as_view(), name='me'),
    path('list/', UserListView.as_view(), name='user-list'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('users/<int:id>/', UserUpdateView.as_view(), name='user-update'),
    path('toggle-active/<int:pk>/', toggle_user_active, name='toggle-user-active'),
    path('change-password/', change_password, name='change-password'),
    path('first-time-change-password/', first_time_change_password, name='first-time-change-password'),
    
    # OTP endpoints
    path('send-otp/', send_otp, name='send-otp'),
    path('verify-otp/', verify_otp_view, name='verify-otp'),
    path('reset-password-otp/', reset_password_with_otp, name='reset-password-otp'),

    
    path('search/', user_search, name='user-search'),
]