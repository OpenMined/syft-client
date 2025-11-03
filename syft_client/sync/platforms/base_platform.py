from pydantic import BaseModel


class BasePlatform(BaseModel):
    name: str
