from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings


from django.shortcuts import redirect
from django.urls import reverse

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login


class AuthRequiredMiddleware:
    """
    Middleware для проверки аутентификации пользователя
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.login_url = 'users:login'  # Используем полный путь с namespace

    def __call__(self, request):
        # Проверяем, нужно ли требовать аутентификацию для этого пути
        exempt_urls = [
            reverse('users:login'),
            reverse('users:register'),
            reverse('users:employee_register'),
            reverse('home'),
            # Добавьте другие URL, которые не требуют аутентификации
        ]

        if not request.user.is_authenticated and request.path not in exempt_urls:
            return redirect_to_login(request.get_full_path(), login_url=self.login_url)

        return self.get_response(request)

