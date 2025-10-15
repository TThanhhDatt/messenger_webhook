import os
import json
import httpx
import asyncio
import traceback
from dotenv import load_dotenv

from log.logger_config import setup_logging

load_dotenv(override=True)
logger = setup_logging(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
CHATBOT_URL_PREFIX = os.getenv("CHATBOT_URL_PREFIX")
CHATBOT_URL_WEBHOOK = os.getenv("CHATBOT_URL_WEBHOOK")
META_PAGE_ID = os.getenv("META_PAGE_ID")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
ADMIN_TAKEOVER_KEY = os.getenv("ADMIN_TAKEOVER_KEY")
ADMIN_RELEASE_KEY = os.getenv("ADMIN_RELEASE_KEY")

async def send_admin_command(customer_chat_id: str, command: str):
    """Gửi lệnh (takeover/release) đến API admin của bot chính."""
    command_url = f"{CHATBOT_URL_PREFIX}/admin/conversations/{command}"
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "api-key": ADMIN_API_KEY  # Add the API key to the headers
    }
    payload = {"chat_id": customer_chat_id}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(command_url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info(f"Gửi lệnh '{command}' thành công cho chat_id: {customer_chat_id}")
            else:
                logger.error(f"Lỗi khi gửi lệnh '{command}': {response.status_code} - {response.text}")
        except httpx.RequestError as e: 
            error_details = traceback.format_exc()
            logger.error(f"Lỗi kết nối khi gửi lệnh admin: {e}")
            logger.error(f"Chi tiết lỗi: \n{error_details}")

async def send_cleaned_message_via_bot(customer_chat_id: str, cleaned_text: str):
    """
    Gửi tin nhắn đã làm sạch đến khách hàng thông qua API của bot chính.
    """
    
    # Sử dụng endpoint send_message của bot chính
    send_url = f"{CHATBOT_URL_PREFIX}/admin/conversations/send_message"
    headers = {
        "Content-Type": "application/json",
        "api-key": ADMIN_API_KEY
    }
    payload = {"chat_id": customer_chat_id, "text": cleaned_text}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(send_url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info(f"Gửi tin nhắn đã làm sạch thành công tới: {customer_chat_id}")
            else:
                logger.error(f"Lỗi khi gửi tin nhắn đã làm sạch: {response.status_code} - {response.text}")
        except httpx.RequestError as e:
            error_details = traceback.format_exc()
            logger.error(f"Lỗi kết nối khi gửi tin nhắn đã làm sạch: {e}")
            logger.error(f"Chi tiết lỗi: \n{error_details}")


async def call_send_api(sender_psid: str, response_payload: dict):
    url = "https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": sender_psid},
        "message": response_payload,
        "messaging_type": "RESPONSE"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, params=params, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Gửi tin nhắn thành công tới {sender_psid}")
        except httpx.HTTPStatusError as e:
            error_details = traceback.format_exc()
            logger.error(f"Lỗi HTTP khi gửi tin nhắn: {e.response.text}")
            logger.error(f"Chi tiết lỗi: \n{error_details}")

async def forward_to_chatbot(chat_id: str, user_input: str, timeout: float = 60.0):
    payload = {"chat_id": chat_id, "user_input": user_input}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(CHATBOT_URL_WEBHOOK, json=payload, timeout=timeout)
            resp.raise_for_status()
            
            logger.info(f"chat_id: {chat_id} | Server process successfully: {resp.text}")
        except httpx.RequestError as e:
            error_details = traceback.format_exc()
            logger.error(f"Request error when calling chatbot: {e}")
            logger.error(f"Error detail: \n{error_details}")
            
        except httpx.HTTPStatusError as e:
            error_details = traceback.format_exc()
            logger.error(f"HTTP error response from chatbot: {e.response.status_code} / {e.response.text}")
            logger.error(f"Error detail: \n{error_details}")
            
        except json.JSONDecodeError as e:
            error_details = traceback.format_exc()
            logger.error(f"Failed to decode JSON from chatbot response: {e}")
            logger.error(f"Error detail: \n{error_details}")
            
async def process_message(data: dict):
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                # Process admin message via echo
                if "message" in messaging_event and messaging_event["message"].get("is_echo"):
                    logger.info("Thông báo: Phát hiện tin nhắn echo.")
                    message_text = messaging_event["message"].get("text", "")
                    
                    is_takeover = ADMIN_TAKEOVER_KEY in message_text
                    is_release = ADMIN_RELEASE_KEY in message_text

                    if is_takeover or is_release:
                        customer_id = messaging_event.get("recipient", {}).get("id")
                        command = "takeover" if is_takeover else "release"
                        
                        if customer_id:
                            logger.info(f"Phát hiện lệnh '{command}' trong echo cho khách hàng: {customer_id}")
                            if is_takeover:
                                cleaned_text = message_text.replace(ADMIN_TAKEOVER_KEY, "").strip()
                            else: # is_release
                                cleaned_text = message_text.replace(ADMIN_RELEASE_KEY, "").strip()

                            # Tạo các tác vụ bất đồng bộ
                            tasks = [send_admin_command(customer_id, command)]
                            
                            # Chỉ gửi tin nhắn nếu có nội dung
                            # if cleaned_text:
                            #     tasks.append(send_cleaned_message_via_bot(customer_id, cleaned_text))
                            
                            # Thực thi đồng thời
                            asyncio.gather(*tasks)
                    continue

                # Process normal message
                if "message" in messaging_event and "text" in messaging_event["message"]:
                    sender_id = messaging_event.get("sender", {}).get("id")
                    message_text = messaging_event["message"]["text"]
                    logger.info(f"Nhận diện tin nhắn từ khách hàng {sender_id} -> Nội dung: '{message_text}'")
                    
                    asyncio.create_task(
                        forward_to_chatbot(sender_id, message_text)
                    )
                else:
                    event_type = next(
                        (key for key in messaging_event if key not in ['sender', 'recipient', 'timestamp']), 
                        "không xác định"
                    )
                    logger.info(f"Thông báo: Bỏ qua sự kiện loại '{event_type}'.")