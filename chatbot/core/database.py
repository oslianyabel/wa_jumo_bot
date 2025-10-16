import json
import sys
from functools import wraps
from typing import Callable, Optional

import asyncpg
import databases
import sqlalchemy
from sqlalchemy import DateTime, ForeignKey, Integer, String, func

from chatbot.config import config
from chatbot.core.ai_agent.prompt import SYSTEM_PROMPT
from chatbot.logging_conf import logger


def with_db_connection(func: Callable) -> Callable:
    # decorador para conectar y desconectar al hacer una consulta a la BD
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        await self.connect()
        try:
            result = await func(self, *args, **kwargs)
            return result
        finally:
            await self.disconnect()

    return wrapper


class Repository:
    def __init__(self, database_url: Optional[str] = None):
        self.metadata = sqlalchemy.MetaData()
        self.users_table = sqlalchemy.Table(
            "users",
            self.metadata,
            sqlalchemy.Column("phone", String, primary_key=True),
            sqlalchemy.Column("name", String, nullable=True),
            sqlalchemy.Column("email", String, nullable=True),
            sqlalchemy.Column("permissions", String, default="user"),
        )
        self.message_table = sqlalchemy.Table(
            "messages",
            self.metadata,
            sqlalchemy.Column("id", Integer, primary_key=True, autoincrement=True),
            sqlalchemy.Column("user_phone", ForeignKey("users.phone"), nullable=False),
            sqlalchemy.Column("role", String, nullable=False),
            sqlalchemy.Column("message", String, nullable=False),
            sqlalchemy.Column("created_at", DateTime, default=func.now()),
        )
        if not database_url:
            self.__database_url = config.DATABASE_URL
        else:
            self.__database_url = database_url
            
        self.engine = sqlalchemy.create_engine(self.__database_url)
        self.metadata.create_all(self.engine)
        self.database = databases.Database(
            self.__database_url,
            force_rollback=False,
        )

    async def connect(self):
        await self.database.connect()

    async def disconnect(self):
        await self.database.disconnect()

    async def get_user(self, phone: str):
        logger.debug(f"get_user {phone}")
        query = self.users_table.select().where(self.users_table.c.phone == phone)
        # logger.debug(query)

        async with self.database.transaction():
            user = await self.database.fetch_one(query)

        return user

    async def create_user(
        self,
        phone: str,
        name: str | None = None,
        email: str | None = None,
        permissions: str = "user",
    ) -> bool:
        data = {
            "phone": phone,
            "name": name,
            "email": email,
            "permissions": permissions,
        }
        query = self.users_table.insert().values(data)
        # logger.debug(query)

        async with self.database.transaction():
            try:
                await self.database.execute(query)
            except asyncpg.exceptions.UniqueViolationError:  # llave duplicada
                logger.warning(f"User with phone number {phone} already exists")
                return False

        logger.debug(f"User {phone} created in DB")
        return True

    async def update_user_data(self, phone: str, data: dict, debug=True) -> bool:
        if debug:
            logger.debug(f"Actualizando datos de {phone}")
        query = (
            self.users_table.update()
            .where(self.users_table.c.phone == phone)
            .values(**data)
        )
        """ if debug:
            logger.debug(query) """

        ans = True
        async with self.database.transaction():
            try:
                await self.database.execute(query)
            except Exception as exc:
                logger.error(exc)
                ans = False

        return ans

    async def create_message(self, phone: str, role: str, message: str):
        data = {
            "user_phone": phone,
            "role": role,
            "message": message,
        }
        query = self.message_table.insert().values(data)
        # logger.debug(query)
        async with self.database.transaction():
            await self.database.execute(query)

        logger.debug(f"mensaje de {role} agregado al chat de {phone}")

    async def reset_chat(self, phone: str):
        logger.warning(f"Deleting chats from {phone}")
        user = await self.get_user(phone)
        if not user:
            return "El usuario no existe"

        query = self.message_table.delete().where(
            self.message_table.c.user_phone == phone
        )
        # logger.debug(query)
        async with self.database.transaction():
            await self.database.execute(query)

        # insertar msg inicial al nuevo chat
        if user.name:  # type: ignore
            if user.email:  # type: ignore
                msg = f"El usuario se llama {user.name} y su correo es {user.email}. Llámale por su nombre"  # type: ignore
            else:
                msg = f"El usuario se llama {user.name}. Llámale por su nombre"  # type: ignore
        else:
            msg = (
                "Pídele el nombre al usuario para que le crees una cuenta en el sistema"
            )

        logger.debug("Insert system messages")
        await self.create_message(phone=phone, role="system", message=SYSTEM_PROMPT)  # type: ignore
        await self.create_message(phone, "system", msg)

    async def get_messages(self, phone: str):
        logger.debug(f"Obteniendo el chat de {phone}")
        query = (
            self.message_table.select()
            .where(self.message_table.c.user_phone == phone)
            .order_by(self.message_table.c.created_at.asc())
        )
        # logger.debug(query)
        async with self.database.transaction():
            return await self.database.fetch_all(query)

    async def get_chat(self, phone: str) -> list[dict]:
        messages_obj = await self.get_messages(phone)

        return [{"role": msg.role, "content": msg.message} for msg in messages_obj]  # type: ignore

    async def get_chat_str(self, phone: str) -> str:
        messages = await self.get_chat(phone)
        return json.dumps(messages)


try:
    db = Repository()
except KeyError:
    logger.error("Incorrect database credentials")
    sys.exit("Exiting program due to database error")
except sqlalchemy.exc.OperationalError: # type: ignore
    logger.error("database server is down")
    sys.exit("Exiting program due to database error")
