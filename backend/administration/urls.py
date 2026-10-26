"""Administrator API routes, mounted at /api/admin/.

Issue #12 covers the catalogue and order endpoints, issue #24 the
customer and sales-report endpoints, and issue #18 the backup execution
records. Every view here is gated by ``staff_required_api``.
"""

from django.urls import path

from . import views_backups, views_books, views_customers, views_orders
from . import views_reports

urlpatterns = [
    # Catalogue management (issue #12)
    path("books/", views_books.book_collection, name="admin_book_collection"),
    path(
        "books/<int:pk>/",
        views_books.book_detail,
        name="admin_book_detail",
    ),
    # Order management (issue #12)
    path(
        "orders/",
        views_orders.order_collection,
        name="admin_order_collection",
    ),
    path(
        "orders/<int:pk>/",
        views_orders.order_detail,
        name="admin_order_detail",
    ),
    path(
        "orders/<int:pk>/status/",
        views_orders.order_status,
        name="admin_order_status",
    ),
    path(
        "orders/<int:pk>/cancel/",
        views_orders.order_cancel,
        name="admin_order_cancel",
    ),
    # Customer management (issue #24)
    path(
        "customers/",
        views_customers.customer_collection,
        name="admin_customer_collection",
    ),
    path(
        "customers/<int:pk>/",
        views_customers.customer_detail,
        name="admin_customer_detail",
    ),
    path(
        "customers/<int:pk>/status/",
        views_customers.customer_status,
        name="admin_customer_status",
    ),
    # Sales reports (issue #24)
    path(
        "reports/sales/",
        views_reports.sales_report,
        name="admin_sales_report",
    ),
    # Backup execution records (issue #18)
    path(
        "backups/",
        views_backups.backup_collection,
        name="admin_backup_collection",
    ),
]
