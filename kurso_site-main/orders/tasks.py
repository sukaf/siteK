from celery import shared_task
from django.utils.timezone import now
from .models import Order
from celery import shared_task
from django.utils import timezone


@shared_task
def check_auto_completion():
    orders = Order.objects.filter(
        status='submitted',
        payout_due_date__lte=now()
    )
    for order in orders:
        order.check_auto_completion()


@shared_task
def check_expired_disputes():
    from .models import Dispute

    expired_disputes = Dispute.objects.filter(
        status='pending',
        order__dispute_deadline__lte=timezone.now()
    )

    for dispute in expired_disputes:
        dispute.status = 'expired'
        dispute.save()

        # Уведомление администратора
        notify_admin.delay(
            f"Спор по заказу #{dispute.order.id} просрочен",
            f"Исполнитель не исправил работу в срок. Заказ: {dispute.order.title}"
        )

