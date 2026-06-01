from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import os

from src.api.routers import approval, activity, contacts, people, research, inbox, marketing, drafts, api_auth
from src.api import auth

app = FastAPI(title="ArtCRM Supervisor", docs_url=None, redoc_url=None)

SESSION_SECRET = os.environ.get("SESSION_SECRET", "change-me-in-production")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

UI_DIR = Path(__file__).parent.parent / "ui"
app.mount("/static", StaticFiles(directory=str(UI_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(UI_DIR / "templates"))

app.include_router(auth.router)
app.include_router(api_auth.router)
app.include_router(approval.router)
app.include_router(activity.router)
app.include_router(contacts.router)
app.include_router(people.router)
app.include_router(research.router)
app.include_router(inbox.router)
app.include_router(marketing.router)
app.include_router(drafts.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return RedirectResponse(url="/approvals/")


def run():
    import uvicorn
    from src.config import HOST, PORT
    uvicorn.run("src.api.main:app", host=HOST, port=PORT, reload=True)


if __name__ == "__main__":
    run()
