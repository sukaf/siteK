# messaging/models.py
from django.db import models
from orders.models import Order
from users.models import User

class Message(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(verbose_name="Текст сообщения")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время отправки")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['timestamp']

    def __str__(self):
        return f"Сообщение от {self.sender.username} ({self.timestamp})"


