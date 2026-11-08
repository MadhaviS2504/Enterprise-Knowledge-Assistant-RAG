# Centralize environment-variable loading and application configuration.
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    aws_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket: str = ""
    database_url: str = ""  # Render PostgreSQL External Database URL
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"
    bedrock_chat_model: str = "amazon.nova-lite-v1:0"
    embed_dim: int = 1024
    max_upload_bytes: int = 10485760
    pinecone_api_key: str = ""
    pinecone_index_name: str = "atlas-enterprise-ai-index"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_ready_timeout: int = 180
    min_relevance: float = 0.25
    hitl_enabled: bool = True
    memory_turns: int = 6


@lru_cache
def settings() -> Settings:
    return Settings()


# ### Why it is useful

# `config.py` provides:

# - Automatic loading from `.env`
# - Named Python attributes such as `settings().aws_region`
# - Type validation—for example, converting `"1024"` into an integer
# - Central defaults when a variable is absent
# - One cached settings object instead of repeated `os.getenv()` calls
# - Consistent configuration across modules

# Instead of repeated code:

# ```python
# aws_region = os.getenv("AWS_REGION", "ap-south-1")
# pinecone_timeout = int(os.getenv("PINECONE_READY_TIMEOUT", "180"))
# ```

# You can use:

# ```python
# settings().aws_region
# settings().pinecone_ready_timeout
# ```

# ### Current repository status

# Currently, only `test.py` uses it:

# ```python
# from app.config import settings

# print(settings().bedrock_embed_model)
# ```

# The application modules mostly do not import it yet, so at present `config.py` is optional for the existing implementation.

# ### Recommendation

# Keep `config.py` as the application’s configuration layer. Store secrets and environment-specific values in `.env`, and access them through `settings()` rather than directly throughout the application.

# The responsibility split is:

# - `.env`: private values and environment-specific configuration
# - `.env.example`: safe template showing required variable names
# - `config.py`: loading, defaults, naming, and validation
# - Application modules: use the loaded settings without reading `.env` directly

# This is especially helpful during development, testing, Docker deployment, or switching between AWS accounts and regions.
