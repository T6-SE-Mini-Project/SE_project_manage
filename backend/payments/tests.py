import json
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from books.models import Book
from cart.models import Cart, CartItem
from orders.models import Order
from payments.models import Payment


SUCCESS_CARD = "4242424242424242"
DECLINED_CARD = "4000000000000002"
INSUFFICIENT_FUNDS_CARD = "4000000000009995"


def book_data(**overrides):
    data = {
        "title": "Payment Book",
        "author": "Payment Author",
        "isbn": "9780132350884",
        "description": "A book used by payment tests.",
        "category": "Fiction",
        "price": Decimal("12.50"),
        "stock_quantity": 5,
    }
    data.update(overrides)
    return data


def card_data(**overrides):
    data = {
        "card_number": SUCCESS_CARD,
        "cvc": "123",
        "expiry_month": 12,
        "expiry_year": 2099,
    }
    data.update(overrides)
    return data


class PaymentFlowTests(TestCase):
    """TC-OBS-012: payment processing and order confirmation."""

    def setUp(self):
        self.book = Book.objects.create(**book_data())
        self.other_book = Book.objects.create(
            **book_data(
                title="Second Payment Book",
                isbn="9780201633610",
                price=Decimal("5.00"),
                stock_quantity=10,
                category="Nonfiction",
            )
        )

    def add_to_cart(self, book, quantity=1):
        response = self.client.post(
            reverse("cart_item_add"),
            data=json.dumps({"book_id": book.pk, "quantity": quantity}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def place_order(self):
        response = self.client.post(reverse("order_collection"))
        self.assertEqual(response.status_code, 201)
        return response.json()["order"]

    def pay(self, payload, order_id=None):
        data = dict(payload)
        if order_id is not None:
            data["order_id"] = order_id
        return self.client.post(
            reverse("payment_create"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def order_row(self, order_id):
        return Order.objects.get(pk=order_id)

    def test_successful_payment_confirms_order(self):
        self.add_to_cart(self.book, quantity=2)
        order = self.place_order()

        response = self.pay(card_data(), order_id=order["id"])

        self.assertEqual(response.status_code, 200)
        body = response.json()

        confirmed = body["order"]
        self.assertEqual(confirmed["status"], "CONFIRMED")
        self.assertTrue(confirmed["is_confirmed"])
        self.assertEqual(confirmed["total_amount"], "25.00")

        payment = body["payment"]
        self.assertEqual(payment["status"], "SUCCEEDED")
        self.assertEqual(payment["amount"], "25.00")
        self.assertEqual(payment["card_last4"], "4242")
        self.assertTrue(payment["reference"])

        db_order = self.order_row(order["id"])
        self.assertEqual(db_order.status, Order.STATUS_CONFIRMED)

    def test_successful_payment_decrements_stock(self):
        self.add_to_cart(self.book, quantity=2)
        self.add_to_cart(self.other_book, quantity=3)
        order = self.place_order()

        response = self.pay(card_data(), order_id=order["id"])
        self.assertEqual(response.status_code, 200)

        self.book.refresh_from_db()
        self.other_book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, 3)
        self.assertEqual(self.other_book.stock_quantity, 7)

    def test_successful_payment_empties_the_cart(self):
        self.add_to_cart(self.book, quantity=2)
        order = self.place_order()

        response = self.pay(card_data(), order_id=order["id"])
        self.assertEqual(response.status_code, 200)

        cart = Cart.objects.filter(
            session_key=self.client.session.session_key
        ).first()
        self.assertTrue(cart is None or cart.items.count() == 0)

        cart_response = self.client.get(reverse("cart_detail"))
        self.assertEqual(cart_response.json()["cart"]["items"], [])

    def test_failed_payment_does_not_confirm_order(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        response = self.pay(
            card_data(card_number=DECLINED_CARD),
            order_id=order["id"],
        )

        self.assertEqual(response.status_code, 402)
        body = response.json()
        self.assertIn("declined", body["error"].lower())

        payment = body["payment"]
        self.assertEqual(payment["status"], "FAILED")
        self.assertIn("failure_reason", payment)
        self.assertNotIn("reference", payment)

        db_order = self.order_row(order["id"])
        self.assertEqual(db_order.status, Order.STATUS_PENDING)
        self.assertFalse(db_order.is_confirmed)

        # Stock and cart are untouched so the customer can retry.
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, 5)
        self.assertEqual(CartItem.objects.count(), 1)

    def test_failed_payment_attempt_is_recorded(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        self.pay(card_data(card_number=DECLINED_CARD), order_id=order["id"])

        payment = Payment.objects.get(order_id=order["id"])
        self.assertEqual(payment.status, Payment.STATUS_FAILED)
        self.assertEqual(payment.amount, Decimal("12.50"))
        self.assertEqual(payment.card_last4, "0002")

    def test_payment_can_be_retried_after_a_decline(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        declined = self.pay(
            card_data(card_number=DECLINED_CARD),
            order_id=order["id"],
        )
        self.assertEqual(declined.status_code, 402)

        retried = self.pay(card_data(), order_id=order["id"])
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(
            retried.json()["order"]["status"],
            "CONFIRMED",
        )
        self.assertEqual(Payment.objects.count(), 2)

    def test_insufficient_funds_card_is_handled(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        response = self.pay(
            card_data(card_number=INSUFFICIENT_FUNDS_CARD),
            order_id=order["id"],
        )

        self.assertEqual(response.status_code, 402)
        self.assertIn(
            "insufficient funds",
            response.json()["error"].lower(),
        )
        self.order_row(order["id"]).refresh_from_db()
        self.assertEqual(
            self.order_row(order["id"]).status,
            Order.STATUS_PENDING,
        )

    def test_invalid_card_number_is_rejected(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        for card_number in ("1234567890123456", "abcd", ""):
            with self.subTest(card_number=card_number):
                response = self.pay(
                    card_data(card_number=card_number),
                    order_id=order["id"],
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(
            self.order_row(order["id"]).status,
            Order.STATUS_PENDING,
        )

    def test_invalid_cvc_and_expiry_are_rejected(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        invalid_payloads = [
            card_data(cvc="12"),
            card_data(cvc="abcd"),
            card_data(expiry_month=13),
            card_data(expiry_month=0),
            card_data(expiry_year=2020),
            card_data(expiry_year="soon"),
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.pay(payload, order_id=order["id"])
                self.assertEqual(response.status_code, 400)

        self.assertEqual(Payment.objects.count(), 0)

    def test_confirmed_order_cannot_be_paid_again(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        first = self.pay(card_data(), order_id=order["id"])
        self.assertEqual(first.status_code, 200)

        second = self.pay(card_data(), order_id=order["id"])
        self.assertEqual(second.status_code, 409)
        self.assertIn(
            "already been confirmed",
            second.json()["error"],
        )
        self.assertEqual(
            Payment.objects.filter(status=Payment.STATUS_SUCCEEDED).count(),
            1,
        )

    def test_stock_drop_between_order_and_payment_blocks_confirmation(self):
        """Availability is re-checked when the payment is processed."""
        self.add_to_cart(self.book, quantity=3)
        order = self.place_order()

        # Another customer buys the last copies meanwhile.
        self.book.stock_quantity = 1
        self.book.save(update_fields=["stock_quantity", "updated_at"])

        response = self.pay(card_data(), order_id=order["id"])

        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertIn("no longer", body["error"])
        self.assertEqual(body["payment"]["status"], "FAILED")
        problem = body["availability"][0]
        self.assertEqual(problem["requested"], 3)
        self.assertEqual(problem["available"], 1)

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, 1)
        self.assertEqual(
            self.order_row(order["id"]).status,
            Order.STATUS_PENDING,
        )

    def test_payment_is_scoped_to_the_order_session(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        other_client = Client()
        response = other_client.post(
            reverse("payment_create"),
            data=json.dumps({"order_id": order["id"], **card_data()}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.order_row(order["id"]).status,
            Order.STATUS_PENDING,
        )

    def test_unknown_order_returns_404(self):
        response = self.pay(card_data(), order_id=999999)

        self.assertEqual(response.status_code, 404)

    def test_missing_order_id_is_rejected(self):
        response = self.pay(card_data())

        self.assertEqual(response.status_code, 400)

    def test_invalid_json_body_is_rejected(self):
        response = self.client.post(
            reverse("payment_create"),
            data="{not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_full_card_number_is_never_stored_or_returned(self):
        self.add_to_cart(self.book)
        order = self.place_order()

        response = self.pay(card_data(), order_id=order["id"])
        self.assertEqual(response.status_code, 200)

        serialized = response.json()["payment"]
        self.assertNotIn(str(SUCCESS_CARD), json.dumps(serialized))
        self.assertNotIn("card_number", serialized)

        payment = Payment.objects.get(order_id=order["id"])
        for field_value in payment.__dict__.values():
            self.assertNotEqual(str(field_value), str(SUCCESS_CARD))

    def test_payment_amount_matches_order_total(self):
        self.add_to_cart(self.book, quantity=2)
        self.add_to_cart(self.other_book, quantity=3)
        order = self.place_order()

        response = self.pay(card_data(), order_id=order["id"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment"]["amount"], "40.00")
        payment = Payment.objects.get(order_id=order["id"])
        self.assertEqual(payment.amount, Decimal("40.00"))
