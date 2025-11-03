from pydantic import BaseModel


class BasePlatform(BaseModel):
    name: str

    def __hash__(self):
        return hash(self.name)
