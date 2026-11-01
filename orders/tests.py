import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from books.models import Book
from .models import BillingAddress, Order

VALID_ADDRESS = {
    "full_name": "Ananya Sharma",
    "phone_number": "9876543210",
    "email": "ananya.sharma@example.com",
    "address_line1": "12 MG Road",
    "address_line2": "Near City Library",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
    "country": "India",
}


class CheckoutApiTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            title="Billing Test Book",
            author="Test Author",
            isbn="9780132350884",
            description="A book used by billing tests.",
            category="Fiction",
            price=Decimal("12.50"),
            stock_quantity=5,
        )
        self.second_book = Book.objects.create(
            title="Second Billing Book",
            author="Another Author",
            isbn="9780201633610",
            description="A second billing test book.",
            category="Nonfiction",
            price=Decimal("7.00"),
            stock_quantity=4,
        )

    def add_to_cart(self, book=None, quantity=1, client=None):
        target = client or self.client
        return target.post(
            reverse("cart_item_add"),
            data=json.dumps(
                {"book_id": (book or self.book).pk, "quantity": quantity}
            ),
            content_type="application/json",
        )

    def checkout(self, address=None, save_address=False, client=None):
        target = client or self.client
        payload = {
            "billing_address": dict(address or VALID_ADDRESS),
            "save_address": save_address,
        }
        return target.post(
            reverse("checkout"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_valid_billing_address_creates_order_and_persists(self):
        self.add_to_cart(quantity=2)

        response = self.checkout()

        self.assertEqual(response.status_code, 201)
        data = response.json()
        order = Order.objects.select_related("billing_address").get(
            pk=data["order"]["id"]
        )

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(BillingAddress.objects.count(), 1)
        self.assertIsNone(order.user)
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        self.assertEqual(order.total, Decimal("25.00"))
        self.assertEqual(
            order.billing_address.full_name,
            "Ananya Sharma",
        )
        self.assertEqual(
            order.billing_address.phone_number,
            "9876543210",
        )
        self.assertEqual(order.billing_address.postal_code, "560001")
        self.assertEqual(order.billing_address.country, "India")
        self.assertEqual(
            order.session_key,
            self.client.session.session_key,
        )

        item = order.items.get()
        self.assertEqual(item.title, "Billing Test Book")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("12.50"))
        self.assertEqual(item.subtotal, Decimal("25.00"))

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, 3)

        cart = self.client.get(reverse("cart_detail")).json()["cart"]
        self.assertEqual(cart["items"], [])

        self.assertFalse(data["address_saved"])

    def test_missing_required_fields_are_rejected(self):
        self.add_to_cart()
        address = {
            **VALID_ADDRESS,
            "full_name": "",
            "address_line1": "",
            "city": " ",
            "state": "",
            "country": "",
        }

        response = self.checkout(address=address)

        self.assertEqual(response.status_code, 400)
        errors = response.json()["errors"]

        for field in (
            "full_name",
            "address_line1",
            "city",
            "state",
            "country",
        ):
            self.assertIn(field, errors)

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(BillingAddress.objects.count(), 0)

    def test_invalid_phone_number_is_rejected(self):
        self.add_to_cart()

        for phone in ("12345", "98765abcde", "98765432101"):
            with self.subTest(phone=phone):
                response = self.checkout(
                    address={**VALID_ADDRESS, "phone_number": phone}
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    "phone_number",
                    response.json()["errors"],
                )

    def test_invalid_email_is_rejected(self):
        self.add_to_cart()

        response = self.checkout(
            address={**VALID_ADDRESS, "email": "not-an-email"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_pin_code_is_rejected(self):
        self.add_to_cart()

        for pin in ("1234", "1234567", "56A001"):
            with self.subTest(pin=pin):
                response = self.checkout(
                    address={**VALID_ADDRESS, "postal_code": pin}
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    "postal_code",
                    response.json()["errors"],
                )

    def test_phone_number_accepts_spaces_and_hyphens(self):
        self.add_to_cart()

        response = self.checkout(
            address={**VALID_ADDRESS, "phone_number": "98765-43210"}
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["order"]["billing_address"]["phone_number"],
            "9876543210",
        )

    def test_empty_cart_is_rejected(self):
        response = self.checkout()

        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["error"].lower())
        self.assertEqual(Order.objects.count(), 0)

    def test_missing_billing_address_object_is_rejected(self):
        response = self.client.post(
            reverse("checkout"),
            data=json.dumps({"save_address": False}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("billing_address", response.json()["errors"])

    def test_invalid_save_address_type_is_rejected(self):
        self.add_to_cart()

        response = self.client.post(
            reverse("checkout"),
            data=json.dumps(
                {
                    "billing_address": VALID_ADDRESS,
                    "save_address": "yes",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("save_address", response.json()["error"])

    def test_invalid_json_is_rejected(self):
        response = self.client.post(
            reverse("checkout"),
            data="{not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid JSON body.")

    def test_out_of_stock_cart_item_is_rejected(self):
        self.add_to_cart(quantity=2)
        self.book.stock_quantity = 1
        self.book.save(update_fields=["stock_quantity", "updated_at"])

        response = self.checkout()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(BillingAddress.objects.count(), 0)

        cart = self.client.get(reverse("cart_detail")).json()["cart"]
        self.assertEqual(cart["items"][0]["quantity"], 2)

    def test_authenticated_customer_can_save_and_reuse_address(self):
        user = get_user_model().objects.create_user(
            username="billingcustomer",
            email="billingcustomer@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)
        self.add_to_cart()

        first = self.checkout(save_address=True)

        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.json()["address_saved"])
        address = BillingAddress.objects.get()
        self.assertEqual(address.user, user)
        self.assertEqual(
            Order.objects.get(pk=first.json()["order"]["id"]).user,
            user,
        )

        self.add_to_cart()
        second = self.checkout(save_address=True)

        self.assertEqual(second.status_code, 201)
        self.assertTrue(second.json()["address_saved"])
        self.assertEqual(BillingAddress.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 2)

        response = self.client.get(reverse("billing_address_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["addresses"]), 1)
        self.assertEqual(
            response.json()["addresses"][0]["full_name"],
            "Ananya Sharma",
        )

    def test_guest_save_flag_does_not_create_saved_address(self):
        self.add_to_cart()

        response = self.checkout(save_address=True)

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["address_saved"])
        self.assertIsNone(BillingAddress.objects.get().user)

        listing = self.client.get(reverse("billing_address_list"))

        self.assertEqual(listing.status_code, 401)

    def test_saved_addresses_are_scoped_to_the_authenticated_customer(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(
            username="addressowner",
            password="StrongPass123!",
        )
        other = user_model.objects.create_user(
            username="otherowner",
            password="StrongPass123!",
        )
        BillingAddress.objects.create(user=owner, **VALID_ADDRESS)
        BillingAddress.objects.create(
            user=other,
            **{
                **VALID_ADDRESS,
                "full_name": "Other Customer",
                "email": "other@example.com",
            },
        )

        self.client.force_login(owner)
        response = self.client.get(reverse("billing_address_list"))

        self.assertEqual(response.status_code, 200)
        addresses = response.json()["addresses"]
        self.assertEqual(len(addresses), 1)
        self.assertEqual(addresses[0]["full_name"], "Ananya Sharma")

    def test_order_detail_is_scoped_to_the_session(self):
        self.add_to_cart()
        order_id = self.checkout().json()["order"]["id"]

        response = self.client.get(reverse("order_detail", args=[order_id]))
        self.assertEqual(response.status_code, 200)

        other_client = Client()
        response = other_client.get(
            reverse("order_detail", args=[order_id])
        )
        self.assertEqual(response.status_code, 404)

    def test_authenticated_order_is_scoped_to_the_owner(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(
            username="orderowner",
            password="StrongPass123!",
        )
        other = user_model.objects.create_user(
            username="otherorderowner",
            password="StrongPass123!",
        )

        self.client.force_login(owner)
        self.add_to_cart()
        order_id = self.checkout().json()["order"]["id"]

        self.client.force_login(other)
        response = self.client.get(
            reverse("order_detail", args=[order_id])
        )
        self.assertEqual(response.status_code, 404)

        self.client.force_login(owner)
        response = self.client.get(
            reverse("order_detail", args=[order_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order"]["id"], order_id)
