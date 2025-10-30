from pydantic import BaseModel


class Peer(BaseModel):
    email: str
