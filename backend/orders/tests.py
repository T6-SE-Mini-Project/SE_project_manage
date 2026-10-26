import json
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from books.models import Book
from cart.models import Cart
from .models import Order, OrderItem
from .services import _availability_problems


def book_data(**overrides):
    data = {
        "title": "Order Book",
        "author": "Order Author",
        "isbn": "9780132350884",
        "description": "A book used by order tests.",
        "category": "Fiction",
        "price": Decimal("12.50"),
        "stock_quantity": 5,
    }
    data.update(overrides)
    return data


class OrderApiTests(TestCase):
    """TC-OBS-010: order placement and availability checking."""

    def setUp(self):
        self.book = Book.objects.create(**book_data())
        self.other_book = Book.objects.create(
            **book_data(
                title="Second Order Book",
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
        return self.client.post(reverse("order_collection"))

    def current_order(self):
        response = self.client.get(reverse("order_collection"))
        self.assertEqual(response.status_code, 200)
        orders = response.json()["orders"]
        return orders[0] if orders else None

    def test_place_order_from_cart(self):
        self.add_to_cart(self.book, quantity=2)
        self.add_to_cart(self.other_book, quantity=3)

        response = self.place_order()

        self.assertEqual(response.status_code, 201)
        order = response.json()["order"]

        self.assertEqual(order["status"], "PENDING")
        self.assertFalse(order["is_confirmed"])
        self.assertEqual(order["total_amount"], "40.00")
        self.assertEqual(order["item_count"], 5)
        self.assertEqual(len(order["items"]), 2)

        first = order["items"][0]
        self.assertEqual(first["book_id"], self.book.pk)
        self.assertEqual(first["title"], self.book.title)
        self.assertEqual(first["unit_price"], "12.50")
        self.assertEqual(first["quantity"], 2)
        self.assertEqual(first["line_total"], "25.00")

        # The order is recorded for further processing (payment).
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 2)

    def test_cart_is_kept_after_placement(self):
        """The cart survives placement so a failed payment can be retried."""
        self.add_to_cart(self.book, quantity=2)

        response = self.place_order()
        self.assertEqual(response.status_code, 201)

        cart_response = self.client.get(reverse("cart_detail"))
        cart = cart_response.json()["cart"]
        self.assertEqual(cart["item_count"], 2)

    def test_empty_cart_cannot_place_order(self):
        response = self.place_order()

        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertIn("error", body)
        self.assertIn(
            "empty",
            body["availability"][0]["reason"].lower(),
        )
        self.assertEqual(Order.objects.count(), 0)

    def test_availability_is_checked_before_order_is_created(self):
        """Stock dropping below the cart quantity blocks the order."""
        self.add_to_cart(self.book, quantity=3)

        self.book.stock_quantity = 1
        self.book.save(update_fields=["stock_quantity", "updated_at"])

        response = self.place_order()

        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertIn("not available", body["error"])
        problem = body["availability"][0]
        self.assertEqual(problem["book_id"], self.book.pk)
        self.assertEqual(problem["requested"], 3)
        self.assertEqual(problem["available"], 1)
        self.assertEqual(Order.objects.count(), 0)

    def test_out_of_stock_book_blocks_order(self):
        self.add_to_cart(self.book)

        self.book.stock_quantity = 0
        self.book.save(update_fields=["stock_quantity", "updated_at"])

        response = self.place_order()

        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "out of stock",
            response.json()["availability"][0]["reason"].lower(),
        )
        self.assertEqual(Order.objects.count(), 0)

    def test_removed_book_blocks_order(self):
        """Deleting a book cascades its cart line away; the order is blocked.

        The cart becomes empty, so placement fails on the empty-cart rule
        (the defensive "no longer in the catalogue" branch is covered by
        AvailabilityLogicTests).
        """
        self.add_to_cart(self.book)
        self.book.delete()

        response = self.place_order()

        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "empty",
            response.json()["availability"][0]["reason"].lower(),
        )
        self.assertEqual(Order.objects.count(), 0)

    def test_availability_check_is_all_or_nothing(self):
        """One unavailable line blocks the whole order."""
        self.add_to_cart(self.book, quantity=1)
        self.add_to_cart(self.other_book, quantity=2)

        self.other_book.stock_quantity = 1
        self.other_book.save(update_fields=["stock_quantity", "updated_at"])

        response = self.place_order()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Order.objects.count(), 0)

    def test_availability_endpoint_reports_cart_problems(self):
        self.add_to_cart(self.book, quantity=2)

        ok = self.client.get(reverse("order_availability"))
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["available"])
        self.assertEqual(ok.json()["problems"], [])

        self.book.stock_quantity = 1
        self.book.save(update_fields=["stock_quantity", "updated_at"])

        blocked = self.client.get(reverse("order_availability"))
        self.assertEqual(blocked.status_code, 200)
        self.assertFalse(blocked.json()["available"])
        self.assertEqual(len(blocked.json()["problems"]), 1)

    def test_order_list_returns_session_orders(self):
        self.add_to_cart(self.book)
        self.place_order()

        response = self.client.get(reverse("order_collection"))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["orders"][0]["status"], "PENDING")
        self.assertEqual(body["orders"][0]["total_amount"], "12.50")
        self.assertEqual(body["orders"][0]["item_count"], 1)

    def test_order_detail_returns_items(self):
        self.add_to_cart(self.book, quantity=2)
        order_id = self.place_order().json()["order"]["id"]

        response = self.client.get(
            reverse("order_detail", args=[order_id])
        )

        self.assertEqual(response.status_code, 200)
        order = response.json()["order"]
        self.assertEqual(order["id"], order_id)
        self.assertEqual(len(order["items"]), 1)
        self.assertEqual(order["items"][0]["quantity"], 2)

    def test_unknown_order_returns_404(self):
        response = self.client.get(reverse("order_detail", args=[999999]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_order_is_scoped_to_the_session(self):
        self.add_to_cart(self.book)
        order_id = self.place_order().json()["order"]["id"]

        other_client = Client()
        response = other_client.get(
            reverse("order_detail", args=[order_id])
        )

        self.assertEqual(response.status_code, 404)

    def test_order_snapshots_price_and_title(self):
        self.add_to_cart(self.book)
        order_id = self.place_order().json()["order"]["id"]

        self.book.price = Decimal("99.00")
        self.book.title = "Renamed Title"
        self.book.save()

        response = self.client.get(
            reverse("order_detail", args=[order_id])
        )
        item = response.json()["order"]["items"][0]

        self.assertEqual(item["unit_price"], "12.50")
        self.assertEqual(item["title"], "Order Book")
        self.assertEqual(response.json()["order"]["total_amount"], "12.50")

    def test_authenticated_order_is_linked_to_user(self):
        user = get_user_model().objects.create_user(
            username="ordercustomer",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        self.add_to_cart(self.book)
        response = self.place_order()

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(order.user, user)

    def test_order_uses_the_session_cart(self):
        """Orders are created from the cart tied to the current session."""
        self.add_to_cart(self.book)
        cart = Cart.objects.get(session_key=self.client.session.session_key)

        self.place_order()

        order = Order.objects.get()
        self.assertEqual(order.session_key, cart.session_key)
        self.assertEqual(order.status, Order.STATUS_PENDING)

    def test_unsupported_methods_are_rejected(self):
        response = self.client.put(reverse("order_collection"))

        self.assertEqual(response.status_code, 405)


class AvailabilityLogicTests(TestCase):
    """Unit coverage for the availability rules that the API relies on."""

    def test_missing_book_is_reported(self):
        """A cart line whose book vanished is reported as unavailable."""
        item = SimpleNamespace(book_id=42, quantity=2)

        problems = _availability_problems([item], {})

        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["book_id"], 42)
        self.assertIn(
            "no longer in the catalogue",
            problems[0]["reason"],
        )

    def test_available_cart_reports_no_problems(self):
        book = SimpleNamespace(pk=7, title="Available Book", stock_quantity=5)
        item = SimpleNamespace(book_id=7, quantity=2)

        problems = _availability_problems([item], {7: book})

        self.assertEqual(problems, [])
