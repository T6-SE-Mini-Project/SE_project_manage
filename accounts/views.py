from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm

from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import CustomerRegistrationForm


def register(request):
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Your account has been created successfully. You can now log in.",
            )
            return redirect("register_success")
    else:
        form = CustomerRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def register_success(request):
    return render(request, "accounts/register_success.html")

def customer_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "You have logged in successfully.")
            return redirect("login_success")
    else:
        form = AuthenticationForm(request)

    return render(request, "accounts/login.html", {"form": form})


def login_success(request):
    return render(request, "accounts/login_success.html")