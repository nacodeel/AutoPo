import os
from openai import OpenAI
from pydantic import BaseModel

from .config import config
from .get_system import get_system

os.environ["http_proxy"] = config.PROXY_URL
os.environ["https_proxy"] = config.PROXY_URL

client = OpenAI(api_key=config.OPENAI_API_KEY)


class Translate(BaseModel):
    language: str
    translate: str


class Response(BaseModel):
    translations: list[Translate]


def translate(text: str, languages: list[str]):
    completion = client.beta.chat.completions.parse(
        model=config.MODEL,
        messages=[
            {"role": "developer", "content": get_system()},
            {"role": "user", "content": str({"text": text, "languages": languages})}
        ],
        response_format=Response
    )
    return completion.choices[0].message.parsed