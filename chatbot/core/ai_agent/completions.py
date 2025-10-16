import asyncio
import json
import sys
import pathlib
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional
from chatbot.logging_conf import logger

# Add project root to sys.path for direct execution
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv
from fastapi import BackgroundTasks
from openai import AsyncOpenAI, OpenAI

from chatbot.config import config
from chatbot.core.ai_agent.enumerations import (
    EffortType,
    MessageType,
    ModelType,
    VerbosityType,
)
from chatbot.core.ai_agent.prompt import SYSTEM_PROMPT

# from chatbot.core.ai_agent.tools.pg_tool import async_execute_query
from chatbot.core.ai_agent.tools_json import tools_json
from chatbot.core.ai_agent.tools.odoo_tools import odoo_tools

load_dotenv(".env")


class SetMessagesError(Exception):
    pass


class ChatMemory:
    def __init__(self, prompt=SYSTEM_PROMPT):
        self.__ai_output: dict[str, Any] = {}
        self.__messages: dict[str, list[dict]] = {}
        self.__tool_msgs: dict[str, list[dict]] = {}
        self.init_msg = {
            "role": MessageType.DEVELOPER.value,
            "content": prompt,
        }
        self.__last_time: float

    def get_ai_output(self, phone: str):
        if phone not in self.__ai_output:
            return []

        return self.__ai_output[phone].output

    def get_tool_msgs(self, phone: str):
        if phone not in self.__tool_msgs:
            return []
        return self.__tool_msgs[phone]

    def get_messages(self, phone: str):
        if phone not in self.__messages:
            logger.info(f"{phone} not found in memory")
            self.init_chat(phone)

        return self.__messages[phone]

    def get_last_time(self):
        return self.__last_time

    def _set_ai_output(self, ai_output, phone: str):
        self.__ai_output[phone] = ai_output

        if phone not in self.__messages:
            logger.info(f"{phone} not found in memory")
            return False

        if phone not in self.__tool_msgs:
            self.__tool_msgs[phone] = ai_output.output.copy()
        else:
            self.__tool_msgs[phone] += ai_output.output.copy()

        self.__messages[phone] += ai_output.output.copy()

    def _clean_tool_msgs(self, phone: str):
        if phone not in self.__tool_msgs:
            logger.info(f"{phone} not have tool messages")

        self.__tool_msgs[phone] = []

    def has_chat(self, phone: str) -> bool:
        return phone in self.__messages and len(self.__messages[phone]) > 0

    def delete_chat(self, phone: str) -> None:
        if phone in self.__messages:
            del self.__messages[phone]
        if phone in self.__tool_msgs:
            del self.__tool_msgs[phone]
        if phone in self.__ai_output:
            del self.__ai_output[phone]

    def init_chat(self, phone: str):
        self.set_messages([self.init_msg], phone)
        logger.info(f"New chat for {phone}")

    def add_msg(self, message: str, role: str, phone: str):
        if phone not in self.__messages:
            self.init_chat(phone)

        if MessageType.has_value(role):
            self.__messages[phone].append(
                {
                    "role": role,
                    "content": message,
                }
            )
            logger.info(f"New message from {role} added to chat of {phone}")
            return True

        logger.warning(f"Invalid role {role}, must be one of: {MessageType.list_values()}")
        return False

    def set_messages(self, messages: list[dict[str, str]], phone: str):
        if not isinstance(messages, list):
            raise SetMessagesError(f"messages must be a list, not {type(messages)}")

        for id, msg in enumerate(messages):
            if not MessageType.has_value(msg["role"]):
                raise SetMessagesError(
                    f"Invalid role {msg['role']} in the {id + 1} message, must be one of: {MessageType.list_values()}"
                )

        self.__messages[phone] = messages

    def _get_ai_msg(self, phone: str):
        ai_output = self.get_ai_output(phone)

        for item in ai_output:  # type: ignore
            try:
                if item.type == "message":
                    ans = item.content[0].text  # type: ignore
                    return ans

            except Exception as exc:
                logger.error(f"Error retrieving AI message: {exc}")
                logger.error(item)

        return "No Answer"

    def _purge_tool_msgs(self, phone: str):
        tool_msgs = self.get_tool_msgs(phone)
        messages = self.get_messages(phone)
        if tool_msgs:
            clean_messages = [m for m in messages if m not in tool_msgs]
            try:
                self.set_messages(clean_messages, phone)
            except SetMessagesError as exc:
                logger.warning(f"Error purging tool messages: {exc}")
            finally:
                self._clean_tool_msgs(phone)

    def _set_tool_output(self, call_id, function_out, phone: str):
        # Store as ephemeral tool output; do not persist in history
        if phone not in self.__messages:
            logger.info(f"{phone} not found in memory")
            return False

        msg = {
            "type": "function_call_output",
            "call_id": call_id,
            "output": str(function_out),
        }

        if phone not in self.__tool_msgs:
            self.__tool_msgs[phone] = [msg]
        else:
            self.__tool_msgs[phone].append(msg)

        self.__messages[phone].append(msg)


