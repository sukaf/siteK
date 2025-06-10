from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.core.exceptions import ValidationError
from django.utils.timezone import now
import time
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging
from users.models import Profile
from django.contrib.admin.views.decorators import staff_member_required
# Правильные импорты моделей из соответствующих приложений
from .models import Order
from payments.models import PriceProposal
from messaging.models import Message
from payments.models import PayoutRequest
from disputes.models import Dispute
from users.models import User
from .forms import OrderForm, PriceProposalForm, MessageForm
from payments.services import PaymentService
from django.contrib import messages
from payments.services import OrderService
from disputes.services import DisputeService
from django.db import transaction

logger = logging.getLogger(__name__)

@login_required
def order_list_view(request):
    """Список доступных заказов (виден только сотрудникам)"""
    if not request.user.is_employee:
        return redirect('profile')

    orders = Order.objects.filter(status='pending', employee__isnull=True)
    return render(request, 'orders/order_list.html', {'orders': orders})

@login_required
def accept_order_view(request, order_id):
    if not request.user.is_employee:
        return redirect('profile')

    order = get_object_or_404(Order, id=order_id)

    if order.status != 'pending' or order.employee is not None:
        messages.warning(request, "Этот заказ уже принят или недоступен.")
        return redirect('orders:order_list')

    if request.method == 'POST':
        if 'accept' in request.POST:
            try:
                PaymentService.accept_order(order, request.user)
                messages.success(request, "Вы успешно приняли заказ")
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Ошибка при принятии заказа: {e}")
                messages.error(request, "Произошла ошибка при принятии заказа")
            return redirect('orders:order_list')

        elif 'propose_price' in request.POST:
            form = PriceProposalForm(request.POST)
            if form.is_valid():
                if not PriceProposal.objects.filter(order=order, employee=request.user).exists():
                    PriceProposal.objects.create(
                        order=order,
                        employee=request.user,
                        proposed_price=form.cleaned_data['proposed_price']
                    )
                    messages.success(request, "Вы предложили цену для заказа")
                else:
                    messages.warning(request, "Вы уже предлагали цену для этого заказа")
                return redirect('orders:order_list')
        else:
            messages.error(request, "Неизвестное действие")
            return redirect('order_list')
    else:
        form = PriceProposalForm()

    return render(request, 'orders/accept_order.html', {'order': order, 'form': form})


@login_required
def create_order_view(request, tag=None):
    if not request.user.is_customer:
        return redirect('users:profile')

    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES)
        if form.is_valid():
            order = form.save(commit=False)
            order.customer = request.user
            order.tag = tag if tag in dict(Order.TAG_CHOICES).keys() else 'ready_work'

            profile = request.user.profile

            if not profile.can_pay(order.price):
                messages.error(request, "Недостаточно средств на балансе")
                return render(request, 'orders/order_create.html', {'form': form})

            try:
                profile.freeze_funds(order.price)
            except ValidationError as e:
                messages.error(request, f"Ошибка с балансом: {str(e)}")
                return render(request, 'orders/order_create.html', {'form': form})

            order.save()
            messages.success(request, "Заказ успешно создан и средства заблокированы")
            return redirect('users:profile')
    else:
        form = OrderForm(initial={'tag': tag})

    return render(request, 'orders/order_create.html', {'form': form})

@login_required
def my_orders_view(request):
    """Список заказов, принятых исполнителем"""
    if not request.user.is_employee:
        return redirect('profile')

    orders = Order.objects.filter(employee=request.user).exclude(status='approved')
    return render(request, 'orders/my_orders.html', {'orders': orders})

@login_required
def order_detail_view(request, order_id):
    """Детали заказа с чатом"""
    order = get_object_or_404(Order, id=order_id)

    if request.user not in [order.customer, order.employee]:
        return redirect('profile')

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.order = order
            message.sender = request.user
            message.save()
            return redirect('order_detail', order_id=order.id)
    else:
        form = MessageForm()

    show_price_proposal = (
        request.user == order.customer and
        order.price_proposals.filter(is_accepted=False).exists()
    )

    can_propose_price = (
        request.user.is_employee and
        order.status == 'pending' and
        not order.price_proposals.filter(employee=request.user).exists()
    )

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'messages': order.messages.all(),
        'form': form,
        'proposals': order.price_proposals.all().select_related('employee'),
        'show_price_proposal': show_price_proposal,
        'active_proposal': order.price_proposals.filter(is_accepted=False).first(),
        'can_propose_price': can_propose_price,
    })


