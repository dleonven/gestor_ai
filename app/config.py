import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    verify_token: str
    whatsapp_token: str
    phone_number_id: str
    database_url: str
    khipu_bearer_token: Optional[str] = None
    khipu_base_url: str = "https://api.khipu.com"
    graph_api_version: str = "v19.0"
    port: int = 3000

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [
            name
            for name in (
                "VERIFY_TOKEN",
                "WHATSAPP_TOKEN",
                "PHONE_NUMBER_ID",
                "DATABASE_URL",
            )
            if not os.getenv(name)
        ]
        if missing:
            raise ValueError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        port_value = os.getenv("PORT", "3000")
        try:
            port = int(port_value)
        except ValueError as exc:
            raise ValueError("PORT must be an integer") from exc

        return cls(
            verify_token=os.environ["VERIFY_TOKEN"],
            whatsapp_token=os.environ["WHATSAPP_TOKEN"],
            phone_number_id=os.environ["PHONE_NUMBER_ID"],
            database_url=os.environ["DATABASE_URL"],
            khipu_bearer_token=os.getenv("KHIPU_BEARER_TOKEN"),
            khipu_base_url=os.getenv("KHIPU_BASE_URL", "https://api.khipu.com"),
            graph_api_version=os.getenv("GRAPH_API_VERSION", "v19.0"),
            port=port,
        )
