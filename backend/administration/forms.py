"""Forms used by the administrator catalogue API (issue #12).

A ``ModelForm`` is used rather than hand-written validation so the
administrator API enforces exactly the same rules as the Django admin
and the model itself, including the ISBN format check in
``Book.clean()``.
"""

from django import forms

from books.models import Book
from books.validators import normalize_isbn, validate_isbn


class BookForm(forms.ModelForm):
    # Declared explicitly with a wider max_length than the model field so
    # a punctuated ISBN ("978-0201616224") is accepted and normalized
    # here; the model stores the 13-character normalized form.
    isbn = forms.CharField(
        max_length=20,
        help_text="ISBN-10 or ISBN-13. Spaces and hyphens are ignored.",
    )

    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "isbn",
            "description",
            "category",
            "price",
            "stock_quantity",
            "cover_image_url",
            "publisher",
            "publication_date",
        ]

    def clean_isbn(self):
        """Normalize and validate the ISBN, and reject duplicates.

        Running the format check here rather than leaving it to
        ``Book.clean()`` attaches the message to the ``isbn`` field
        instead of the form-wide errors, so the frontend can show it next
        to the input. The model's unique constraint would raise an
        IntegrityError; this turns it into a field error too.
        """
        isbn = normalize_isbn(self.cleaned_data["isbn"])
        validate_isbn(isbn)

        duplicates = Book.objects.filter(isbn=isbn)

        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise forms.ValidationError(
                "Another book already uses this ISBN."
            )

        return isbn
