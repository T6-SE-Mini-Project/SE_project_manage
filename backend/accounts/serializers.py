def serialize_user(user):
    """Account fields the frontend needs to render the signed-in state.

    ``is_staff`` drives the administrator navigation and route guards in
    the React app; the server re-checks it on every admin request.
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "date_joined": user.date_joined.isoformat(),
    }


def serialize_form_errors(form):
    """Flatten Django form errors into ``{field: [messages]}``.

    Keeps field-level validation messages (from
    ``CustomerRegistrationForm`` and ``AuthenticationForm``) available to
    the React forms instead of collapsing them into one string.
    """
    return {field: list(messages) for field, messages in form.errors.items()}


def first_form_error(form):
    """Return a single human-readable message for a failed form."""
    for messages in form.errors.values():
        if messages:
            return messages[0]
    return "The submitted data is not valid."
