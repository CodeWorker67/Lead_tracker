from api.handlers import payments, users
from fastapi import Depends, FastAPI, Header, HTTPException

from config import settings


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid X-API-KEY")


app = FastAPI(dependencies=[Depends(verify_api_key)])

app.include_router(users.router)
app.include_router(payments.router)
