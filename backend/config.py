from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from services.usage import Pricing

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file = ".env")

    google_api_key: str
    tavily_api_key: str
    database_url: str

    ingestion_interval_minutes: int = 60

    # Cost cap: at most this many *new* articles per feed per run (~$0.03
    # each). Feeds list newest first, so a capped run keeps the freshest.
    max_new_articles_per_feed: int = 2

    # Cost cap: at most this many *new* In Terms generations per UTC day.
    # The feed is public and the endpoint has no auth, so this is what
    # bounds spend. Cached translations are always served, cap or not.
    max_in_terms_generations_per_day: int = 200

    # Optional USD rates for cost estimates in the logs. Leave unset and
    # usage is still logged (calls, tokens, time), just without a $ figure.
    llm_input_usd_per_mtok: float | None = None
    llm_output_usd_per_mtok: float | None = None
    search_usd_per_call: float | None = None

    def pricing(self) -> Pricing | None:
        rates = (
            self.llm_input_usd_per_mtok,
            self.llm_output_usd_per_mtok,
            self.search_usd_per_call,
        )
        if any(rate is None for rate in rates):
            return None
        return Pricing(*rates)

@lru_cache
def get_settings() -> Settings:
    return Settings()