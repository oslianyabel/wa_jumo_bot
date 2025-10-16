async def test_get_partner(
    user_number, background_tasks, name=False, twilio_number=None
) -> str:
    partner = {
        "name": "Osliani",
        "email": "test@gmail.com",
        "phone": "+5352045846",
    }
    return f"Socio existente: {partner}"


async def test_create_partner(
    name, user_number, background_tasks, email=None, twilio_number=None
):
    partner = {
        "name": "Osliani",
        "email": "test@gmail.com",
        "phone": "+5352045846",
    }
    return f"Contacto existente: {partner}"


async def test_presupuestos(user_number, background_tasks, twilio_number=None) -> str:
    return "No se encontraron pedidos asociados al teléfono +5352045846"


async def test_get_sale_order_by_name(
    name, user_number, background_tasks, twilio_number=None
) -> str:
    return "El pedido no le pertenece a usted"


async def test_clean_chat(user_number, background_tasks, twilio_number=None) -> str:
    return "Historial Eliminado"
