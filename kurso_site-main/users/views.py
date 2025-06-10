from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegisterForm, PriceApprovalForm
from orders.models import Order


def register_view(request):
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_customer = True  # Явно указываем, что это заказчик
            user.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('users:profile')

    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'users:profile')
            messages.success(request, f'Добро пожаловать, {username}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')

    return render(request, 'users/login.html')


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Вы успешно вышли из системы')
    return redirect('users:login')


@login_required
def profile_view(request):
    try:
        if request.user.is_customer:
            orders = Order.objects.filter(customer=request.user)
        elif request.user.is_employee:
            orders = Order.objects.filter(employee=request.user)
        else:
            orders = Order.objects.none()

    except Exception as e:
        orders = Order.objects.none()
        messages.error(request, f'Ошибка загрузки заказов: {str(e)}')

    return render(request, 'users/profile.html', {'orders': orders})


def employee_register_view(request):
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_customer = False
            user.is_employee = True
            user.save()
            login(request, user)
            messages.success(request, 'Регистрация сотрудника прошла успешно!')
            return redirect('users:profile')
    else:
        form = RegisterForm()

    return render(request, 'users/employee_register.html', {'form': form})



