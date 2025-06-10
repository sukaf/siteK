from django.contrib import admin
from .models import User, Profile
from django.contrib import admin, messages
from .models import User, Profile
from decimal import Decimal
from django.db import transaction
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile
from decimal import Decimal
from django.db import transaction


admin.site.register(User)

admin.site.site_header = "Администрирование сайта"
admin.site.site_title = "Панель администратора"
admin.site.index_title = "Добро пожаловать в админ-панель"


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'frozen_balance', 'available_balance')
    readonly_fields = ('available_balance',)
    search_fields = ('user__username', 'user__email')
    actions = ['transfer_frozen_to_balance', 'transfer_frozen_to_employee']

    def available_balance(self, obj):
        return obj.balance - obj.frozen_balance

    available_balance.short_description = 'Доступный баланс'

    @admin.action(description="Перевести все замороженные средства на доступный баланс")
    def transfer_frozen_to_balance(self, request, queryset):
        for profile in queryset:
            if profile.frozen_balance > 0:
                with transaction.atomic():
                    profile.release_funds(profile.frozen_balance)
                    messages.success(request, f"Средства разморожены для {profile.user.username}")
            else:
                messages.warning(request, f"У {profile.user.username} нет замороженных средств.")

    @admin.action(description="Перевести замороженные средства на баланс исполнителя")
    def transfer_frozen_to_employee(self, request, queryset):
        from orders.models import Order  # импорт здесь, чтобы избежать циклических

        for profile in queryset:
            # Находим активный заказ клиента, по которому есть исполнитель
            try:
                order = Order.objects.filter(customer=profile.user, employee__isnull=False).latest('id')
            except Order.DoesNotExist:
                messages.warning(request, f"У {profile.user.username} нет подходящего заказа.")
                continue

            employee_profile = order.employee.profile
            amount = profile.frozen_balance

            if amount > 0:
                with transaction.atomic():
                    profile.frozen_balance -= amount
                    profile.save()

                    employee_profile.balance += amount
                    employee_profile.save()

                    messages.success(
                        request,
                        f"{amount} руб. переведено от {profile.user.username} к исполнителю {employee_profile.user.username}"
                    )
            else:
                messages.warning(request, f"У {profile.user.username} нет замороженных средств.")



