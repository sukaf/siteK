# disputes/services.py
from django.db import transaction
from disputes.models import Dispute
from orders.models import Order
from django.core.exceptions import ValidationError


class DisputeService:
    @staticmethod
    @transaction.atomic
    def create_dispute_from_client(order, comment: str):
        """Клиент инициирует спор"""
        if order.status != 'submitted':
            raise ValidationError("Невозможно создать спор для этого заказа")

        if hasattr(order, 'dispute'):
            raise ValidationError("Спор по этому заказу уже существует")

        dispute = Dispute.objects.create(
            order=order,
            customer_comment=comment,
            status='pending'
        )

        order.status = 'disputed'
        order.save()

        return dispute

    @staticmethod
    @transaction.atomic
    def resolve_dispute(dispute, decision: str, admin_user, refund_customer: bool):
        if dispute.status != 'pending':
            raise ValidationError("Спор уже разрешен")

        order = dispute.order

        customer_profile = Profile.objects.select_for_update().get(user=order.customer)
        employee_profile = Profile.objects.select_for_update().get(user=order.employee)

        order_price = order.price

        # Проверяем, что у клиента достаточно замороженных средств
        if customer_profile.frozen_balance < order_price:
            raise ValidationError("Недостаточно замороженных средств у клиента для списания")

        if refund_customer:
            # Вернуть деньги клиенту — разморозить средства (замороженные → доступные)
            customer_profile.release_funds(order_price)
        else:
            # Выплатить исполнителю — списать замороженные средства заказчика (без возврата в баланс)
            customer_profile.frozen_balance -= order_price
            customer_profile.save()

            employee_profile.balance += order_price
            employee_profile.save()

        # Если было refund_customer, release_funds уже вызвал save(), иначе customer_profile.save() вызвали выше.

        dispute.status = 'resolved'
        dispute.resolved_by = admin_user
        dispute.decision = decision
        dispute.save()

        order.status = 'resolved'
        order.save()






