from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Этот email уже используется")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class EmployeeRegisterForm(RegisterForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_customer = False
        user.is_employee = True
        if commit:
            user.save()
        return user


class PriceApprovalForm(forms.Form):
    counter_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Ваша цена",
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control'}))


