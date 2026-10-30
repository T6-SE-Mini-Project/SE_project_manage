def serialize_user(user, identity=None):
    """Account fields the frontend needs to render the signed-in state.

    ``is_staff`` drives the administrator navigation and route guards in
    the React app; the server re-checks it on every admin request.

    ``identity`` is the caller's :class:`~accounts.models.FirebaseIdentity`
    when one is known. ``uid`` is echoed back so the frontend can assert
    that the account the API resolved is the Firebase account its SDK
    currently holds — the two can only disagree if a stale token is in
    flight, and the UI should not render one customer's name over another
    customer's data.
    """
    data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "date_joined": user.date_joined.isoformat(),
        "uid": "",
        "provider": "",
        "display_name": "",
    }

    if identity is not None:
        data.update(
            {
                "uid": identity.uid,
                "provider": identity.provider,
                "display_name": identity.display_name,
            }
        )

    return data