class AIClient:
    def __init__(
        self,
        api_key: str,
    ):
        self.__client = OpenAI(api_key=api_key)
        self.__async_client = AsyncOpenAI(api_key=api_key)

    async def _async_gen_ai_output(self, params: dict):
        ai_output = await self.__async_client.responses.create(**params)
        return ai_output

    def _gen_ai_output(self, params: dict):
        return self.__client.responses.create(**params)


class ToolRunner:
    def __init__(
        self,
        error_msg="Ha ocurrido un error inesperado",
    ):
        self.ERROR_MSG = error_msg

    def _run_functions(
        self,
        functions_called,
        odoo_number: str,
        chat_memory: ChatMemory,
        whatsapp_number: Optional[str],
        background_tasks: Optional[BackgroundTasks],
    ) -> None:
        logger.info(f"{len(functions_called)} functions need to be called!")

        with ThreadPoolExecutor() as executor:
            futures = []
            for tool in functions_called:
                function_name = tool.name
                logger.info(f"function_name: {function_name}")

                function_to_call = odoo_tools[function_name]
                function_args = json.loads(tool.arguments)
                function_args["background_tasks"] = background_tasks
                if odoo_number:
                    function_args["user_number"] = odoo_number

                if whatsapp_number:
                    function_args["twilio_number"] = whatsapp_number

                if function_name == "create_lead":
                    function_args["chat"] = chat_memory.get_messages(odoo_number)

                fa_str = str(function_args)
                logger.info(
                    f"function_args: {fa_str[:100]}{'...' if len(fa_str) > 100 else ''}"
                )
                futures.append(executor.submit(function_to_call, **function_args))

            self.run_futures(futures, functions_called, odoo_number, chat_memory)

    def _run_custom_tools(
        self,
        custom_tools_called,
        odoo_number: str,
        chat_memory: ChatMemory,
        whatsapp_number: Optional[str],
        background_tasks: Optional[BackgroundTasks],
    ) -> None:
        logger.info(f"{len(custom_tools_called)} custom tools need to be called!")

        with ThreadPoolExecutor() as executor:
            futures = []
            for tool in custom_tools_called:
                logger.info(f"Custom tool name: {tool.name}")
                function_to_call = odoo_tools[tool.name]
                logger.info(f"Custom tool input: {tool.input}")

                function_args = {"tool_input": tool.input}
                function_args["background_tasks"] = background_tasks
                if odoo_number:
                    function_args["user_number"] = odoo_number
                if whatsapp_number:
                    function_args["twilio_number"] = whatsapp_number

                futures.append(executor.submit(function_to_call, **function_args))

            self.run_futures(futures, custom_tools_called, odoo_number, chat_memory)

    def run_futures(self, futures, tools_called, phone: str, chat_memory: ChatMemory):
        for future, tool in zip(futures, tools_called):
            try:
                function_out = future.result()
                logger.info(f"{tool.name}: {function_out[:100]}")  # type: ignore
            except Exception as exc:
                logger.error(f"{tool.name}: {exc}")
                function_out = self.ERROR_MSG

            chat_memory._set_tool_output(tool.call_id, function_out, phone)

    async def _async_run_functions(
        self,
        functions_called,
        odoo_number: str,
        chat_memory: ChatMemory,
        whatsapp_number: Optional[str],
        background_tasks: Optional[BackgroundTasks],
    ) -> None:
        logger.info(f"{len(functions_called)} function need to be called!")
        tasks = []
        for tool in functions_called:
            function_name = tool.name
            logger.info(f"function_name: {function_name}")
            function_to_call = odoo_tools[function_name]  # type: ignore

            function_args = json.loads(tool.arguments)
            function_args["background_tasks"] = background_tasks
            if odoo_number:
                function_args["user_number"] = odoo_number
            if whatsapp_number:
                function_args["twilio_number"] = whatsapp_number
            if function_name == "create_lead":
                function_args["chat"] = chat_memory.get_messages(odoo_number)

            fa_str = str(function_args)
            logger.info(f"function_args: {fa_str[:100]}{'...' if len(fa_str) > 100 else ''}")
            tasks.append(function_to_call(**function_args))

        await self.run_coroutines(functions_called, tasks, odoo_number, chat_memory)

    async def _async_run_custom_tools(  # type: ignore
        self,
        custom_tools_called,
        odoo_number: str,
        chat_memory: ChatMemory,
        whatsapp_number: Optional[str],
        background_tasks: Optional[BackgroundTasks],
    ) -> None:
        logger.info(f"{len(custom_tools_called)} custom tools need to be called!")

        tasks = []
        for tool in custom_tools_called:
            logger.info(f"function_name: {tool.name}")
            function_to_call = odoo_tools[tool.name]  # type: ignore

            logger.info(f"Input tool: {tool.input}")

            function_args = {"tool_input": tool.input}
            function_args["background_tasks"] = background_tasks
            if odoo_number:
                function_args["user_number"] = odoo_number
            if whatsapp_number:
                function_args["twilio_number"] = whatsapp_number

            tasks.append(function_to_call(**function_args))

        await self.run_coroutines(custom_tools_called, tasks, odoo_number, chat_memory)

    async def run_coroutines(
        self, tools_called, tasks, phone: str, chat_memory: ChatMemory
    ):
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for tool, function_out in zip(tools_called, results):
            if isinstance(function_out, Exception):
                logger.error(f"{tool.name}: {function_out}")
                function_out = self.ERROR_MSG  # type: ignore
            else:
                logger.info(f"{tool.name}: {function_out[:100]}")  # type: ignore

            chat_memory._set_tool_output(tool.call_id, function_out, phone)


