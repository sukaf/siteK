from django.urls import path
from . import views

app_name = 'payments'


urlpatterns = [
    path('deposit/', views.deposit_view, name='deposit'),
    path('success/', views.payment_success_view, name='payment_success'),
    path('cancel/', views.payment_cancel_view, name='payment_cancel'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('withdraw/', views.request_withdrawal, name='request_withdrawal'),
    path('create-payment-intent/', views.create_payment_intent, name='create_payment_intent'),
]


