"""Backfill payment state for orders placed before issue #10.

Orders confirmed by the payment flow in issue #9 already had their stock
decremented, but the ``paid_at`` and ``stock_reserved`` fields did not
exist yet. Without this backfill, cancelling one of those orders would
leave the released stock unaccounted for.
"""

from django.db import migrations


def backfill_paid_orders(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Payment = apps.get_model("payments", "Payment")

    confirmed = Order.objects.filter(status="CONFIRMED")

    for order in confirmed.iterator():
        succeeded = (
            Payment.objects.filter(order_id=order.pk, status="SUCCEEDED")
            .order_by("created_at")
            .first()
        )

        order.paid_at = (
            succeeded.created_at if succeeded is not None else order.updated_at
        )
        order.stock_reserved = True
        order.save(update_fields=["paid_at", "stock_reserved"])


def clear_paid_orders(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(status="CONFIRMED").update(
        paid_at=None,
        stock_reserved=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_order_lifecycle_and_cancellation"),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_paid_orders, clear_paid_orders),
    ]