@login_required
@require_POST
def approve_proposal_view(request, proposal_id):
    """Заказчик принимает предложение цены"""
    proposal = get_object_or_404(PriceProposal, id=proposal_id)
    order = proposal.order

    if request.user != order.customer:
        return HttpResponseForbidden("Только заказчик может подтвердить предложение")

    if order.status != 'pending':
        messages.error(request, "Заказ уже принят другим исполнителем")
        return redirect('orders:order_detail', order_id=order.id)

    customer_profile = request.user.profile
    old_price = order.price
    new_price = proposal.proposed_price
    available_total = customer_profile.balance + customer_profile.frozen_balance

    if available_total < new_price:
        messages.error(request, "Недостаточно средств для принятия нового предложения.")
        return redirect('orders:order_detail', order_id=order.id)

    with transaction.atomic():
        # Разморозить старую сумму
        customer_profile.frozen_balance -= old_price
        customer_profile.balance += old_price

        # Проверка на всякий случай
        if customer_profile.balance < new_price:
            messages.error(request, "Недостаточно средств после разморозки для новой цены.")
            return redirect('orders:order_detail', order_id=order.id)

        # Заморозить новую цену
        customer_profile.balance -= new_price
        customer_profile.frozen_balance += new_price
        customer_profile.save()

        # Обновить заказ
        order.employee = proposal.employee
        order.price = new_price
        order.status = 'in_progress'
        order.save()

        proposal.is_accepted = True
        proposal.save()

        # Остальные предложения отклонить
        PriceProposal.objects.filter(order=order).exclude(id=proposal.id).update(is_accepted=False)

        messages.success(request, f"Вы приняли предложение от {proposal.employee.username}")
        return redirect('orders:order_detail', order_id=order.id)


@login_required
def approve_price_view(request, order_id):
    """Заказчик подтверждает предложенную цену или предлагает свою"""
    order = get_object_or_404(Order, id=order_id, status='price_proposed', customer=request.user)

    if request.method == 'POST':
        if 'approve' in request.POST:
            order.is_price_approved = True
            order.status = 'in_progress'
            order.save()
            return redirect('profile')

        elif 'counter_offer' in request.POST:
            form = PriceProposalForm(request.POST)
            if form.is_valid():
                order.price = form.cleaned_data['proposed_price']
                order.status = 'pending'
                order.employee = None
                order.is_price_approved = False
                order.proposed_price = None
                order.save()
                return redirect('profile')
    else:
        form = PriceProposalForm(initial={'proposed_price': order.proposed_price})

    return render(request, 'orders/approve_price.html', {
        'order': order,
        'form': form,
        'proposed_price': order.proposed_price
    })

def index_view(request):
    return render(request, 'orders/index.html')

@require_POST
@login_required
def submit_to_client_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.user != order.employee:
        return HttpResponseForbidden("Только исполнитель может отправить заказ")

    if 'completed_file' not in request.FILES:
        messages.error(request, "Вы не прикрепили файл с выполненной работой")
        return redirect('order_detail', order_id=order.id)

    try:
        if order.completed_file:
            order.completed_file.delete()

        uploaded_file = request.FILES['completed_file']
        fs = FileSystemStorage()

        file_ext = uploaded_file.name.split('.')[-1]
        filename = f"completed_orders/order_{order.id}_{int(time.time())}.{file_ext}"

        saved_file = fs.save(filename, uploaded_file)

        order.completed_file = saved_file
        order.status = 'submitted'
        order.submitted_at = timezone.now()
        order.payout_due_date = timezone.now() + timedelta(days=3)
        order.save()

        Message.objects.create(
            order=order,
            sender=request.user,
            text=f"Отправлен готовый файл: {uploaded_file.name}"
        )

        messages.success(request, "Файл успешно отправлен клиенту")
    except Exception as e:
        messages.error(request, f"Ошибка при отправке файла: {str(e)}")
        logger.error(f"Error submitting file: {str(e)}")

    return redirect('orders:order_detail', order_id=order.id)

@require_POST
@login_required
def client_approve_view(request, order_id):
    """Клиент подтверждает выполнение заказа и переводит средства исполнителю"""
    order = get_object_or_404(Order, id=order_id, status='submitted')

    if request.user != order.customer:
        return HttpResponseForbidden("Только заказчик может подтвердить заказ")

    try:
        OrderService.client_approve(order)

        Message.objects.create(
            order=order,
            sender=request.user,
            text="Заказ принят. Спасибо!"
        )

        messages.success(request, "Заказ успешно подтверждён, средства переведены исполнителю.")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Ошибка при подтверждении заказа клиентом: {e}")
        messages.error(request, "Произошла ошибка при завершении заказа")

    return redirect('orders:order_detail', order_id=order.id)


