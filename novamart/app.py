"""novamart API service."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db, logutil
from .routers import accounts, carts, catalog, orders, similar


@asynccontextmanager
async def lifespan(app):
    await db.pool.open()
    yield
    await db.pool.close()
    logutil.close_all()


app = FastAPI(title="novamart", lifespan=lifespan)
app.include_router(accounts.router)
app.include_router(catalog.router)
app.include_router(carts.router)
app.include_router(orders.router)
app.include_router(similar.router)


@app.get("/health")
async def health():
    return {"ok": True}
