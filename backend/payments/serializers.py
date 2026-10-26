def serialize_payment(payment):
    """Payment representation safe to expose to clients.

    Only the last four card digits are ever included; full card numbers
    are not stored anywhere.
    """
    data = {
        "id": payment.id,
        "order_id": payment.order_id,
        "amount": f"{payment.amount:.2f}",
        "method": payment.method,
        "status": payment.status,
        "card_last4": payment.card_last4,
        "created_at": payment.created_at.isoformat(),
    }

    if payment.status == "SUCCEEDED":
        data["reference"] = payment.reference
    else:
        data["failure_reason"] = payment.failure_reason

    return data
