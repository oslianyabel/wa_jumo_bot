create_sale_order_by_product_id = {
    "type": "function",
    "name": "create_sale_order_by_product_id",
    "description": "Crea un pedido que contiene una linea de pedido con un producto",
    "parameters": {
        "type": "object",
        "properties": {
            "product_id": {
                "type": "integer",
                "description": "id del producto solicitado",
            },
            "product_qty": {
                "type": "integer",
                "description": "Cantidad solicitada del producto",
            },
            "email": {"type": "string", "description": "Email del cliente"},
        },
        "required": ["product_id", "product_qty", "email"],
    },
}

create_lead = {
    "type": "function",
    "name": "create_lead",
    "description": "Notifica a los jefes sobre el interés del cliente en algún producto. Activar automáticamente después de cerrar un presupuesto",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Correo electrónico del cliente interesado (Obligatorio)",
            },
            "name": {
                "type": "string",
                "description": "Nombre del cliente interesado (Obligatorio)",
            },
            "product_name": {
                "type": "string",
                "description": "Nombre del producto que el cliente desea",
            },
        },
        "required": ["email", "name", "product_name"],
    },
}

get_partner = {
    "type": "function",
    "name": "get_partner",
    "description": "Consulta informacion de un usuario. Esta acción verifica si el usuario es cliente de JUMO y de ser así retorna su información personal. Activación automática al detectar frases como '¿Sabes quién soy?'.",
}

create_partner = {
    "type": "function",
    "name": "create_partner",
    "description": "Registra un usuario a partir de su nombre",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "Correo electrónico del cliente",
            },
            "name": {
                "type": "string",
                "description": "Nombre del cliente (Obligatorio)",
            },
        },
        "required": ["name"],
    },
}

presupuestos = {
    "type": "function",
    "name": "presupuestos",
    "description": "Consulta todos los pedidos de un cliente",
}

get_sale_order_by_name = {
    "type": "function",
    "name": "get_sale_order_by_name",
    "description": "Consulta el estado de un pedido especifico a partir de su nombre",
    "parameters": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Nombre del pedido"}},
        "required": ["name"],
    },
}

get_sale_order_by_id = {
    "type": "function",
    "name": "get_sale_order_by_id",
    "description": "Consulta el estado de un pedido especifico a partir de su id",
    "parameters": {
        "type": "object",
        "properties": {"id": {"type": "number", "description": "id del pedido"}},
        "required": ["id"],
    },
}

get_product_by_sku = {
    "type": "function",
    "name": "get_product_by_sku",
    "description": "Consulta datos de un producto a partir de su sku",
    "parameters": {
        "type": "object",
        "properties": {
            "sku": {"type": "string", "description": "sku del producto a consultar"}
        },
        "required": ["sku"],
    },
}

get_product_by_name = {
    "type": "function",
    "name": "get_product_by_name",
    "description": "Consulta informacion sobre un producto a partir de su nombre",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Nombre del producto a consultar"}
        },
        "required": ["name"],
    },
}

get_all_products = {
    "type": "function",
    "name": "get_all_products",
    "description": "Consulta todos los productos disponibles",
}

get_products_by_category_id = {
    "type": "function",
    "name": "get_products_by_category_id",
    "description": "Consulta una categoría a partir de su id y devuelve todos los productos que pertenezcan a ella",
    "parameters": {
        "type": "object",
        "properties": {
            "category_id": {"type": "integer", "description": "id de la categoría"}
        },
        "required": ["category_id"],
    },
}

get_all_categories = {
    "type": "function",
    "name": "get_all_categories",
    "description": "Consulta todas las categorías de productos disponibles",
}

send_main_product_image = {
    "type": "function",
    "name": "send_main_product_image",
    "description": "Envía la imagen principal de un producto a partir de su sku",
    "parameters": {
        "type": "object",
        "properties": {"sku": {"type": "string", "description": "sku del producto"}},
        "required": ["sku"],
    },
}

send_all_product_images = {
    "type": "function",
    "name": "send_all_product_images",
    "description": "Envía todas las imágenes de un producto a partir de su sku",
    "parameters": {
        "type": "object",
        "properties": {"sku": {"type": "string", "description": "sku del producto"}},
        "required": ["sku"],
    },
}

SQL_query = {
    "type": "custom",
    "name": "execute_query",
    "description": "Ejecuta una consulta SELECT SQL en la base de datos PostgreSQL de Odoo",
}

odoo_tools_json = [
    create_sale_order_by_product_id,
    create_lead,
    get_partner,
    create_partner,
    presupuestos,
    get_sale_order_by_name,
    get_sale_order_by_id,
    get_product_by_sku,
    get_product_by_name,
    get_all_products,
    get_products_by_category_id,
    get_all_categories,
    send_main_product_image,
    send_all_product_images,
]

tools_json = [
    *odoo_tools_json,
    # SQL_query,
]
