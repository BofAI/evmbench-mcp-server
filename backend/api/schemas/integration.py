from pydantic import BaseModel


class FrontendConfig(BaseModel):
    auth_enabled: bool
    key_predefined: bool
    azure_model: str | None = None
