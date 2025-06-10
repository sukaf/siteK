from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    register_view,
    login_view,
    logout_view,
    profile_view,
    employee_register_view
)

app_name = 'users'

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('register/employee/', employee_register_view, name='employee_register'),
    path('profile/', profile_view, name='profile'),
]

    # Альтернативный вариант с встроенными views Django (если хотите использовать)
    # path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    # path('logout/', auth_views.LogoutView.as_view(), name='logout'),



