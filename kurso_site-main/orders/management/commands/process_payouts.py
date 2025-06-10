from django.core.management.base import BaseCommand
from django.utils.timezone import now
from orders.models import Order


class Command(BaseCommand):
    help = "Автоматически переводит деньги исполнителям за завершенные заказы"

    def handle(self, *args, **kwargs):
        orders = Order.objects.filter(status='waiting_approval', payout_due_date__lte=now())

        for order in orders:
            if order.auto_payout():
                self.stdout.write(self.style.SUCCESS(f"Заказ {order.id} успешно оплачен."))
            else:
                self.stdout.write(self.style.WARNING(f"Не удалось обработать заказ {order.id}."))

