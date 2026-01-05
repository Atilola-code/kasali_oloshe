from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from inventory.models import Product
from sales.models import Sale, SaleItem
from concurrent.futures import ThreadPoolExecutor

User = get_user_model()

class ConcurrentSaleTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass123", role="admin")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.product = Product.objects.create(
            name="Test Product",
            sku="SKU001",
            quantity=10,
            selling_price=100,
            cost_price=50
        )

        self.sale_payload = {
            "customer_name": "John Doe",
            "items": [
                {"product": self.product.id, "quantity": 5, "price": 100}
            ]
        }

    def make_sale(self):
        return self.client.post("/api/sales/", self.sale_payload, format="json")

    def test_concurrent_sales_reduce_stock_safely(self):
        """Ensure stock is not oversold under concurrent sales"""
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.make_sale(), range(2)))

        # Fetch updated product
        self.product.refresh_from_db()
        total_sold = SaleItem.objects.filter(product=self.product).count()

        print("Results:", [r.status_code for r in results])
        print("Remaining stock:", self.product.quantity)

        # Expect one sale to succeed, one to fail due to insufficient stock
        self.assertTrue(self.product.quantity >= 0)
        self.assertEqual(total_sold, 1)
