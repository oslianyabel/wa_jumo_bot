import json
import unittest

from chatbot.core.ai_agent.tools.odoo_manager import odoo_orion
from chatbot.core.old_ai_agent import functions


class TestFetch(unittest.IsolatedAsyncioTestCase):
    async def test_get_partner_by_id(self):
        result = await odoo_orion.get_partner_by_id(353)
        expected = {
            "company_id": False,
            "email": "ALEJANDROGONZALEZ@GMAIL.COM",
            "id": 353,
            "is_company": False,
            "name": " ALEJANDRO GONZALEZ",
            "parent_id": False,
            "phone": "+57 313 4053828",
        }
        self.assertEqual(result, expected)

    async def test_get_partner_by_phone(self):
        result = await odoo_orion.get_partner_by_phone("+57 313 4053828")
        expected = {
            "company_id": False,
            "email": "ALEJANDROGONZALEZ@GMAIL.COM",
            "id": 353,
            "is_company": False,
            "name": " ALEJANDRO GONZALEZ",
            "parent_id": False,
            "phone": "+57 313 4053828",
        }
        self.assertEqual(result, expected)

    async def test_get_partner_by_email(self):
        result = await odoo_orion.get_partner_by_email("ALEJANDROGONZALEZ@GMAIL.COM")
        expected = {
            "company_id": False,
            "email": "ALEJANDROGONZALEZ@GMAIL.COM",
            "id": 353,
            "is_company": False,
            "name": " ALEJANDRO GONZALEZ",
            "parent_id": False,
            "phone": "+57 313 4053828",
        }
        self.assertEqual(result, expected)

    async def test_get_product_by_id(self):
        result = await odoo_orion.get_product_by_id(2192)
        print(result)
        expected = {
            "active": True,
            "id": 2192,
            "list_price": 375081.0,
            "name": "Silla Gamer Edifice Azul",
            "qty_available": 2.0,
            "taxes_id": [9],
            "uom_id": [1, "Units"],
        }
        self.assertIsInstance(result, dict)
        self.assertEqual(result, expected)

    async def test_get_product_by_name(self):
        result = await odoo_orion.get_product_by_id("Silla Gamer Edifice Azul")
        print(result)
        expected = {
            "active": True,
            "id": 2192,
            "list_price": 375081.0,
            "name": "Silla Gamer Edifice Azul",
            "qty_available": 2.0,
            "taxes_id": [9],
            "uom_id": [1, "Units"],
        }
        self.assertIsInstance(result, dict)
        self.assertEqual(result, expected)

    async def test_presupuestos(self):
        result = await odoo_orion.presupuestos(477953)
        print(result)
        self.assertIsInstance(json.loads(result), list)


class TestCreatePartner(unittest.IsolatedAsyncioTestCase):
    phone = 34936069261

    async def test_create_partner_already(self):
        result_data, result_status = await odoo_orion.create_partner(
            name="osliani", phone=str(self.phone)
        )
        self.assertIsInstance(result_data, dict)
        self.assertEqual(result_status, "ALREADY")

    async def test_create_partner(self):
        self.phone += 1
        result_data, result_status = await odoo_orion.create_partner(
            name="Test", phone=str(self.phone)
        )
        self.assertIsInstance(result_data, dict)
        self.assertEqual(result_status, "CREATE")


class TestSaleOrder(unittest.IsolatedAsyncioTestCase):
    async def test_create_sale_order(self):
        user_number = "+57 313 4053828"
        product_id = 2192
        product_qty = 1
        result = await functions.create_sale_order(user_number, product_id, product_qty)
        print(result)
        self.assertIsInstance(result, str)

    async def test_get_sale_order_by_id(self):
        sale_order = await odoo_orion.get_sale_order_by_id(60013)
        print(sale_order)
        self.assertIsInstance(sale_order, dict)
        self.assertEqual(sale_order["link"], "https://akivoyempresas.odoo.com/my/orders/60013")

    async def test_get_sale_order_by_name(self):
        sale_order = await odoo_orion.get_sale_order_by_name("SOD 14006349")
        print(sale_order)
        self.assertIsInstance(sale_order, dict)
        self.assertEqual(sale_order["link"], "https://akivoyempresas.odoo.com/my/orders/60013")


class TestCreateLead(unittest.IsolatedAsyncioTestCase):
    async def test_create_lead(self):
        user_number = "3057673272"
        result = await functions.create_lead(user_number, "Test", "test@gmail.com")
        print(result)
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
