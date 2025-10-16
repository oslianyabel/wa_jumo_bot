import asyncio
import base64
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiofiles
import aiohttp
from aiohttp import BasicAuth

from chatbot.config import config
from chatbot.logging_conf import logger


class OdooHttpException(Exception):
    pass


class OdooClient:
    def __init__(
        self,
        ODOO_URL,
        CLIENT_ID,
        CLIENT_SECRET,
        SEARCH_PATH,
        CREATE_PATH,
        TOKEN_PATH,
    ):
        self.__ODOO_URL = ODOO_URL
        self.__CLIENT_ID = CLIENT_ID
        self.__CLIENT_SECRET = CLIENT_SECRET
        self.__SEARCH_PATH = SEARCH_PATH
        self.__CREATE_PATH = CREATE_PATH
        self.__TOKEN_PATH = TOKEN_PATH

        self.__SEARCH_URL = f"{self.__ODOO_URL}{self.__SEARCH_PATH}"
        self.__CREATE_URL = f"{self.__ODOO_URL}{self.__CREATE_PATH}"
        self.__TOKEN_URL = f"{self.__ODOO_URL}{self.__TOKEN_PATH}"

        # Token management
        self.__access_token: Optional[str] = None
        self.__token_expires_at: Optional[datetime] = None
        self.__token_buffer_seconds = 300  # Renovar token 5 minutos antes de expirar

    async def http_get(self, url, headers, params):
        msg = f"URL: {url}\n"
        msg += f"headers: {headers}\n"
        msg += f"params: {params}\n"
        logger.debug(f"Get http request\n{msg}")
        async with aiohttp.ClientSession() as session:
            args = {"url": url, "headers": headers, "params": params}

            async with session.get(**args) as response:
                if response.ok:
                    return await response.json()
                else:
                    raise OdooHttpException(response.text)

    async def http_post_json(self, url, headers, json):
        msg = f"URL: {url}\n"
        msg += f"headers: {headers}\n"
        msg += f"json: {json}\n"
        logger.debug(f"Post http request\n{msg}")
        async with aiohttp.ClientSession() as session:
            args = {"url": url, "headers": headers, "json": json}

            async with session.post(**args) as response:
                logger.debug(response.status)
                if response.ok:
                    return await response.json()
                else:
                    raise OdooHttpException(response.text)

    async def http_post_data(self, url, headers, data):
        msg = f"URL: {url}\n"
        msg += f"headers: {headers}\n"
        msg += f"data: {data}\n"
        logger.debug(f"Post http request\n{msg}")
        async with aiohttp.ClientSession() as session:
            args = {"url": url, "headers": headers, "data": data}

            async with session.post(**args) as response:
                logger.debug(f"status code: {response.status}")
                if response.ok:
                    return await response.json()
                else:
                    raise OdooHttpException(response.text)

    async def http_post_auth(self, url, data, auth):
        """Authenticate and get OAuth token from Odoo API.

        Args:
            url: Token endpoint URL
            data: Authentication data
            auth: Basic auth credentials

        Returns:
            str: Access token

        Raises:
            Exception: If authentication fails
        """
        async with aiohttp.ClientSession() as session:
            args = {"url": url, "data": data, "auth": auth}

            async with session.post(**args) as response:
                if response.status == 200:
                    token_data = await response.json()
                    access_token = token_data["access_token"]
                    expires_in = token_data.get("expires_in", 3600)  # Default 1 hour

                    # Store token and calculate expiration time
                    self.__access_token = access_token
                    self.__token_expires_at = datetime.now() + timedelta(
                        seconds=expires_in
                    )

                    logger.info(
                        f"Token obtenido exitosamente. Expira en: {self.__token_expires_at}"
                    )
                    return access_token
                else:
                    error_text = await response.text()
                    raise Exception(f"Error al obtener el token Odoo: {error_text}")

    def _is_token_expired(self) -> bool:
        """Check if the current token is expired or about to expire.

        Returns:
            bool: True if token is expired or will expire soon
        """
        if not self.__access_token or not self.__token_expires_at:
            return True

        # Consider token expired if it expires within the buffer time
        buffer_time = datetime.now() + timedelta(seconds=self.__token_buffer_seconds)
        return self.__token_expires_at <= buffer_time

    async def _ensure_valid_token(self) -> str:
        """Ensure we have a valid, non-expired token.

        Returns:
            str: Valid access token

        Raises:
            Exception: If unable to obtain a valid token
        """
        if self._is_token_expired():
            logger.debug("Token expirado o próximo a expirar, renovando...")
            await self.get_oauth_token()

        if not self.__access_token:
            raise Exception("No se pudo obtener un token válido")

        return self.__access_token

    async def get_oauth_token(self) -> str:
        """Get a new OAuth token from Odoo API.

        Returns:
            str: Access token
        """
        logger.debug("Obteniendo nuevo token de Odoo...")
        data = {"grant_type": "client_credentials"}
        auth = BasicAuth(self.__CLIENT_ID, self.__CLIENT_SECRET)
        return await self.http_post_auth(self.__TOKEN_URL, data, auth)

    async def _make_authenticated_request(self, request_func, *args, **kwargs):
        """Make an authenticated request with automatic token renewal on 401 errors.

        Args:
            request_func: The function to call (http_get, http_post_data, etc.)
            *args: Arguments to pass to the request function
            **kwargs: Keyword arguments to pass to the request function

        Returns:
            Response from the API

        Raises:
            Exception: If request fails after token renewal attempt
        """
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Ensure we have a valid token
                token = await self._ensure_valid_token()

                # Update headers with current token if they exist in kwargs
                if "headers" in kwargs:
                    kwargs["headers"]["Authorization"] = f"Bearer {token}"
                elif len(args) > 1:  # For positional arguments
                    # This handles cases where headers is the second argument
                    args = list(args)
                    if isinstance(args[1], dict):
                        args[1]["Authorization"] = f"Bearer {token}"
                    args = tuple(args)

                return await request_func(*args, **kwargs)

            except Exception as e:
                error_msg = str(e).lower()

                # Check if it's an authentication error
                if (
                    "401" in error_msg
                    or "unauthorized" in error_msg
                    or "invalid_token" in error_msg
                    or "token_expired" in error_msg
                ):
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Token inválido detectado, renovando... (intento {attempt + 1})"
                        )
                        # Force token renewal
                        self.__access_token = None
                        self.__token_expires_at = None
                        continue
                    else:
                        logger.error(
                            "Falló la renovación del token después de múltiples intentos"
                        )
                        raise Exception(f"Error de autenticación persistente: {e}")
                else:
                    # Not an auth error, re-raise immediately
                    raise e

        raise Exception("Se agotaron los intentos de autenticación")

    async def create_odoo(self, model, args):
        """Create a record in Odoo with automatic token management.

        Args:
            model: Odoo model name
            args: Arguments for record creation

        Returns:
            Created record data
        """
        headers = {
            "Authorization": "Bearer placeholder"
        }  # Will be updated by _make_authenticated_request
        data = {
            "model": model,
            "method": "create",
            "args": args,
        }

        return await self._make_authenticated_request(
            self.http_post_data, self.__CREATE_URL, headers, data
        )

    async def fetch_odoo(
        self,
        model,
        fields,
        domain,
        order=None,
        limit=None,
        group_by=None,
        cookie=None,
    ):
        """Fetch records from Odoo with automatic token management.

        Args:
            model: Odoo model name
            fields: Fields to retrieve
            domain: Search domain
            order: Sort order
            limit: Maximum number of records
            group_by: Group by field
            cookie: Optional cookie for session

        Returns:
            List of records from Odoo
        """
        headers = {
            "Authorization": "Bearer placeholder",  # Will be updated by _make_authenticated_request
        }
        if cookie:
            headers["Cookie"] = cookie

        params = {
            "model": model,
            "fields": fields,
            "domain": domain,
        }
        if order:
            params["order"] = order
        if limit:
            params["limit"] = limit
        if group_by:
            params["group_by"] = group_by

        return await self._make_authenticated_request(
            self.http_get, self.__SEARCH_URL, headers, params
        )

    async def get_report(
        self,
        sale_order_id,
        raw=None,
        cookie=None,
    ):
        headers = {
            "Authorization": f"Bearer {self.__access_token}",
        }
        if cookie:
            headers["Cookie"] = cookie

        if raw:
            endpoint = f"/api/v2/report/sale.report_saleorder_raw?ids=%5B{sale_order_id}%5D&type=PDF"
        else:
            endpoint = f"/api/v2/report/sale.report_saleorder?ids=%5B{sale_order_id}%5D&type=PDF"

        url = config.ODOO_URL + endpoint  # type: ignore

        report = await self._make_authenticated_request(self.http_get, url, headers, {})

        report_binary = base64.b64decode(report["content"])
        path = f"static/reports/{sale_order_id}.pdf"
        async with aiofiles.open(path, "wb") as f:
            await f.write(report_binary)

        return path


