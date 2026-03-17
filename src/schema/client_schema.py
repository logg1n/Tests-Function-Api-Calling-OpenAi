from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, HttpUrl, PrivateAttr, SecretStr

from src.schema.settings import api_keys_storage

StrUrl = Annotated[HttpUrl, AfterValidator(lambda v: str(v))]


class ModelsConfig(BaseModel):
    name: str
    semaphore: int = Field(ge=1)
    max_tokens: int = Field(ge=1)
    temperature: float = Field(ge=0.0, le=2.0)

    _properties: dict[str, Any] = PrivateAttr(default_factory=dict)


class AggregatorConfig(BaseModel):
    name: str
    base_url: StrUrl
    models: ModelsConfig
    role: str
    timeout: int = Field(default=60, ge=1)
    tool_choice: Literal["none", "auto", "required"] = "auto"

    max_retries: int = Field(default=3, ge=1)
    retry_delay: float = Field(default=1.3, ge=0.5)

    api_key: SecretStr | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.api_key:
            self.api_key = api_keys_storage.get_key_for(self.name)

            if not self.api_key:
                raise ValueError(f"API key for {self.name} not found in ENV/Secrets")


class ClientModel(BaseModel):
    aggregator: AggregatorConfig

    _request_token: int = PrivateAttr(default=0)
    _response_token: int = PrivateAttr(default=0)
    _total_token: int = PrivateAttr(default=0)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
