import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from books.models import Book
from .models import Cart


class CartApiTests(TestCase):
    """TC-OBS-007, TC-OBS-008 and TC-OBS-009 for the shopping cart."""

    def setUp(self):
        self.book = Book.objects.create(
            title="Cart Book",
            author="Cart Author",
            isbn="9780132350884",
            description="A book used by cart tests.",
            category="Fiction",
            price=Decimal("12.50"),
            stock_quantity=5,
        )
        self.other_book = Book.objects.create(
            title="Second Cart Book",
            author="Another Author",
            isbn="9780201633610",
            description="A second book used by cart tests.",
            category="Nonfiction",
            price=Decimal("5.00"),
            stock_quantity=10,
        )
        self.out_of_stock_book = Book.objects.create(
            title="Unavailable Book",
            author="Another Author",
            isbn="9780134685991",
            description="A book that is out of stock.",
            category="Nonfiction",
            price=Decimal("9.99"),
            stock_quantity=0,
        )

    def add_item(self, payload):
        return self.client.post(
            reverse("cart_item_add"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def update_item(self, item_id, payload):
        return self.client.patch(
            reverse("cart_item_detail", args=[item_id]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def current_cart(self):
        response = self.client.get(reverse("cart_detail"))
        self.assertEqual(response.status_code, 200)
        return response.json()["cart"]

    def test_empty_cart_is_returned(self):
        cart = self.current_cart()

        self.assertEqual(cart["items"], [])
        self.assertEqual(cart["total"], "0.00")
        self.assertEqual(cart["item_count"], 0)

    def test_add_book_to_cart(self):
        response = self.add_item({"book_id": self.book.pk})

        self.assertEqual(response.status_code, 200)
        cart = response.json()["cart"]

        self.assertEqual(cart["item_count"], 1)
        self.assertEqual(cart["total"], "12.50")
        self.assertEqual(len(cart["items"]), 1)

        item = cart["items"][0]
        self.assertEqual(item["book"]["id"], self.book.pk)
        self.assertEqual(item["quantity"], 1)
        self.assertEqual(item["subtotal"], "12.50")

    def test_add_same_book_increments_quantity(self):
        self.add_item({"book_id": self.book.pk})
        response = self.add_item({"book_id": self.book.pk})

        self.assertEqual(response.status_code, 200)
        item = response.json()["cart"]["items"][0]

        self.assertEqual(item["quantity"], 2)

    def test_add_with_explicit_quantity(self):
        response = self.add_item(
            {"book_id": self.book.pk, "quantity": 3}
        )

        self.assertEqual(response.status_code, 200)
        cart = response.json()["cart"]

        self.assertEqual(cart["items"][0]["quantity"], 3)
        self.assertEqual(cart["total"], "37.50")

    def test_out_of_stock_book_is_rejected(self):
        response = self.add_item({"book_id": self.out_of_stock_book.pk})

        self.assertEqual(response.status_code, 400)
        self.assertIn("out of stock", response.json()["error"].lower())
        self.assertEqual(self.current_cart()["items"], [])

    def test_unknown_book_returns_404(self):
        response = self.add_item({"book_id": 999999})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_quantity_above_stock_is_rejected(self):
        response = self.add_item(
            {"book_id": self.book.pk, "quantity": 6}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.current_cart()["items"], [])

    def test_invalid_quantity_is_rejected(self):
        for quantity in (0, -1, "abc"):
            with self.subTest(quantity=quantity):
                response = self.add_item(
                    {"book_id": self.book.pk, "quantity": quantity}
                )
                self.assertEqual(response.status_code, 400)

    def test_update_cart_item_quantity(self):
        self.add_item({"book_id": self.book.pk})
        item_id = self.current_cart()["items"][0]["id"]

        response = self.update_item(item_id, {"quantity": 4})

        self.assertEqual(response.status_code, 200)
        cart = response.json()["cart"]

        self.assertEqual(cart["items"][0]["quantity"], 4)
        self.assertEqual(cart["items"][0]["subtotal"], "50.00")
        self.assertEqual(cart["total"], "50.00")

    def test_update_above_stock_is_rejected(self):
        self.add_item({"book_id": self.book.pk})
        item_id = self.current_cart()["items"][0]["id"]

        response = self.update_item(item_id, {"quantity": 6})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.current_cart()["items"][0]["quantity"],
            1,
        )

    def test_remove_cart_item(self):
        self.add_item({"book_id": self.book.pk})
        item_id = self.current_cart()["items"][0]["id"]

        response = self.client.delete(
            reverse("cart_item_detail", args=[item_id]),
        )

        self.assertEqual(response.status_code, 200)
        cart = response.json()["cart"]

        self.assertEqual(cart["items"], [])
        self.assertEqual(cart["total"], "0.00")
        self.assertEqual(cart["item_count"], 0)

    def test_authenticated_cart_is_linked_to_user(self):
        """TC-OBS-022 uses a registered customer's session."""
        user = get_user_model().objects.create_user(
            username="cartcustomer",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.add_item({"book_id": self.book.pk})

        self.assertEqual(response.status_code, 200)
        cart = Cart.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(cart.user, user)

    def test_cart_is_scoped_to_the_session(self):
        self.add_item({"book_id": self.book.pk})
        item_id = self.current_cart()["items"][0]["id"]

        other_client = Client()
        response = other_client.patch(
            reverse("cart_item_detail", args=[item_id]),
            data=json.dumps({"quantity": 2}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_total_reflects_prices_and_quantities(self):
        self.add_item({"book_id": self.book.pk, "quantity": 2})
        response = self.add_item(
            {"book_id": self.other_book.pk, "quantity": 3}
        )

        cart = response.json()["cart"]

        self.assertEqual(cart["total"], "40.00")
        self.assertEqual(cart["item_count"], 5)

        subtotals = {
            item["book"]["id"]: item["subtotal"]
            for item in cart["items"]
        }
        self.assertEqual(subtotals[self.book.pk], "25.00")
        self.assertEqual(subtotals[self.other_book.pk], "15.00")

    def test_total_updates_when_contents_change(self):
        self.add_item({"book_id": self.book.pk, "quantity": 2})
        item_id = self.current_cart()["items"][0]["id"]

        response = self.update_item(item_id, {"quantity": 1})
        self.assertEqual(response.json()["cart"]["total"], "12.50")

        response = self.client.delete(
            reverse("cart_item_detail", args=[item_id]),
        )
        self.assertEqual(response.json()["cart"]["total"], "0.00")

    def test_invalid_json_body_is_rejected(self):
        response = self.client.post(
            reverse("cart_item_add"),
            data="{not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")



class Task19SecurityObjectiveTests(CartApiTests):
    """Focused security objective validation for Task #19."""
    def test_025_other_session_cannot_read_another_carts_item(self):
        self.add_item({"book_id": self.book.pk})

        original_cart = self.current_cart()
        self.assertEqual(len(original_cart["items"]), 1)

        # A separate session must receive its own empty cart.
        other_client = Client()
        response = other_client.get(reverse("cart_detail"))

        self.assertEqual(response.status_code, 200)
        other_cart = response.json()["cart"]
        self.assertEqual(other_cart["items"], [])

        # Confirm the original session's data remains intact.
        original_cart_after = self.current_cart()
        self.assertEqual(len(original_cart_after["items"]), 1)
        self.assertEqual(
            original_cart_after["items"][0]["quantity"], 1
        )


    def test_026_other_session_cannot_modify_cart_item(self):
        self.add_item({"book_id": self.book.pk})
        item_id = self.current_cart()["items"][0]["id"]

        other_client = Client()
        response = other_client.patch(
            reverse("cart_item_detail", args=[item_id]),
            data=json.dumps({"quantity": 3}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

        # Verify persisted data, not just the response.
        from .models import CartItem

        item = CartItem.objects.get(pk=item_id)
        self.assertEqual(item.quantity, 1)

    def test_027_anonymous_user_can_access_public_catalogue(self):
        response = self.client.get(reverse("book_list"))
        self.assertEqual(response.status_code, 200)

    def test_027_authenticated_customer_can_access_catalogue(self):
        user = get_user_model().objects.create_user(
            username="task19customer",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("book_list"))
        self.assertEqual(response.status_code, 200)

    def test_027_anonymous_user_cannot_access_protected_page(self):
        response = self.client.get(reverse("login_success"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("customer_login"),
            response.url,
        )

    def test_027_authenticated_customer_can_access_protected_page(self):
        user = get_user_model().objects.create_user(
            username="task19protected",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("login_success"))

        self.assertEqual(response.status_code, 200)
