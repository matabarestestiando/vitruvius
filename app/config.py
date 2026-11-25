import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    owner_token: str = os.getenv("OWNER_TOKEN", "")
    openrouter_key: str = os.getenv("OPENROUTER_API_KEY", "")
    model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    memory_url: str = os.getenv("MEMORY_URL", "http://10.116.0.5:8001")
    memory_token: str = os.getenv("MEMORY_TOKEN", "")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    spaces_endpoint: str = os.getenv("SPACES_ENDPOINT", "")
    spaces_region: str = os.getenv("SPACES_REGION", "")
    spaces_bucket: str = os.getenv("SPACES_BUCKET", "")
    repo_root: str = os.getenv("REPOSITORY_ROOT", "/repositories")
    mcp_origins: str = os.getenv("MCP_ALLOWED_ORIGINS", "")

    @property
    def spaces_ready(self):
        return all(
            (
                self.spaces_endpoint,
                self.spaces_region,
                self.spaces_bucket,
                os.getenv("AWS_ACCESS_KEY_ID"),
                os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
        )


settings = Settings()
