from django import forms
from decimal import Decimal

class DepositForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal('50.00'),
        max_value=Decimal('50000.00'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Сумма пополнения'
        })
    )

class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(
        min_value=50,
        max_value=50000,
        label="Сумма вывода (руб.)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Минимум 50 руб.'
        })
    )
    withdrawal_method = forms.ChoiceField(
        choices=[
            ('bank_card', 'Банковская карта'),
            ('electronic_wallet', 'Электронный кошелек')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    wallet_details = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Номер карты/кошелька'
        })
    )


