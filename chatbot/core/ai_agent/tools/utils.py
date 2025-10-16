import json
import asyncio
import os

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

from chatbot.config import config
from chatbot.core import notifications
from chatbot.core.ai_agent.enumerations import MessageType
from chatbot.core.ai_agent.tools.odoo_manager import OdooHttpException  # type: ignore
from chatbot.core.ai_agent.tools.odoo_manager import odoo_orion
from chatbot.logging_conf import logger


async def create_sale_order(
    odoo_product, product_qty, partner, email, twilio_number, background_tasks
):
    product_qty = int(product_qty)

    if odoo_product["qty_available"] and int(odoo_product["qty_available"]) < 1:
        return f"No hay stock disponible del producto {odoo_product['name']} en este momento"

    order_line = [
        {
            "product_id": int(odoo_product["id"]),
            "product_uom_qty": product_qty,
            "price_unit": int(odoo_product["list_price"]) * product_qty,
        },
    ]
    try:
        sale_order = await odoo_orion.create_sale_order(partner["id"], order_line)
        sale_order_data = await odoo_orion.get_sale_order_by_id(sale_order[0][0])  # type: ignore
    except Exception as exc:
        logger.error(exc)
        return f"Ha ocurrido un error al intentar crear un pedido con el producto {odoo_product['name']}. Error: {exc}"

    msg = f"Nombre del producto: {odoo_product['name']}\nCantidad: {product_qty}\nMonto total: {odoo_product['list_price'] * product_qty}\nID del pedido: {sale_order[0][0]}\nEnlace al presupuesto: {sale_order_data['link']}"  # type: ignore

    try:
        pdf_path = await odoo_orion.get_report(sale_order[0][0])  # type: ignore
    except OdooHttpException:
        try:
            pdf_path = await odoo_orion.get_report(sale_order[0][0], raw=True)  # type: ignore
        except OdooHttpException as exc:
            logger.error(exc)

            if background_tasks:
                background_tasks.add_task(notifications.notify_sale_order, email, msg)

            asyncio.create_task(
                notifications.send_whatsapp_message(
                    body=f"Vea su presupuesto aquí: {sale_order_data['link']}",  # type: ignore
                    to=twilio_number,
                )
            )
            return f"Presupuesto creado! Número de seguimiento: {sale_order[0][0]}. No se pudo generar el PDF con la cotización"  # type: ignore

    if background_tasks:
        background_tasks.add_task(notifications.notify_sale_order, email, msg, pdf_path)

    if twilio_number:
        url = upload_file(pdf_path, sale_order[0][0])  # type: ignore
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body=f"Cotización #{sale_order[0][0]}",  # type: ignore
                to=twilio_number,
                media=url,
            )
        )
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body=f"Vea su presupuesto aquí: {sale_order_data['link']}",  # type: ignore
                to=twilio_number,
            )
        )

    return f"Presupuesto creado! Número de seguimiento: {sale_order[0][0]}"  # type: ignore


def upload_file(path, id):
    cloudinary.config(
        cloud_name=config.CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True,
    )
    id = str(id)
    cloudinary.uploader.upload(path, public_id=id)
    optimize_url, _ = cloudinary_url(id, fetch_format="auto", quality="auto")
    return optimize_url


async def send_image(sku, name, twilio_number):
    logger.debug(f"Enviando imagen de {name}...")
    image_path = f"static/images/{sku}.jpg"

    # Validar que el archivo exista antes de intentar subirlo
    if not os.path.exists(image_path):
        logger.warning(f"Imagen no encontrada: {image_path}")
        # Enviar un mensaje de texto informando que la imagen no está disponible
        if twilio_number:
            asyncio.create_task(
                notifications.send_whatsapp_message(
                    body=f"No se encontró la imagen del producto {name}.",
                    to=twilio_number,
                )
            )
        return False

    url = upload_file(image_path, sku)

    asyncio.create_task(
        notifications.send_whatsapp_message(
            body=name,
            to=twilio_number,
            media=url,
        )
    )


async def send_report(sale_order_id, twilio_number=None):
    logger.debug(f"Obteniendo reporte de cotización del pedido {sale_order_id}...")
    sale_order_id = int(sale_order_id)
    try:
        pdf_path = await odoo_orion.get_report(sale_order_id)
    except OdooHttpException:
        try:
            pdf_path = await odoo_orion.get_report(sale_order_id, raw=True)
        except OdooHttpException:
            return False

    url = upload_file(pdf_path, sale_order_id)
    if twilio_number:
        asyncio.create_task(
            notifications.send_whatsapp_message(
                body=f"Cotización #{sale_order_id}",
                to=twilio_number,
                media=url,
            )
        )
    return True


async def check_order(partner, order, twilio_number):
    if not partner:
        msg = "El partner no existe"
        logger.warning(msg)
        return msg

    if not order:
        msg = "El pedido no existe"
        logger.warning(msg)
        return msg

    # verifica que el pedido esté asociado al partner
    if order["partner_id"][0] == partner["id"]:
        await send_report(order["id"], twilio_number)
        return json.dumps(order)

    # Si el partner pertenece a una compañía verificar que el pedido pertenezca a la compañía
    if not partner["is_company"] and partner["parent_id"]:
        logger.info(f"Compañía {partner['parent_id']} tomada como referencia")
        partner = await odoo_orion.get_partner_by_id(partner["parent_id"][0])
        # verifica que el pedido esté asociado a la compañía
        if order["partner_id"][0] == partner["id"]:  # type: ignore
            await send_report(order["id"], twilio_number)
            return json.dumps(order)

    logger.warning(
        f"El pedido le pertenece a {order['partner_id']}, no a {partner['name']}"  # type: ignore
    )
    return "El pedido no le pertenece a usted"


async def resume_chat(
    chat: list[dict[str, str]], html_format: bool = True
) -> str | None:
    logger.debug("Resumiendo chat...")
    msg_base = """A continuación te paso una conversación entre un cliente y un asistente virtual. Necesito que resumas la conversación para que quede bien definida la intencion del cliente y se destaquen: el servicio que desea el cliente, los precios ofrecidos por el asistente, nombre del cliente y empresa a la que pertenece (si aparece)"""

    msg_html = msg_base + " Responde en formato html"
    msg_plain = (
        msg_base
        + " No utilices saltos de línea ni formato markdown, solo texto plano. Tu respuesta se enviará por email"
    )
    sys_msg = msg_html if html_format else msg_plain

    chat_str = ""
    for msg in chat:
        if "role" not in msg:
            continue

        if msg.get("role") not in [MessageType.USER.value, MessageType.ASSISTANT.value]:
            continue

        chat_str += f"{msg['role']}: {msg.get('content', '')} \n"

    # Importar localmente para evitar importación circular con completions
    from chatbot.core.ai_agent.completions import AsyncAgent

    resumidor = AsyncAgent(
        name="Resumidor", prompt=sys_msg, api_key=config.OPENAI_API_KEY
    )
    msg = await resumidor.process_msg(chat_str, "resume_chat")
    return msg
