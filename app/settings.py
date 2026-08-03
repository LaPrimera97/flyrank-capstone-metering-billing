from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./billing.db"
    stripe_secret_key: str = "sk_test_placeholder"
    stripe_webhook_secret: str = "whsec_placeholder"
    stripe_pro_price_id: str = "price_placeholder"
    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"


settings = Settings()
