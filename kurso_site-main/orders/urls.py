from django.urls import path
from django.contrib.auth.decorators import login_required
from .views import (
    order_list_view, accept_order_view, create_order_view,
    my_orders_view, order_detail_view, approve_price_view,
    submit_to_client_view, client_approve_view, client_reject_view,
    request_payout_view, payout_requests_view, process_payout_view,
    index_view, approve_proposal_view, propose_price_view
)

from .views import resolve_dispute_view

from . import views

app_name = 'orders'

urlpatterns = [
    path('', index_view, name='index'),
    path('orders/', login_required(order_list_view), name='order_list'),
    path('orders/create/', login_required(create_order_view), name='create_order'),
    path('orders/create/<str:tag>/', login_required(create_order_view), name='create_order_tagged'),
    path('orders/accept/<int:order_id>/', login_required(accept_order_view), name='accept_order'),
    path('orders/<int:order_id>/approve-price/', login_required(approve_price_view), name='approve_price'),

    # Новые URL для workflow
    path('orders/<int:order_id>/submit/', login_required(submit_to_client_view), name='submit_to_client'),
    path('orders/<int:order_id>/client-approve/', login_required(client_approve_view), name='client_approve'),
    path('orders/<int:order_id>/client-reject/', login_required(client_reject_view), name='client_reject'),

    # URL для выплат
    path('payout/request/', login_required(request_payout_view), name='request_payout'),
    path('payout/requests/', login_required(payout_requests_view), name='payout_requests'),
    path('payout/process/<int:payout_id>/', login_required(process_payout_view), name='process_payout'),

    # Общие URL
    path('my-orders/', login_required(my_orders_view), name='my_orders'),
    path('order/<int:order_id>/', login_required(order_detail_view), name='order_detail'),

    path('orders/<int:order_id>/propose-price/', views.propose_price_view, name='propose_price'),
    path('proposals/<int:proposal_id>/approve/', views.approve_proposal_view, name='approve_proposal'),

    path('disputes/', views.dispute_list_view, name='dispute_list'),
    path('disputes/<int:dispute_id>/resolve/', views.resolve_dispute_view, name='resolve_dispute'),
    path('dispute/<int:pk>/resolve/', views.resolve_dispute, name='orders_dispute_resolve'),
    path('dispute/<int:dispute_id>/resolve/', views.resolve_dispute_view, name='orders_dispute_resolve'),

    path('create/', views.create_order_view, name='create_order'),  # без тега
    path('create/<str:tag>/', views.create_order_view, name='create_order_tagged'),  # с тегом


]