@login_required
def client_reject_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    if request.method == 'POST':
        comment = request.POST.get('comment', '')

        try:
            DisputeService.create_dispute_from_client(order, comment)
            messages.success(request, "Заказ отклонён, спор создан.")
        except ValidationError as e:
            messages.error(request, str(e))

        return redirect('orders:order_detail', order_id=order.id)

    return render(request, 'orders/client_reject_form.html', {'order': order})

@login_required
@staff_member_required
def dispute_list_view(request):
    disputes = Dispute.objects.filter(status='pending').select_related('order')
    return render(request, 'orders/dispute_list.html', {
        'active_disputes': disputes,
    })

@login_required
@staff_member_required
def resolve_dispute_view(request, dispute_id):
    dispute = get_object_or_404(Dispute, id=dispute_id)

    if request.method == 'POST':
        decision = request.POST.get('decision')
        refund_customer = 'refund_customer' in request.POST

        try:
            DisputeService.resolve_dispute(
                dispute=dispute,
                decision=decision,
                admin_user=request.user,
                refund_customer=refund_customer
            )
            messages.success(request, "Спор успешно разрешен")
            return redirect('dispute_list')
        except ValidationError as e:
            messages.error(request, str(e))

    decisions = [
        ('client', 'Возврат клиенту'),
        ('executor', 'Выплата исполнителю'),
    ]

    return render(request, 'orders/resolve_dispute.html', {
        'dispute': dispute,
        'decisions': decisions,
    })

@staff_member_required
def resolve_dispute(request, pk):
    dispute = get_object_or_404(Dispute, pk=pk)
    if request.method == 'POST':
        decision = request.POST.get('decision')
        refund_customer = 'refund_customer' in request.POST

        try:
            DisputeService.resolve_dispute(
                dispute=dispute,
                decision=decision,
                admin_user=request.user,
                refund_customer=refund_customer
            )

            if refund_customer:
                messages.success(request, "Деньги возвращены клиенту")
            else:
                messages.success(request, "Деньги выплачены исполнителю")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('admin:disputes_dispute_change', object_id=pk)


@login_required
def request_payout_view(request):
    if not request.user.is_employee:
        return HttpResponseForbidden("Только исполнители могут запрашивать выплаты")

    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            if amount <= 0:
                messages.error(request, "Сумма должна быть положительной")
                return redirect('request_payout')

            if amount > profile.balance:
                messages.error(request, "Недостаточно средств на балансе")
                return redirect('request_payout')

            payout = PayoutRequest.objects.create(
                employee=request.user,
                amount=amount
            )

            profile.balance -= amount
            profile.save()

            messages.success(request, f"Запрос на выплату {amount} руб. создан")
            return redirect('profile')

        except Exception as e:
            messages.error(request, f"Ошибка: {str(e)}")
            logger.error(f"Payout request error: {str(e)}")

    return render(request, 'orders/request_payout.html', {
        'balance': profile.balance
    })

@login_required
def payout_requests_view(request):
    """Список запросов на выплату (для админа)"""
    if not request.user.is_superuser:
        return HttpResponseForbidden("Только администратор может просматривать запросы")

    payout_requests = PayoutRequest.objects.filter(status='pending')
    return render(request, 'orders/payout_requests.html', {
        'payout_requests': payout_requests
    })

@require_POST
@login_required
def process_payout_view(request, payout_id):
    """Администратор обрабатывает запрос на выплату"""
    if not request.user.is_superuser:
        return HttpResponseForbidden("Только администратор может обрабатывать запросы")

    payout = get_object_or_404(PayoutRequest, id=payout_id)
    action = request.POST.get('action')
    comment = request.POST.get('comment', '')

    try:
        if action == 'approve':
            payout.approve(comment=comment)
            messages.success(request, "Выплата одобрена")
        elif action == 'reject':
            payout.reject(comment=comment)
            messages.success(request, "Выплата отклонена")
    except Exception as e:
        messages.error(request, f"Ошибка: {str(e)}")

    return redirect('payout_requests')

@login_required
def propose_price_view(request, order_id):
    """Исполнитель предлагает цену для заказа"""
    if not request.user.is_employee:
        return redirect('profile')

    order = get_object_or_404(Order, id=order_id, status='pending')

    if request.method == 'POST':
        form = PriceProposalForm(request.POST)
        if form.is_valid():
            if not PriceProposal.objects.filter(order=order, employee=request.user).exists():
                PriceProposal.objects.create(
                    order=order,
                    employee=request.user,
                    proposed_price=form.cleaned_data['proposed_price']
                )
                messages.success(request, "Ваше предложение цены отправлено")
            else:
                messages.warning(request, "Вы уже предлагали цену для этого заказа")
            return redirect('order_detail', order_id=order.id)
    else:
        form = PriceProposalForm()

    return render(request, 'orders/propose_price.html', {
        'order': order,
        'form': form
    })


