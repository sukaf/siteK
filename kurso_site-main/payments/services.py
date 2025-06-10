# payments/services.py
from users.models import Profile
import stripe
from django.conf import settings
from .models import Transaction
from users.models import Profile
from django.core.exceptions import ValidationError
from django.db import transaction

stripe.api_key = settings.STRIPE_SECRET_KEY



class PayoutService:
    @staticmethod
    def create_payout_request(profile, amount):
        """Создание запроса на выплату"""
        if not profile.user.is_employee:
            raise ValidationError("Только исполнители могут запрашивать выплаты")

        with transaction.atomic():
            profile.freeze_funds(amount)
            from payments.models import PayoutRequest
            return PayoutRequest.objects.create(
                employee=profile.user,
                amount=amount
            )


class PaymentService:
    @staticmethod
    def create_payment_intent(amount, user, description=None):
        """Создает платежное намерение в Stripe"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe использует центы/копейки
                currency=settings.STRIPE_CURRENCY,
                metadata={
                    'user_id': user.id,
                    'description': description or 'Пополнение баланса'
                }
            )
            return intent
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe error: {str(e)}")



    @staticmethod
    def handle_successful_payment(payment_intent):
        """Обрабатывает успешный платеж"""
        try:
            user_id = payment_intent.metadata.get('user_id')
            amount = payment_intent.amount / 100  # Конвертируем обратно в рубли

            # Создаем транзакцию
            transaction = Transaction.objects.create(
                user_id=user_id,
                amount=amount,
                transaction_type='deposit',
                status='succeeded',
                payment_id=payment_intent.id,
                description=payment_intent.metadata.get('description')
            )

            # Пополняем баланс пользователя
            profile = Profile.objects.get(user_id=user_id)
            profile.balance += amount
            profile.save()

            return transaction
        except Exception as e:
            raise ValueError(f"Payment processing error: {str(e)}")


    @staticmethod
    @transaction.atomic
    def accept_order(order, employee):
        if order.status != 'pending':
            raise ValidationError("Заказ нельзя принять, он не в статусе 'pending'")

        if order.employee is not None:
            raise ValidationError("Заказ уже принят другим исполнителем")

        if not hasattr(order.customer, 'profile'):
            raise ValidationError("У заказчика отсутствует профиль")

        customer_profile = order.customer.profile

        # Проверяем, что замороженных средств достаточно
        if customer_profile.frozen_balance < order.price:
            raise ValidationError("Недостаточно замороженных средств у заказчика")

        # Назначаем исполнителя и меняем статус заказа
        order.employee = employee
        order.status = 'in_progress'
        order.save()

        # Подтверждаем заморозку (записываем это в транзакции)
        Transaction.objects.create(
            user=order.customer,
            profile=customer_profile,
            amount=order.price,
            order=order,
            transaction_type='freeze',
            status='succeeded',
            description="Подтверждение: средства уже были заморожены при создании заказа"
        )


class OrderService:
    @staticmethod
    @transaction.atomic
    def client_approve(order):
        """Клиент подтверждает выполнение — средства переходят исполнителю"""
        if order.status != 'submitted':
            raise ValidationError("Заказ ещё не отправлен на подтверждение или уже завершён")

        customer_profile = Profile.objects.select_for_update().get(user=order.customer)
        employee_profile = Profile.objects.select_for_update().get(user=order.employee)

        amount = order.price

        if customer_profile.frozen_balance < amount:
            raise ValidationError("Замороженных средств недостаточно для выплаты")

        # Списываем с заморозки у заказчика
        customer_profile.frozen_balance -= amount
        customer_profile.save()

        # Переводим исполнителю
        employee_profile.balance += amount
        employee_profile.save()

        # Меняем статус заказа
        order.status = 'completed'
        order.save()

        # Логируем транзакцию
        Transaction.objects.create(
            user=order.employee,
            profile=employee_profile,
            order=order,
            amount=amount,
            transaction_type='payout',
            status='succeeded',
            description='Выплата исполнителю при подтверждении заказа клиентом'
        )




