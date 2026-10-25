
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
