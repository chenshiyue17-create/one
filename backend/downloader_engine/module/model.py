from pydantic import BaseModel


class ExtractParams(BaseModel):
    url: str
    download: bool = False
    index: list[int] = None
    cookie: str = None
    proxy: str = None
    skip: bool = False
    work_path: str = None
    task_id: str = None



class ExtractData(BaseModel):
    message: str
    params: ExtractParams
    data: dict | None
