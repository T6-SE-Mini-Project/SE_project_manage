from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from .forms import CustomerRegistrationForm


def _safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")

    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return None


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
            next_url = _safe_next_url(request)
            if next_url:
                return redirect(next_url)
            return redirect("login_success")
    else:
        form = AuthenticationForm(request)

    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


def login_success(request):
    return render(request, "accounts/login_success.html")


@require_GET
def session_status(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"authenticated": False, "user": None}
        )

    return JsonResponse(
        {
            "authenticated": True,
            "user": {
                "id": request.user.pk,
                "username": request.user.get_username(),
                "email": request.user.email,
            },
        }
    )
