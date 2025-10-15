import os
import traceback
from dotenv import load_dotenv
from fastapi.responses import PlainTextResponse
from fastapi import APIRouter, Request, Query, HTTPException

from log.logger_config import setup_logging
from services.v1.process_chat import forward_to_chatbot, process_message, send_admin_command

router = APIRouter()
load_dotenv(override=True)
logger = setup_logging(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ADMIN_TAKEOVER_KEY = os.getenv("ADMIN_TAKEOVER_KEY")
ADMIN_RELEASE_KEY = os.getenv("ADMIN_RELEASE_KEY")

@router.get("/")
async def root():
    return PlainTextResponse(content="Webhook service is running.", status_code=200)

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Xác thực thất bại.")

@router.post("/webhook")
async def handle_webhook(request: Request):
    """
    Webhook nâng cấp: Lắng nghe tin nhắn ECHO để thực hiện lệnh admin.
    """
    data = await request.json()
    try:
        await process_message(data=data)
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Lỗi: {e}")
        logger.error(f"Chi tiết lỗi: \n{error_details}")

    return PlainTextResponse(content="OK", status_code=200)