# disputes/models.py
from django.db import models
from django.utils import timezone
from orders.models import Order
from users.models import User
from django.core.exceptions import ValidationError
from users.models import Profile
from django.db import transaction

class Dispute(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает решения'),
        ('resolved', 'Решен'),
    ]

    RESOLUTION_CHOICES = [
        ('customer', 'Клиент'),
        ('executor', 'Исполнитель'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispute')
    customer_comment = models.TextField()
    admin_comment = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_for = models.CharField(max_length=10, choices=RESOLUTION_CHOICES, null=True, blank=True)

    def resolve(self, admin, decision, refund_customer):
        if self.status == 'resolved':
            raise ValidationError("Этот спор уже был решен.")

        order = self.order
        order_price = order.price

        # Заблокируем профили для корректного атомарного обновления балансов
        customer_profile = Profile.objects.select_for_update().get(user=order.customer)
        employee_profile = Profile.objects.select_for_update().get(user=order.employee)

        with transaction.atomic():
            if customer_profile.frozen_balance < order_price:
                raise ValidationError("Недостаточно замороженных средств у клиента для списания")

            # Всегда уменьшаем frozen_balance у клиента
            customer_profile.frozen_balance -= order_price

            if refund_customer:
                # Возврат клиенту: разморозить средства обратно в balance
                customer_profile.balance += order_price
                self.resolved_for = 'customer'
            else:
                # Выплата исполнителю: переводим средства на баланс исполнителя
                employee_profile.balance += order_price
                self.resolved_for = 'executor'

            # Сохраняем профили
            customer_profile.save()
            if not refund_customer:
                employee_profile.save()

            # Обновляем статус спора и заказа
            self.status = 'resolved'
            self.resolved_at = timezone.now()
            self.admin_comment = f"Решено админом: {admin.username}"
            self.save()

            order.status = 'closed'
            order.save()

class DisputeMessage(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    file = models.FileField(upload_to='dispute_files/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']



