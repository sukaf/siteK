from django import forms
from .models import Order
import datetime
from messaging.models import Message

class PriceProposalForm(forms.Form):
    proposed_price = forms.DecimalField(max_digits=10, decimal_places=2, label="Предложенная цена")


class OrderForm(forms.ModelForm):
    WORK_TYPE_CHOICES = [
        ('', 'Выберите тип работы'),
        ('coursework', 'Курсовая работа'),
        ('diploma', 'Дипломная работа'),
        ('essay', 'Эссе'),
        ('research', 'Реферат'),
        ('lab_work', 'Лабораторная'),
        ('other', 'Другое'),
        #('значение в базе', 'отображ. текст'),
    ]

    TAG_CHOICES = [
        ('ready_work', 'Готовая работа'),
        ('consultation', 'Консультация'),
        ('final_touches', 'Финальные штрихи'),
    ]

    work_type = forms.ChoiceField(choices=WORK_TYPE_CHOICES, required=True, widget=forms.Select(attrs={
        'class': 'form-control'
    }))
    subject = forms.CharField(max_length=255, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Введите предмет'
    }))
    title = forms.CharField(max_length=255, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Тема работы *'
    }))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Ваш e-mail *'
    }))
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'class': 'form-control', 'placeholder': 'Комментарии', 'rows': 2
    }))
    price = forms.DecimalField(max_digits=10, decimal_places=2, required=True, widget=forms.NumberInput(attrs={
        'class': 'form-control', 'placeholder': 'Введите цену *'
    }))
    file = forms.FileField(required=False, label="Прикрепить файл",
                           widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

    # Добавляем поле tag
    tag = forms.ChoiceField(choices=TAG_CHOICES, required=False, widget=forms.HiddenInput())

    deadline = forms.DateField(required=True, label="Срок сдачи",
                               widget=forms.DateInput(attrs={
                                   'class': 'form-control',
                                   'type': 'date',
                                   'min': datetime.date.today().strftime('%Y-%m-%d')
                               }))

    description = forms.CharField(required=True, label="Подробное описание",
                                  widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}))

    class Meta:
        model = Order
        fields = ['work_type', 'subject', 'title', 'description', 'email',
                  'price', 'deadline', 'file', 'tag']

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline and deadline < datetime.date.today():
            raise forms.ValidationError("Срок сдачи не может быть в прошлом")
        return deadline

    def clean_description(self):
        description = self.cleaned_data.get('description')
        if not description or description.strip() == '':
            raise forms.ValidationError("Пожалуйста, укажите описание работы")
        return description


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Введите сообщение...'})
        }


