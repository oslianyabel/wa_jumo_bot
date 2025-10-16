from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    ENV_STATE: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class GlobalConfig(BaseConfig):
    DATABASE_URL: str

    # Odoo
    ODOO_URL: str
    ODOO_CLIENT_ID: str
    ODOO_CLIENT_SECRET: str

    # MUK
    TOKEN_PATH: str
    SEARCH_PATH: str
    CREATE_PATH: str

    # OpenAI
    OPENAI_API_KEY: str
    ORION_ASSISTANT_ID: str
    EXTRACTOR_ASSISTANT_ID: str

    # Meta WhatsApp Business API
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str

    # Smtp
    EMAIL: str
    DEV_EMAIL: str
    ADMIN_EMAIL: str
    EMAIL_PASSWORD: str
    EMAIL_HOST: str

    # Hosting
    HOST: str
    PORT: Optional[int] = None

    # cloudinary
    CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    # Others
    BOT_NUMBER: str
    WORDS_LIMIT: Optional[int] = None
    CANVA_LINK: str


class DevConfig(GlobalConfig):
    model_config = SettingsConfigDict(env_prefix="DEV_")


class ProdConfig(GlobalConfig):
    model_config = SettingsConfigDict(env_prefix="PROD_")


@lru_cache
def get_config(env_state: str) -> GlobalConfig:
    configs = {
        "dev": DevConfig,
        "prod": ProdConfig,
    }
    return configs[env_state]()


config = get_config(BaseConfig().ENV_STATE)  # type: ignore


if __name__ == "__main__":
    print(config)
