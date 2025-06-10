# users/models.py
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal

class User(AbstractUser):
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        permissions = [
            ("can_request_payout", "Can request payout"),
        ]

    is_customer = models.BooleanField(default=False, verbose_name="Заказчик")
    is_employee = models.BooleanField(default=False, verbose_name="Исполнитель")
    wallet_address = models.CharField(max_length=100, blank=True, null=True, verbose_name="Кошелек")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")

    groups = models.ManyToManyField(
        Group,
        verbose_name="Группы",
        blank=True,
        related_name="custom_user_groups"
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name="Права доступа",
        blank=True,
        related_name="custom_user_permissions"
    )

    def clean(self):
        if self.is_customer and self.is_employee:
            raise ValidationError("Пользователь не может быть одновременно заказчиком и исполнителем")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.username

class Profile(models.Model):
    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), null=False)
    frozen_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), null=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00, verbose_name="Рейтинг")
    completed_orders = models.PositiveIntegerField(default=0, verbose_name="Завершенные заказы")

    @property
    def available_balance(self):
        if self.balance is None or self.frozen_balance is None:
            return Decimal('0.00')
        return self.balance - self.frozen_balance


    def deposit(self, amount):
        """Пополнение баланса"""
        if amount <= 0:
            raise ValidationError("Сумма пополнения должна быть положительной")
        with transaction.atomic():
            self.balance += amount
            self.save()
        return True

    def withdraw(self, amount):
        """Снятие средств (для внутренних операций)"""
        if amount <= 0:
            raise ValidationError("Сумма снятия должна быть положительной")
        if self.balance < amount:
            raise ValidationError("Недостаточно средств на балансе")
        with transaction.atomic():
            self.balance -= amount
            self.save()
        return True

    def can_pay(self, amount):
        return self.available_balance >= amount

    def freeze_funds(self, amount):
        """Заморозка средств для заказа"""
        if amount <= 0:
            raise ValidationError("Сумма должна быть положительной")
        if not self.can_pay(amount):
            raise ValidationError("Недостаточно средств")
        with transaction.atomic():
            self.balance -= amount
            self.frozen_balance += amount
            self.save()

    def release_funds(self, amount):
        """Разморозка средств"""
        if amount <= 0:
            raise ValidationError("Сумма должна быть положительной")
        if self.frozen_balance < amount:
            raise ValidationError("Недостаточно замороженных средств")
        with transaction.atomic():
            self.frozen_balance -= amount
            self.balance += amount
            self.save()

    def transfer_to(self, recipient_profile, amount):
        """Перевод средств другому пользователю"""
        if amount <= 0:
            raise ValidationError("Сумма перевода должна быть положительной")
        if not self.can_pay(amount):
            raise ValidationError("Недостаточно средств")
        with transaction.atomic():
            self.balance -= amount
            self.save()
            recipient_profile.balance += amount
            recipient_profile.save()

    def __str__(self):
        return f"{self.user.username} (Баланс: {self.balance} руб.)"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Сигнал для автоматического создания/обновления профиля"""
    if created:
        Profile.objects.create(user=instance)
    else:
        instance.profile.save()


