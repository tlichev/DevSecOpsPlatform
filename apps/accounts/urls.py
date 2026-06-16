from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',           views.login_view,          name='login'),
    path('logout/',          views.logout_view,         name='logout'),
    path('verify-otp/',      views.verify_otp_view,     name='verify_otp'),
    path('resend-otp/',      views.resend_otp_view,     name='resend_otp'),
    path('profile/',         views.profile_view,        name='profile'),
    path('password-change/', views.password_change_view, name='password_change'),
    path('users/',           views.user_list_view,      name='user_list'),
]
