from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.html import format_html
from django import forms

from disputes.models import Dispute
from orders.models import Order


class DisputeResolutionForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ['resolved_for', 'admin_comment']

    def clean_resolved_for(self):
        resolved_for = self.cleaned_data.get('resolved_for')
        if resolved_for not in ['customer', 'executor']:
            raise forms.ValidationError("Некорректное значение для 'resolved_for'.")
        return resolved_for


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ['custom_id_link', 'order', 'status', 'resolved_at']
    readonly_fields = ['resolve_link']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:dispute_id>/resolve/',
                self.admin_site.admin_view(self.resolve_dispute),
                name='resolve_dispute'  # <--- это важно
            ),
        ]
        return custom_urls + urls

    def custom_id_link(self, obj):
        url = reverse('admin:resolve_dispute', args=[obj.id])
        return format_html('<a href="{}">#{}</a>', url, obj.id)

    custom_id_link.short_description = "ID спора"
    custom_id_link.admin_order_field = 'id'


    def resolve_dispute(self, request, dispute_id):
        dispute = get_object_or_404(Dispute, id=dispute_id)
        if request.method == 'POST':
            decision = request.POST.get('decision')
            comment = request.POST.get('admin_comment', '')

            try:
                # Вызов твоего метода resolve
                refund_customer = decision == 'customer'
                dispute.resolve(admin=request.user, decision=decision, refund_customer=refund_customer)
                dispute.admin_comment = comment
                dispute.save()

                messages.success(
                    request,
                    f"Спор #{dispute.id} успешно решён в пользу "
                    f"{'клиента' if refund_customer else 'исполнителя'}."
                )
                return redirect(f'/admin/disputes/dispute/{dispute.id}/change/')
            except Exception as e:
                messages.error(request, f"Ошибка: {e}")

        return render(request, 'admin/resolve_dispute.html', {
            'dispute': dispute,
            'order': dispute.order,
        })

    def resolve_link(self, obj):
        url = reverse('admin:disputes_dispute_resolve_dispute', args=[obj.id])
        return format_html('<a class="button" href="{}">Перейти к разрешению</a>', url)
    resolve_link.short_description = "Разрешить спор"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'status', 'customer', 'employee', 'has_dispute')
    list_filter = ('status', 'work_type')
    search_fields = ('title', 'description', 'customer__username', 'employee__username')
    readonly_fields = ('dispute_link',)

    def has_dispute(self, obj):
        return hasattr(obj, 'dispute')
    has_dispute.boolean = True
    has_dispute.short_description = 'Спор'

    def dispute_link(self, obj):
        if hasattr(obj, 'dispute'):
            return format_html(
                '<a href="{}" style="background-color: #ffc107; padding: 2px 5px; border-radius: 3px;">'
                'Разрешить спор</a>',
                reverse('admin:resolve_dispute', args=[obj.dispute.id])
            )
        return "-"

    dispute_link.short_description = 'Спор'















