import re

from django.core.exceptions import ValidationError


def normalize_isbn(value):
    """Return an ISBN without spaces or hyphens, with any check digit uppercased."""
    return re.sub(r"[\s-]", "", value or "").upper()


def validate_isbn(value):
    """Validate that a normalized ISBN is either ISBN-10 or ISBN-13."""
    if not re.fullmatch(r"\d{9}[\dX]|\d{13}", normalize_isbn(value)):
        raise ValidationError(
            "Enter a valid ISBN-10 or ISBN-13 (10 or 13 characters)."
        )
