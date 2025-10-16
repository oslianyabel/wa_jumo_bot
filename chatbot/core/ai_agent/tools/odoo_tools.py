import asyncio
import json

from chatbot.core import notifications
from chatbot.core.ai_agent.tools import utils
from chatbot.core.ai_agent.tools.odoo_manager import odoo_orion
from chatbot.logging_conf import logger


async def create_sale_order_by_product_id(
    user_number, product_id, product_qty, email, background_tasks, twilio_number=None
) -> str:
    logger.debug("Creando pedido...")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy creando su pedido 🛒",
                to=twilio_number,
            )
        )
    product_id = int(product_id)

    partner, odoo_product = await asyncio.gather(
        odoo_orion.get_partner_by_phone(user_number),
        odoo_orion.get_product_by_sku(product_id, template_first=False),
    )
    if not partner:
        return f"No existe el partner asociado al teléfono {user_number}"

    if not odoo_product:
        return f"No existe producto con sku: {product_id}"

    ans = await utils.create_sale_order(
        odoo_product,
        product_qty,
        partner,
        email,
        twilio_number,
        background_tasks,
    )
    return ans


async def create_lead(
    user_number, name, email, background_tasks, chat, product_name, twilio_number=None
) -> str:
    logger.debug("Creando lead...")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy registrando sus datos ✍️",
                to=twilio_number,
            )
        )

    partner, status = await odoo_orion.create_partner(name, user_number, email)
    if status == "ERROR":
        return "Error durante la creación del partner"

    resume_html, resume_text = await asyncio.gather(
        utils.resume_chat(chat, html_format=True),
        utils.resume_chat(chat, html_format=False),
    )
    logger.debug("Chat resumido")
    lead = await odoo_orion.create_lead(partner, resume_html, email)

    if background_tasks:
        background_tasks.add_task(
            notifications.notify_lead, partner, resume_text, email, lead
        )

    return "Hemos registrado sus datos. Pronto nuestro equipo se pondrá en contacto con usted"


async def get_partner(user_number, background_tasks, twilio_number=None) -> str:
    logger.debug(f"Getting partner with number {user_number}")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy verificando su usuario ✅",
                to=twilio_number,
            )
        )
    partner = await odoo_orion.get_partner_by_phone(user_number)
    if partner:
        return f"Partner encontrado: {partner}"

    return f"No existe usuario asociado al teléfono {user_number}. Sugerir crear cuenta"


async def create_partner(
    name, user_number, background_tasks, email=None, twilio_number=None
) -> str:
    logger.debug("Creating partner...")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy creando su usuario 👤",
                to=twilio_number,
            )
        )

    partner, status = await odoo_orion.create_partner(name, user_number, email)
    if status == "ALREADY":
        return f"Partner encontrado: {partner}"
    elif status == "CREATE":
        return f"Partner creado: {partner}"

    return "Error creando partner"


async def presupuestos(user_number, background_tasks, twilio_number=None) -> str:
    logger.debug(f"Getting sale orders (presupuestos) of {user_number}")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy buscando sus pedidos 🔍",
                to=twilio_number,
            )
        )
    partner = await odoo_orion.get_partner_by_phone(user_number)
    if not partner:
        return f"No se encontró ningún cliente con el teléfono {user_number}"

    if not partner["is_company"] and partner["parent_id"]:
        # Si el partner pertenece a una compañía tomar la compañía como referencia
        logger.debug(f"Partner pertenece a la compañía {partner['parent_id'][0]}")
        company = await odoo_orion.get_partner_by_id(partner["parent_id"][0])
        sale_orders = await odoo_orion.presupuestos(company["id"])  # type: ignore
        if sale_orders:
            return json.dumps(sale_orders)

        logger.debug(f"La compañía {partner['parent_id'][0]} no tiene presupuestos")

    sale_orders = await odoo_orion.presupuestos(partner["id"])
    if sale_orders:
        return json.dumps(sale_orders)

    msg = f"No se encontraron pedidos asociados a {user_number}"
    logger.warning(msg)
    return msg


async def get_sale_order_by_name(
    name, user_number, background_tasks, twilio_number=None
) -> str:
    logger.debug(f"Getting sale order {name}")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy buscando su pedido 📦",
                to=twilio_number,
            )
        )
    partner, order = await asyncio.gather(
        odoo_orion.get_partner_by_phone(user_number),
        odoo_orion.get_sale_order_by_name(name),
    )
    return await utils.check_order(partner, order, twilio_number)


async def get_sale_order_by_id(
    id, user_number, background_tasks, twilio_number=None
) -> str:
    logger.debug(f"Getting sale order {id}")
    id = int(id)

    if twilio_number:
        await notifications.send_whatsapp_message(
            body="Estoy buscando su pedido 📦",
            to=twilio_number,
        )
    partner, order = await asyncio.gather(
        odoo_orion.get_partner_by_phone(user_number),
        odoo_orion.get_sale_order_by_id(id),
    )
    return await utils.check_order(partner, order, twilio_number)


