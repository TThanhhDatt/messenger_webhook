# File: main.py của dự án messenger_webhook

import os
import asyncio
import httpx
import json
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
import uvicorn
# --- 1. TẢI CÁC BIẾN MÔI TRƯỜNG ---
load_dotenv(override=True)

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
CHATBOT_URL_PREFIX = os.getenv("CHATBOT_URL_PREFIX")
META_PAGE_ID = os.getenv("META_PAGE_ID")

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
ADMIN_TAKEOVER_KEY = os.getenv("ADMIN_TAKEOVER_KEY")
ADMIN_RELEASE_KEY = os.getenv("ADMIN_RELEASE_KEY")

# --- 2. HÀM GỬI LỆNH ADMIN ĐẾN BOT CHÍNH ---
async def send_admin_command(customer_chat_id: str, command: str):
    """Gửi lệnh (takeover/release) đến API admin của bot chính."""
    if not CHATBOT_URL_PREFIX or not ADMIN_API_KEY:
        print("LỖI: CHATBOT_URL_PREFIX hoặc ADMIN_API_KEY chưa được cấu hình.")
        return

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
                print(f"Gửi lệnh '{command}' thành công cho chat_id: {customer_chat_id}")
            else:
                print(f"Lỗi khi gửi lệnh '{command}': {response.status_code} - {response.text}")
        except httpx.RequestError as e: 
            print(f"Lỗi kết nối khi gửi lệnh admin: {e}")

async def send_cleaned_message_via_bot(customer_chat_id: str, cleaned_text: str):
    """Gửi tin nhắn đã làm sạch đến khách hàng thông qua API của bot chính."""
    if not CHATBOT_URL_PREFIX or not ADMIN_API_KEY:
        print("LỖI: CHATBOT_URL_PREFIX hoặc ADMIN_API_KEY chưa được cấu hình.")
        return

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
                print(f"Gửi tin nhắn đã làm sạch thành công tới: {customer_chat_id}")
            else:
                print(f"Lỗi khi gửi tin nhắn đã làm sạch: {response.status_code} - {response.text}")
        except httpx.RequestError as e:
            print(f"Lỗi kết nối khi gửi tin nhắn đã làm sạch: {e}")

# --- 2. HÀM GỬI TIN NHẮN TRẢ LỜI CHO MESSENGER ---
async def call_send_api(sender_psid: str, response_payload: dict):
    # ... (code của bạn ở đây, không thay đổi) ...
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
            print(f"Gửi tin nhắn thành công tới {sender_psid}")
        except httpx.HTTPStatusError as e:
            print(f"Lỗi HTTP khi gửi tin nhắn: {e.response.text}")

# --- 3. HÀM GỌI ĐẾN BOT CHÍNH (CHATBOT_EDUCATION) (Giữ nguyên) ---
async def forward_to_chatbot(chat_id: str, user_input: str):
    # ... (code của bạn ở đây, không thay đổi) ...
    if not CHATBOT_URL_PREFIX:
        print("CHATBOT_URL_PREFIX chưa được cấu hình.")
        return
    bot_url = f"{CHATBOT_URL_PREFIX}/api/v2/chat"
    payload = {"chat_id": chat_id, "user_input": user_input}
    final_response = ""
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", bot_url, json=payload, timeout=60.0) as response:
                async for line in response.aiter_lines():
                    if line.startswith('data:'):
                        try:
                            json_data = json.loads(line.split('data: ', 1)[1])
                            if "content" in json_data:
                                final_response = json_data["content"]
                        except json.JSONDecodeError:
                            continue
            if final_response:
                await call_send_api(chat_id, {"text": final_response})
        except httpx.RequestError as e:
            print(f"Lỗi khi kết nối đến chatbot chính: {e}")

# --- 4. WEBHOOK ENDPOINT (CỔNG VÀO) ---
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    # ... (code của bạn ở đây, không thay đổi) ...
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Xác thực thất bại.")


@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Webhook nâng cấp: Lắng nghe tin nhắn ECHO để thực hiện lệnh admin.
    """
    data = await request.json()
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                
                # ===== XỬ LÝ LỆNH ADMIN QUA ECHO =====
                if "message" in messaging_event and messaging_event["message"].get("is_echo"):
                    print("Thông báo: Phát hiện tin nhắn echo.")
                    message_text = messaging_event["message"].get("text", "")
                    
                    is_takeover = ADMIN_TAKEOVER_KEY in message_text
                    is_release = ADMIN_RELEASE_KEY in message_text

                    if is_takeover or is_release:
                        customer_id = messaging_event.get("recipient", {}).get("id")
                        command = "takeover" if is_takeover else "release"
                        
                        if customer_id:
                            print(f"Phát hiện lệnh '{command}' trong echo cho khách hàng: {customer_id}")
                            # Tách lấy phần tin nhắn và làm sạch
                            if is_takeover:
                                cleaned_text = message_text.replace(ADMIN_TAKEOVER_KEY, "").strip()
                            else: # is_release
                                cleaned_text = message_text.replace(ADMIN_RELEASE_KEY, "").strip()

                            # Tạo các tác vụ bất đồng bộ
                            tasks = [
                                send_admin_command(customer_id, command)
                            ]
                            
                            # Chỉ gửi tin nhắn nếu có nội dung
                            # if cleaned_text:
                            #     tasks.append(send_cleaned_message_via_bot(customer_id, cleaned_text))
                            
                            # Thực thi đồng thời
                            asyncio.gather(*tasks)
                    continue # Đã xử lý xong echo, bỏ qua các bước sau

                # ===== XỬ LÝ TIN NHẮN THÔNG THƯỜNG (NẾU CÓ) =====
                if "message" in messaging_event and "text" in messaging_event["message"]:
                    sender_id = messaging_event.get("sender", {}).get("id")
                    message_text = messaging_event["message"]["text"]
                    print(f"Nhận diện tin nhắn từ khách hàng {sender_id} -> Nội dung: '{message_text}'")
                    
                    # Chuyển tiếp đến bot để trả lời (hiện tại sẽ không chạy do chưa nhận được sự kiện `messages`)
                    asyncio.create_task(
                        forward_to_chatbot(sender_id, message_text)
                    )
                else:
                    event_type = next((key for key in messaging_event if key not in ['sender', 'recipient', 'timestamp']), "không xác định")
                    print(f"Thông báo: Bỏ qua sự kiện loại '{event_type}'.")

    return PlainTextResponse(content="OK", status_code=200)

@app.get("/")
async def root():
    return PlainTextResponse(content="Webhook service is running.", status_code=200)

if __name__ == '__main__':
    uvicorn.run("main:app",
                host="0.0.0.0",
                port=8020,
                reload=True)