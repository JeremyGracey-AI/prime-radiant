"""Settings loaded from environment / .env — secrets and cost caps.

Cost caps are hard limits enforced by the run loop (Phase C): the bot must
stop spending when a cap is hit, and every run logs token spend against it.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    metaculus_token: str = ""
    news_api_key: str = ""

    per_question_budget_usd: float = 0.25
    per_run_budget_usd: float = 2.50