class Agent:
    def __init__(
        self,
        name="Akivoy Agent",
        model=ModelType.GPT_5.value,
    ):
        self.name = name
        self.model = model
        self.chat_memory = ChatMemory()
        self._ai_client = AIClient(config.OPENAI_API_KEY)
        self._tool_runner = ToolRunner()

    def process_msg(
        self,
        message: str,
        odoo_number: str,
        background_tasks: Optional[BackgroundTasks] = None,
        whatsapp_number: Optional[str] = None,
    ) -> str | None:
        logger.info(f"Running {self.model} with {len(tools_json)} tools")

        self.chat_memory.add_msg(message, MessageType.USER.value, odoo_number)

        while True:
            params = {
                "model": self.model,  # type: ignore
                "input": self.chat_memory.get_messages(odoo_number),  # type: ignore
                "tools": tools_json,  # type: ignore
            }
            if self.model == ModelType.GPT_5.value:  # type: ignore
                params["text"] = {"verbosity": VerbosityType.LOW.value}
                params["reasoning"] = {"effort": EffortType.MINIMAL.value}

            ai_output = self._ai_client._gen_ai_output(params)
            self.chat_memory._set_ai_output(ai_output, odoo_number)

            functions_called = [
                item
                for item in ai_output.output  # type: ignore
                if item.type == MessageType.FUNCTION_CALL.value
            ]

            custom_tools_called = [
                item
                for item in ai_output.output  # type: ignore
                if item.type == MessageType.CUSTOM_TOOL_CALL.value
            ]

            if not functions_called and not custom_tools_called:
                break

            if functions_called:
                self._tool_runner._run_functions(
                    functions_called,
                    odoo_number,
                    self.chat_memory,
                    whatsapp_number,
                    background_tasks,
                )

            if custom_tools_called:
                self._tool_runner._run_custom_tools(
                    custom_tools_called,
                    odoo_number,
                    self.chat_memory,
                    whatsapp_number,
                    background_tasks,
                )

        self.chat_memory._purge_tool_msgs(odoo_number)
        ai_msg = self.chat_memory._get_ai_msg(odoo_number)
        logger.info(f"{self.name}: {ai_msg}")
        self.chat_memory.add_msg(ai_msg, MessageType.ASSISTANT.value, odoo_number)
        return ai_msg

    async def async_process_msg(
        self,
        message: str,
        odoo_number: str,
        background_tasks: Optional[BackgroundTasks] = None,
        whatsapp_number: Optional[str] = None,
    ) -> str | None:
        logger.info(f"Running {self.name} with {len(tools_json)} tools")

        self.chat_memory.add_msg(message, MessageType.USER.value, odoo_number)

        while True:
            params = {
                "model": self.model,  # type: ignore
                "input": self.chat_memory.get_messages(odoo_number),  # type: ignore
                "tools": tools_json,  # type: ignore
            }
            if self.model == ModelType.GPT_5.value:  # type: ignore
                params["text"] = {"verbosity": VerbosityType.LOW.value}
                params["reasoning"] = {"effort": EffortType.MINIMAL.value}

            ai_output = await self._ai_client._async_gen_ai_output(params)
            self.chat_memory._set_ai_output(ai_output, odoo_number)

            functions_called = [
                item
                for item in ai_output.output  # type: ignore
                if item.type == MessageType.FUNCTION_CALL.value
            ]

            custom_tools_called = [
                item
                for item in ai_output.output  # type: ignore
                if item.type == MessageType.CUSTOM_TOOL_CALL.value
            ]

            if not functions_called and not custom_tools_called:
                break

            if functions_called:
                await self._tool_runner._async_run_functions(
                    functions_called,
                    odoo_number,
                    self.chat_memory,
                    whatsapp_number,
                    background_tasks,
                )

            if custom_tools_called:
                await self._tool_runner._async_run_custom_tools(
                    custom_tools_called,
                    odoo_number,
                    self.chat_memory,
                    whatsapp_number,
                    background_tasks,
                )

        self.chat_memory._purge_tool_msgs(odoo_number)
        ai_msg = self.chat_memory._get_ai_msg(odoo_number)
        logger.info(f"{self.name}: {ai_msg}")
        self.chat_memory.add_msg(ai_msg, MessageType.ASSISTANT.value, odoo_number)
        return ai_msg


