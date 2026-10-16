from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    app_env: str = "development"

    telegram_bot_token: SecretStr
    telegram_admin_id: int = 0
    telegram_init_data_max_age_seconds: int = 86400

    xui_base_url: str
    xui_api_token: SecretStr
    internal_api_token: SecretStr | None = None
    xui_inbound_id: int = 4
    xui_verify_tls: bool = True

    public_sub_base_url: str

    public_link_secret: SecretStr
    public_subscription_url_base: str = "https://sub.kaditsolution.site/s"

    model_config = SettingsConfigDict(
        env_file="/opt/kad-bot/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
