import stripe
from decimal import Decimal
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth import get_user_model
from .forms import DepositForm, WithdrawalForm
from .models import Transaction
from django.utils import timezone  # Добавить для request_withdrawal
from django.core.mail import send_mail  # Перенести в начало файла
User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY
import logging
logger = logging.getLogger(__name__)


@login_required
def deposit_view(request):
    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            # Создание сессии Stripe Checkout
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'rub',
                        'product_data': {
                            'name': 'Пополнение баланса',
                        },
                        'unit_amount': int(amount * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(reverse('payments:payment_success')) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('payments:payment_cancel')),
                metadata={
                    'user_id': str(request.user.id),
                    'amount': str(amount),
                }
            )
            return redirect(session.url, code=303)
    else:
        form = DepositForm()

    return render(request, 'payments/deposit.html', {
        'form': form,
    })


@login_required
def payment_success_view(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        return redirect("profile")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(session_id)

    if session.payment_status == "paid":
        amount = Decimal(session.amount_total) / 100  # преобразуем в Decimal

        profile = request.user.profile

        # Добавляем проверку: если транзакция уже есть — не дублируем
        if not Transaction.objects.filter(stripe_session_id=session_id).exists():
            profile.balance += amount
            profile.save()

            Transaction.objects.create(
                user=request.user,
                amount=amount,
                transaction_type="deposit",  # ✅ Поле называется transaction_type
                status="succeeded",
                stripe_session_id=session_id
            )

        return render(request, "payments/success.html", {"amount": amount})
    else:
        return render(request, "payments/payment_failed.html")


@login_required
def payment_cancel_view(request):
    """Страница отмены платежа"""
    return render(request, 'payments/cancel.html')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Обработчик вебхуков Stripe для надежной обработки платежей"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    # Обработка успешного платежа через Checkout Session
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        if session.payment_status == 'paid':
            try:
                metadata = session.metadata
                user_id = metadata.get('user_id')
                amount = Decimal(metadata.get('amount'))

                user = User.objects.get(id=user_id)
                transaction = Transaction.objects.filter(
                    stripe_session_id=session.id
                ).first()

                if not transaction:
                    transaction = Transaction.objects.create(
                        user=user,
                        profile=user.profile,
                        amount=amount,
                        transaction_type="deposit",
                        stripe_session_id=session.id,
                        stripe_payment_intent_id=session.payment_intent,
                        description="Пополнение через Stripe",
                        status="succeeded"
                    )
                elif transaction.status != 'succeeded':
                    transaction.status = 'succeeded'
                    transaction.stripe_payment_intent_id = session.payment_intent
                    transaction.save()

                user.profile.deposit(amount)

            except Exception as e:
                # Логируем ошибку для дальнейшего анализа
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Webhook error: {str(e)}", exc_info=True)

    return HttpResponse(status=200)


@login_required
def request_withdrawal(request):
    """Запрос на вывод средств с дополнительными проверками"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST-запросы'}, status=405)

    form = WithdrawalForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors.as_json()}, status=400)

    amount = form.cleaned_data['amount']
    profile = request.user.profile

    # Проверка минимальной суммы вывода
    if amount < Decimal('50.00'):  # Минимум 50 руб.
        return JsonResponse({'error': 'Минимальная сумма вывода 50 руб.'}, status=400)

    if profile.balance < amount:
        return JsonResponse({'error': 'Недостаточно средств'}, status=400)

    # Проверка не чаще 1 раза в 24 часа
    last_withdrawal = Transaction.objects.filter(
        user=request.user,
        transaction_type="withdrawal",
        created_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).first()

    if last_withdrawal:
        return JsonResponse({
            'error': 'Вы можете запрашивать вывод не чаще 1 раза в 24 часа'
        }, status=400)

    # Замораживаем средства
    profile.freeze(amount)

    # Создаем запрос на вывод
    Transaction.objects.create(
        user=request.user,
        profile=profile,
        amount=amount,
        transaction_type="withdrawal",
        description="Запрошен вывод средств",
        status="pending",
        withdrawal_details=form.cleaned_data.get('withdrawal_details')
    )

    # Отправляем уведомление администратору
    from django.core.mail import send_mail
    send_mail(
        'Новый запрос на вывод средств',
        f'Пользователь {request.user.email} запросил вывод {amount} руб.',
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMIN_EMAIL],
        fail_silently=True,
    )

    return JsonResponse({
        'status': 'Заявка на вывод принята',
        'balance': str(profile.balance),
        'frozen_balance': str(profile.frozen_balance)
    })


@require_POST
@csrf_exempt
def create_payment_intent(request):
    try:
        logger.info(f"Request data: {request.body}")
        data = json.loads(request.body)
        amount = int(float(data['amount']) * 100)  # Переводим в копейки

        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency='rub',
            automatic_payment_methods={'enabled': True},  # <<< ВАЖНО!
            metadata={
                'user_id': request.user.id,
                'amount': str(amount)
            }
        )

        return JsonResponse({
            'clientSecret': intent.client_secret
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
