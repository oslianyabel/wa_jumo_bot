"""
Script para enviar un mensaje de WhatsApp manualmente a un número específico.

Uso:
    uv run python scripts/send_whatsapp.py
    uv run python scripts/send_whatsapp.py --to 18352353226 --message "Hola, ¿cómo estás?"
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chatbot.core.notifications import send_whatsapp_message
from chatbot.logging_conf import logger

# Número de destino por defecto (formato E.164 sin +)
DEFAULT_TO: str = "18352353226"
DEFAULT_MESSAGE: str = "Hola, este es un mensaje de prueba enviado desde el script."


async def main(to: str, message: str) -> None:
    logger.info(f"Enviando mensaje a {to}...")
    success = await send_whatsapp_message(body=message, to=to)
    if success:
        logger.info(f"Mensaje enviado exitosamente a {to}")
    else:
        logger.error(f"Falló el envío del mensaje a {to}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enviar mensaje de WhatsApp")
    parser.add_argument(
        "--to",
        type=str,
        default=DEFAULT_TO,
        help=f"Número de destino en formato E.164 sin + (por defecto: {DEFAULT_TO})",
    )
    parser.add_argument(
        "--message",
        type=str,
        default=DEFAULT_MESSAGE,
        help="Mensaje a enviar",
    )
    args = parser.parse_args()

    asyncio.run(main(to=args.to, message=args.message))
