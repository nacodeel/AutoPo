from pydantic_settings import BaseSettings
from pydantic import Field


class Configuration(BaseSettings):
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    MODEL: str = Field(..., env="MODEL")
    PROXY_URL: str = Field(..., env="PROXY_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


config = Configuration()