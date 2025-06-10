# payments/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from orders.models import Order
from users.models import User
import logging

logger = logging.getLogger(__name__)


from django.db import models
from django.conf import settings

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Пополнение'),
        ('withdrawal', 'Вывод'),
        ('payout', 'Выплата за заказ'),
        ('income', 'Доход исполнителя'),
        ('commission', 'Комиссия'),
        ('refund', 'Возврат'),
        ('freeze', 'Заморозка средств'),
    )

    STATUS_CHOICES = (
        ('pending', 'В обработке'),
        ('succeeded', 'Успешно'),
        ('failed', 'Неудачно'),
        ('refunded', 'Возвращено'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    profile = models.ForeignKey('users.Profile', on_delete=models.CASCADE, null=True, blank=True)  # Добавлено
    stripe_session_id = models.CharField(max_length=100, blank=True, null=True)  # Добавляем это поле

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    payment_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    description = models.TextField(
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['transaction_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} | {self.amount} ₽ | {self.user}"

    def save(self, *args, **kwargs):
        if not self.description:
            self.description = f"{self.get_transaction_type_display()} на сумму {self.amount} ₽"
        super().save(*args, **kwargs)

    @property
    def is_successful(self):
        return self.status == 'succeeded'


class PayoutRequest(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payout_requests")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'В ожидании'), ('approved', 'Одобрено'), ('rejected', 'Отклонено')],
        default='pending'
    )
    comment = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Запрос на выплату'
        verbose_name_plural = 'Запросы на выплату'
        ordering = ['-created_at']

class PriceProposal(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='price_proposals')
    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    proposed_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('order', 'employee')