class OdooOrion(OdooClient):
    def __init__(self):
        super().__init__(
            ODOO_URL=config.ODOO_URL,
            CLIENT_ID=config.ODOO_CLIENT_ID,
            CLIENT_SECRET=config.ODOO_CLIENT_SECRET,
            SEARCH_PATH=config.SEARCH_PATH,
            CREATE_PATH=config.CREATE_PATH,
            TOKEN_PATH=config.TOKEN_PATH,
        )

    async def get_partner(self, phone=False, email=False, id=False) -> dict | None:
        fields = json.dumps(
            [
                "id",
                "name",
                "company_type",
                "parent_id",
                "phone",
                "email",
                "website",
                "mobile",
                "street",
                "city",
                "street2",
                "zip",
                "country_id",
                "state_id",
                "vat",
                "company_id",
                "customer_rank",
                "supplier_rank",
                "credit",
                "debit",
                "category_id",
                "lang",
                "industry_id",
                "type",
                "is_company",
            ]
        )
        domain = json.dumps(
            [["name", "!=", ""], ["email", "!=", ""], ["phone", "!=", ""]]
        )
        if phone:
            domain = json.dumps([["phone", "=", phone]])
        elif email:
            domain = json.dumps([["email", "=", email]])
        elif id:
            domain = json.dumps([["id", "=", id]])

        partners = await self.fetch_odoo("res.partner", fields, domain, limit=1)
        if partners:
            return partners[0]

        logger.warning(f"No se encontró ningún partner con el teléfono {phone}")
        return None

    async def get_partner_by_id(self, id):
        logger.debug(f"get_partner_by_id {id}")
        return await self.get_partner(id=id)

    async def get_partner_by_phone(self, phone):
        logger.debug(f"get_partner_by_phone {phone}")
        return await self.get_partner(phone=phone)

    async def get_partner_by_email(self, email):
        logger.debug(f"get_partner_by_email {email}")
        return await self.get_partner(email=email)

    async def get_product(
        self, id=None, sku=None, name=None, image=False, template_first=True
    ) -> dict | None:
        async def process_product():
            if image:
                if product_data[0]["image_1024"]:
                    asyncio.create_task(
                        self.download_image(
                            product_data[0]["image_1024"],
                            product_data[0]["default_code"],
                        )
                    )
                    product_data[0]["has_image"] = True
                else:
                    product_data[0]["has_image"] = False

                product_data[0].pop("image_1024")

            return product_data[0]

        fields = [
            "id",
            "name",
            "default_code",
            "barcode",
            "categ_id",
            "brand_name",
            "qty_available",
            "out_of_stock_message",
            "list_price",
            "currency_id",
            "compare_list_price",
            "tax_string",
            "description_sale",
            "invoice_policy",
            "allow_out_of_stock_order",
            "is_published",
            "type",
            "active",
        ]

        if image:
            fields.append("image_1024")

        fields = json.dumps(fields)
        domain = json.dumps([["active", "=", True]])

        if sku:
            domain = json.dumps([["default_code", "=", sku]])
        elif name:
            name = name.replace(" ", "%")
            name = f"%{name}%"
            domain = json.dumps([["name", "ilike", name]])
        elif id:
            domain = json.dumps([["id", "=", id]])

        models = []
        if template_first:
            models = ["product.template", "product.product"]
        else:
            models = ["product.product", "product.template"]

        for m in models:
            product_data = await self.fetch_odoo(m, fields, domain, limit=1)
            if product_data:
                ans = await process_product()
                return ans

        return None

    async def download_image(self, image_base64, sku):
        if not image_base64:
            logger.warning(f"La imagen del producto con sku {sku} no existe")
            return

        logger.debug(f"Descargando imagen del producto con sku {sku}...")
        image_binary = base64.b64decode(image_base64)
        path = f"static/images/{sku}.jpg"

        async with aiofiles.open(path, "wb") as f:
            await f.write(image_binary)

        logger.info(f"Imagen descargada y guardada en {path}")
        return path

    async def get_all_products(self) -> list[dict] | None:
        fields = json.dumps(
            [
                "default_code",
                "name",
                "list_price",
                "qty_available",
                "categ_id",
                "active",
            ]
        )
        domain = json.dumps([["active", "=", True]])
        product_data = await self.fetch_odoo(
            "product.product", fields, domain, order="id"
        )
        if product_data:
            return product_data

        return None

    async def get_product_by_sku(
        self, sku, image=False, template_first=True
    ) -> dict | None:
        return await self.get_product(
            sku=sku, image=image, template_first=template_first
        )

    async def get_product_by_name(self, name, image=False) -> list[dict]:
        logger.debug(f"get_product_by_name({name}, image={image}) -> list")

        fields = [
            "id",
            "name",
            "default_code",
            "barcode",
            "categ_id",
            "brand_name",
            "qty_available",
            "out_of_stock_message",
            "list_price",
            "currency_id",
            "compare_list_price",
            "tax_string",
            "description_sale",
            "invoice_policy",
            "allow_out_of_stock_order",
            "is_published",
            "type",
            "active",
        ]

        if image:
            fields.append("image_1024")

        fields_json = json.dumps(fields)

        # Build domain for ilike search
        name_q = name.replace(" ", "%")
        name_q = f"%{name_q}%"
        domain_json = json.dumps([["name", "ilike", name_q], ["active", "=", True]])

        # Search both template and product variants, with a reasonable limit
        products: list[dict] = []
        tmpl = await self.fetch_odoo(
            "product.template", fields_json, domain_json, limit=100
        )
        if tmpl:
            products.extend(tmpl)
        variants = await self.fetch_odoo(
            "product.product", fields_json, domain_json, limit=100
        )
        if variants:
            products.extend(variants)

        # De-duplicate by id to avoid overlaps between template and variant queries
        seen = set()
        unique_products = []
        for p in products:
            pid = p.get("id")
            if pid in seen:
                continue

            seen.add(pid)
            if image:
                if p["image_1024"]:
                    asyncio.create_task(
                        self.download_image(p["image_1024"], p["default_code"])
                    )
                    p["image"] = "Disponible"
                else:
                    p["image"] = "No image"

                p.pop("image_1024", None)

            unique_products.append(p)

        logger.debug(f"get_product_by_name -> {len(unique_products)} productos")
        return unique_products

    async def get_product_by_id(self, id, image=False) -> dict | None:
        return await self.get_product(id=id, image=image)

    async def get_sale_order(self, name=None, id=None) -> dict | None:
        domain = json.dumps([["amount_total", ">", 0]])
        if name:
            domain = json.dumps([["name", "ilike", name]])
        elif id:
            domain = json.dumps([["id", "=", id]])
        fields = json.dumps(
            [
                "id",
                "name",
                "partner_id",
                "date_order",
                "order_line",
                "state",
                "amount_total",
                "user_id",
                "company_id",
                "access_token",
                "access_url",
            ]
        )

        sale_orders = await self.fetch_odoo("sale.order", fields, domain, limit=1)
        if sale_orders:
            link = config.ODOO_URL + str(sale_orders[0]["access_url"])  # type: ignore
            if sale_orders[0]["access_token"]:
                link += "?access_token=" + str(sale_orders[0]["access_token"])

            sale_orders[0]["link"] = link
            return sale_orders[0]
        else:
            logger.warning(f"No se encontró el pedido {name}")
            return None

    async def get_sale_order_by_name(self, name) -> dict | None:
        return await self.get_sale_order(name=name)

    async def get_sale_order_by_id(self, id) -> dict | None:
        return await self.get_sale_order(id=id)

    async def verify_order(self, order, partner_id):
        real_order = await self.get_sale_order_by_name(order["name"])
        # verifica que el pedido le pertenezca al partner
        if real_order and real_order["partner_id"][0] == partner_id:
            return order

        logger.warning(
            f"No se pudo verificar que el pedido {order['name']} pertenece al usuario"
        )
        return None

    async def presupuestos(self, partner_id) -> list[dict] | None:
        domain = json.dumps([["partner_id", "=", partner_id]])
        fields = json.dumps(
            [
                "id",
                "name",
                "partner_id",
                "date_order",
                "order_line",
                "state",
                "amount_total",
                "user_id",
                "company_id",
                "access_token",
                "access_url",
            ]
        )

        orders = await self.fetch_odoo("sale.order", fields, domain)
        for order in orders:
            link = config.ODOO_URL + str(order["access_url"])  # type: ignore
            if order["access_token"]:
                link += "?access_token=" + str(order["access_token"])

            order["link"] = link

        return orders

        # problema raro pasado
        if orders:
            tasks = [self.verify_order(order, partner_id) for order in orders]
            results = await asyncio.gather(*tasks)
            verified_orders = [order for order in results if order is not None]
            return verified_orders

        return None

    async def create_lead(self, partner, resume, email) -> dict:
        args = json.dumps(
            [
                {
                    "stage_id": 1,
                    "type": "opportunity",
                    "name": f"WhatsApp - {partner['name']}",
                    "email_from": email,
                    "phone": partner["phone"],
                    "description": resume,
                    "partner_id": partner["id"],
                }
            ]
        )

        lead_info = await self.create_odoo("crm.lead", args)
        logger.info(f"Lead creado: {lead_info}")
        return lead_info

    async def create_partner(self, name, phone, email=None) -> tuple[dict | None, str]:
        partner = await self.get_partner_by_phone(phone)
        if partner:
            logger.debug(f"Partner found: {partner}")
            return partner, "ALREADY"

        args = [{}]
        args[0]["name"] = name
        args[0]["phone"] = phone
        if email:
            args[0]["email"] = email

        await self.create_odoo("res.partner", json.dumps(args))
        partner = await self.get_partner_by_phone(phone)
        if partner:
            logger.debug(f"Partner created: {partner}")
            return partner, "CREATE"

        logger.error(f"Error asignando teléfono {phone} al nuevo partner {name}")
        return None, "ERROR"

    async def create_sale_order(self, partner_id, order_line) -> int:
        logger.debug("Creando pedido...")
        order_line_commands = [(0, 0, line) for line in order_line]
        args = json.dumps(
            [
                {
                    "partner_id": partner_id,
                    "order_line": order_line_commands,
                    "company_id": 1,
                    "access_token": str(uuid.uuid4()),
                }
            ]
        )

        sale_order = await self.create_odoo("sale.order", args)
        logger.debug(f"Pedido creado: {sale_order}")
        return sale_order

    async def create_order_line(self, products):
        logger.debug("Creating order lines...")
        order_line = []
        try:
            for p in products:
                odoo_product = await self.get_product_by_sku(p["default_code"])
                if not odoo_product:
                    logger.warning(f"Product with sku {p['default_code']} not exists")
                    continue
                if odoo_product["qty_available"] < 1:
                    logger.warning(
                        f"product {p['name']} with sku: {p['default_code']} out of stock"
                    )
                    continue

                order_line.append(
                    {
                        "product_id": odoo_product["id"],
                        "product_uom_qty": p["uom_qty"],
                        "price_unit": odoo_product["list_price"] * p["uom_qty"],
                    }
                )
                # end for
            logger.debug(f"Order lines created: {order_line}")
            return order_line

        except Exception as exc:
            logger.error(f"Error creating order lines: {str(exc)}")
            return False

    async def get_children_ids(self, category_id):
        children_ids = [category_id]
        children = await self.get_categories_children(category_id)
        for child in children:
            children_ids.append(child["id"])
            if child["child_id"]:
                children += await self.get_categories_children(child["id"])

        logger.debug(
            f"category_id {category_id} tiene {len(children)} categorías hijas"
        )
        return children_ids

    async def get_products_by_category_name(self, category_name):
        # return {'category_name': [products], ...}
        logger.debug(f"get_products_by_category_name({category_name})")

        category_id_list = await self.get_categories_by_name(category_name)
        ans = {}
        for category in category_id_list:
            products = await self.get_products_by_category_id(category["id"])
            ans[category["name"]] = products

        return ans

    async def get_products_by_category_id(self, category_id) -> list[dict]:
        logger.debug(f"get_products_by_category_id({category_id})")

        fields = json.dumps(
            [
                "id",
                "default_code",
                "name",
                "categ_id",
                "list_price",
                "type",
                "active",
            ]
        )
        category_id_list = await self.get_children_ids(category_id)
        tasks = []
        for id in category_id_list:
            domain = json.dumps([["categ_id", "=", id], ["active", "=", True]])
            tasks.append(self.fetch_odoo("product.product", fields, domain, limit=100))

        results = await asyncio.gather(*tasks)
        product_data = []
        for r in results:
            product_data += r

        if product_data:
            logger.debug(f"{len(product_data)} productos encontrados")
            return product_data

        return []

    async def get_categories(
        self, id=None, name=None, parent_id=None, child_id=None
    ) -> list[dict]:
        if id:
            domain = json.dumps([["id", "=", id]])
        elif name:
            domain = json.dumps([["name", "ilike", name]])
        elif parent_id:
            domain = json.dumps([["parent_id", "=", parent_id]])
        elif child_id:
            domain = json.dumps([["child_id", "=", child_id]])
        else:
            domain = ""

        fields = json.dumps(["id", "name", "parent_id", "child_id", "product_count"])
        categories = await self.fetch_odoo("product.category", fields, domain)

        if categories:
            return categories

        return []

    async def get_category_by_id(self, id):
        logger.debug(f"get_category_by_id({id})")
        return await self.get_categories(id=id)

    async def get_categories_by_name(self, name):
        logger.debug(f"get_categories_by_name({name})")
        return await self.get_categories(name=name)

    async def get_categories_children(self, parent_id):
        logger.debug(f"get_categories_children({parent_id})")
        return await self.get_categories(parent_id=parent_id)

    async def get_category_parent(self, child_id):
        logger.debug(f"get_category_parent({child_id})")
        return await self.get_categories(child_id=child_id)

    async def get_all_categories(self):
        logger.debug("get_all_categories()")
        return await self.get_categories()

    async def get_images_by_product_id(self, product_id, product_sku) -> list[str]:
        domain = json.dumps([["product_tmpl_id", "=", product_id]])
        domain2 = json.dumps([["product_variant_id", "=", product_id]])

        fields = json.dumps(
            [
                "product_tmpl_id",
                "name",
                "product_variant_id",
                "image_1024",
            ]
        )

        images = await self.fetch_odoo("product.image", fields, domain)  # type: ignore
        if not images:
            images = await self.fetch_odoo("product.image", fields, domain2)  # type: ignore
            if not images:
                return []

        images_path = []
        for idx, image in enumerate(images):
            file_name = f"{product_sku}_{idx}"  # type: ignore
            images_path.append(file_name)
            asyncio.create_task(self.download_image(image["image_1024"], file_name))  # type: ignore

        return images_path


odoo_orion = OdooOrion()
