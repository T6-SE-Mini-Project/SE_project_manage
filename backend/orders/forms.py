"""Validation for the billing address submitted at checkout.

The React checkout page validates the same rules before submitting so the
customer sees mistakes immediately, but this form is authoritative: the API
never trusts the browser.
"""

import re

from django import forms
from django.core.exceptions import ValidationError

from .models import BillingAddress


class BillingAddressForm(forms.ModelForm):
    """Validate the ``billing_address`` object from the checkout API."""

    phone_number = forms.CharField(
        max_length=20,
        required=True,
        label="Phone number",
    )
    postal_code = forms.CharField(
        max_length=12,
        required=True,
        label="PIN code",
    )

    class Meta:
        model = BillingAddress
        fields = [
            "full_name",
            "phone_number",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
        ]

    def _clean_required_text(self, field_name, label):
        value = " ".join((self.cleaned_data.get(field_name) or "").split())

        if not value:
            raise ValidationError(f"{label} is required.")

        return value

    def clean_full_name(self):
        return self._clean_required_text("full_name", "Full name")

    def clean_phone_number(self):
        raw = (self.cleaned_data.get("phone_number") or "").strip()
        compact = re.sub(r"[\s-]", "", raw)

        if not compact:
            raise ValidationError("Phone number is required.")

        if not re.fullmatch(r"\d{10}", compact):
            raise ValidationError("Phone number must be exactly 10 digits.")

        return compact

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email:
            raise ValidationError("Email address is required.")

        return email

    def clean_address_line1(self):
        return self._clean_required_text("address_line1", "Address line 1")

    def clean_address_line2(self):
        return " ".join((self.cleaned_data.get("address_line2") or "").split())

    def clean_city(self):
        return self._clean_required_text("city", "City")

    def clean_state(self):
        return self._clean_required_text("state", "State")

    def clean_postal_code(self):
        raw = (self.cleaned_data.get("postal_code") or "").strip()
        compact = re.sub(r"\s", "", raw)

        if not compact:
            raise ValidationError("PIN code is required.")

        if not re.fullmatch(r"\d{6}", compact):
            raise ValidationError("PIN code must be exactly 6 digits.")

        return compact

    def clean_country(self):
        country = " ".join((self.cleaned_data.get("country") or "").split())

        if not country:
            raise ValidationError("Country is required.")

        return country


def form_errors(form):
    """Field errors in the shape the frontend renders."""
    return {
        field: [entry["message"] for entry in entries]
        for field, entries in form.errors.get_json_data().items()
    }