async def console_chat_main():
    """
    Flujo de chat principal con entrada de usuario por consola
    """
    print("🤖 Console Chat Bot")
    print("=" * 50)
    print("Comandos: /exit (salir), /reset (reiniciar), /help (ayuda)")
    print("=" * 50)

    bot = Agent("Test Agent")
    conversation_count = 0

    while True:
        try:
            user_input = input("\n👤 Usuario: ").strip()

            if not user_input:
                continue

            # Comandos especiales
            if user_input.lower() in ["/exit", "quit", ":q"]:
                print("👋 ¡Hasta luego!")
                break

            elif user_input.lower() == "/reset":
                bot.chat_memory.init_chat("console")
                bot.chat_memory.add_msg(
                    "Conversación reiniciada.", MessageType.DEVELOPER.value, "console"
                )
                conversation_count = 0
                print("🔄 Conversación reiniciada")
                continue

            elif user_input.lower() == "/help":
                help_text = """
📋 Comandos disponibles:
  /exit, quit, :q  - Salir del chat
  /reset           - Reiniciar conversación
  /help            - Mostrar esta ayuda
  
💡 Simplemente escribe tu mensaje para chatear con el bot
                """
                print(help_text)
                continue

            print("🤖 Procesando...")

            try:
                await bot.async_process_msg(user_input, odoo_number="console")
                conversation_count += 1

            except Exception as exc:
                print(f"❌ Error: {exc}")

        except (EOFError, KeyboardInterrupt):
            print("\n👋 Saliendo del chat...")
            break
        except Exception as exc:
            print(f"❌ Error inesperado: {exc}")


if __name__ == "__main__":
    asyncio.run(console_chat_main())
