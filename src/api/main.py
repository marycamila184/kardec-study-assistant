from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(title="Dialogando com a Doutrina")
app.include_router(router)
