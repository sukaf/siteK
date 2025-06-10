# orders/models.py
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from users.models import User
import os
import transliterate
import time

from decimal import Decimal


def rename_uploaded_file(instance, filename):
    name, ext = os.path.splitext(filename)
    try:
        name = transliterate.translit(name, reversed=True)
    except Exception:
        pass
    name = slugify(name)
    return f"uploads/{name}{ext}"


class Order(models.Model):
    WORK_TYPE_CHOICES = [
        ('coursework', 'Курсовая работа'),
        ('diploma', 'Дипломная работа'),
        ('essay', 'Эссе'),
        ('research', 'Реферат'),
        ('lab_work', 'Лабораторная'),
        ('other', 'Другое'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ожидает исполнителя'),
        ('price_proposed', 'Ожидает подтверждения цены'),
        ('waiting_approval', 'Ожидает подтверждения'),
        ('in_progress', 'В работе'),
        ('submitted', 'Отправлено клиенту'),
        ('approved', 'Принято клиентом'),
        ('rejected', 'Отклонено клиентом'),
        ('completed', 'Завершено'),
        ('auto_completed', 'Автоматически завершено'),
        ('refunded', 'Возврат средств'),
        ('closed', 'Закрыт'),
    ]

    TAG_CHOICES = [
        ('ready_work', 'Готовая работа'),
        ('consultation', 'Консультация'),
        ('final_touches', 'Финальные штрихи'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_orders')
    employee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='employee_orders')
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    work_type = models.CharField(max_length=20, choices=WORK_TYPE_CHOICES, default='coursework')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending')
    deadline = models.DateField(verbose_name="Срок сдачи", null=True, blank=True)
    file = models.FileField(upload_to=rename_uploaded_file, null=True, blank=True)
    tag = models.CharField(max_length=30, choices=TAG_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_file = models.FileField(upload_to='completed_orders/', null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)

    def submit_to_client(self):
        """Исполнитель отправляет заказ на проверку клиенту"""
        if self.status != 'in_progress':
            raise ValidationError("Можно отправить только заказ в статусе 'В работе'")
        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.save()


    def client_reject(self, comment=None):
        self.status = 'rejected_by_client'
        if comment:
            self.client_comment = comment
        self.save()

    def return_to_work(self):
        """Возврат заказа в работу после отклонения"""
        if self.status != 'rejected':
            raise ValidationError("Можно вернуть в работу только отклоненный заказ")
        self.status = 'in_progress'
        self.save()

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']


    def create_dispute(self, customer_comment):
        if hasattr(self, 'dispute'):
            raise ValidationError("Спор уже создан для этого заказа.")

        return Dispute.objects.create(
            order=self,
            customer_comment=customer_comment,
        )