async def get_product_by_sku(
    sku, user_number, background_tasks, twilio_number=None
) -> str:
    logger.debug(f"Consultando producto con sku {sku}")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body=f"Estoy consultando el producto con sku {sku} 🔍",
                to=twilio_number,
            )
        )

    product = await odoo_orion.get_product_by_sku(sku, image=False)
    if product:
        return json.dumps(product)

    return f"Producto con sku {sku} no encontrado"


async def get_product_by_name(
    name, user_number, background_tasks, twilio_number=None
) -> str:
    logger.debug(f"Consultando producto {name}")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body=f"Estoy consultando el producto {name} 🔍",
                to=twilio_number,
            )
        )

    products = await odoo_orion.get_product_by_name(name, image=False)
    if products:
        return json.dumps(products)

    return (
        f"Producto {name} no encontrado. Indique su sku para una búsqueda más precisa"
    )


async def get_all_products(user_number, background_tasks, twilio_number=None) -> str:
    logger.debug("Consultando todos los productos...")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy revisando el almacén 🔍",
                to=twilio_number,
            )
        )

    products = await odoo_orion.get_all_products()
    if products:
        return json.dumps(products)

    return "Falló la consulta"


async def get_products_by_category_id(
    category_id: int, user_number, background_tasks, twilio_number=None
) -> str:
    if isinstance(category_id, str):
        category_id = int(category_id)

    category_name = None
    try:
        categories = await odoo_orion.get_category_by_id(category_id)
        if categories and isinstance(categories, list) and len(categories) > 0:
            category_name = categories[0].get("name")
    except Exception as e:
        logger.warning(
            f"No se pudo obtener el nombre de la categoría {category_id}: {e}"
        )

    display_name = category_name or str(category_id)
    logger.debug(f"Consultando productos de la categoría: {display_name}")

    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body=f"Estoy buscando productos de la categoría {display_name} 🔍",
                to=twilio_number,
            )
        )

    products = await odoo_orion.get_products_by_category_id(category_id)
    if products:
        ans = json.dumps(products)
        return ans

    return f"No se encontraron productos con category_id {display_name}"


async def get_all_categories(user_number, background_tasks, twilio_number=None) -> str:
    logger.debug("Consultando todas las categorías...")
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body="Estoy revisando las categorías de los productos 🔍",
                to=twilio_number,
            )
        )
    categories = await odoo_orion.get_all_categories()
    if categories:
        return json.dumps(categories)

    return "Falló la obtención de categorías"


async def send_main_product_image(
    sku, user_number, background_tasks, twilio_number=None
) -> str:
    logger.debug(f"Enviando imagen principal del producto con sku {sku}")

    product = await odoo_orion.get_product_by_sku(sku, image=True)
    if product:
        if product["has_image"]:
            if twilio_number and background_tasks:
                background_tasks.add_task(
                    utils.send_image, sku, product["name"], twilio_number
                )
                return f"Imagen principal del producto {product['name']} esta siendo enviada"
        else:
            return "El producto no tiene imagen disponible"

        return "La imagen no se ha enviado por estar dentro de un entorno de pruebas"

    return f"Producto con sku {sku} no encontrado"


async def send_all_product_images(
    sku, user_number, background_tasks, twilio_number=None
) -> str:
    logger.debug(f"Enviando todas las imágenes del producto con sku {sku}")

    product = await odoo_orion.get_product_by_sku(sku, image=True)
    if product:
        if twilio_number and background_tasks:
            # Enviar imagen principal
            background_tasks.add_task(
                utils.send_image, sku, product["name"], twilio_number
            )

            # Enviar imágenes adicionales
            images = await odoo_orion.get_images_by_product_id(product["id"], sku)
            for image_name in images:
                background_tasks.add_task(
                    utils.send_image, image_name, product["name"], twilio_number
                )

            total_images = 1 + len(images)
            return f"Se estan enviando {total_images} imágenes del producto {product['name']}"

        return (
            "Las imágenes no se han enviado por estar dentro de un entorno de pruebas"
        )

    return f"Producto con sku {sku} no encontrado"


odoo_tools = {
    "create_lead": create_lead,
    "create_sale_order_by_product_id": create_sale_order_by_product_id,
    "create_partner": create_partner,
    "get_partner": get_partner,
    "presupuestos": presupuestos,
    "get_sale_order_by_name": get_sale_order_by_name,
    "get_sale_order_by_id": get_sale_order_by_id,
    "get_product_by_sku": get_product_by_sku,
    "get_product_by_name": get_product_by_name,
    "get_all_products": get_all_products,
    "get_products_by_category_id": get_products_by_category_id,
    "get_all_categories": get_all_categories,
    "send_main_product_image": send_main_product_image,
    "send_all_product_images": send_all_product_images,
}
