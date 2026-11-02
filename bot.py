#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KenhLive Telegram Bot 24/7 với DeepSeek AI
- Trả lời tin nhắn thông minh qua DeepSeek AI (DM hoặc tag/reply trong nhóm).
- Chỉ tự động gửi file APK khi có PHIÊN BẢN MỚI được phát hành (không spam file cũ).
- Hỗ trợ chạy liên tục 24/7 trên GitHub Actions với cơ chế tự khởi động nối tiếp (Self-Relay).
"""

import os
import sys
import time
import json
import logging
import urllib.request
import urllib.parse
import threading
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, "last_version.txt")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1004461944549").strip()
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://literouter.fun/v1").strip()
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4.1-flash-1017").strip()
VERSION_URL = os.environ.get("VERSION_CHECK_URL", "https://kenhlive-dl.htuananh153.workers.dev/version").strip()
APK_URL = os.environ.get("APK_DOWNLOAD_URL", "https://kenhlive-dl.htuananh153.workers.dev/apk").strip()
GH_PAT = os.environ.get("GH_PAT", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "hanhk112023-jpg/kenhlive-bot").strip()
RUN_DURATION = int(os.environ.get("RUN_DURATION_MINUTES", "0"))

if not BOT_TOKEN:
    # Thử nạp từ config.json nếu có
    cfg_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                BOT_TOKEN = cfg.get("bot_token", "")
                if not DEEPSEEK_API_KEY:
                    DEEPSEEK_API_KEY = cfg.get("deepseek_api_key", "")
        except Exception:
            pass

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOT_USERNAME = "KenhLiveTv_bot"

SYSTEM_PROMPT = """Bạn là trợ lý AI thông minh chính thức của ứng dụng KenhLive (KenhLive TV & KenhLive iOS).
Nhiệm vụ của bạn:
1. Giải đáp thắc mắc về ứng dụng KenhLive:
   - Thể thao trực tiếp 4 nhà đài: Socolive TV, ColaTV, Gà Vàng 33, Giờ Vàng TV (đầy đủ các giải Ngoại Hạng Anh, C1, La Liga, Serie A, V-League...).
   - Kho phim truyện KKPhim với hơn 33.000 phim thuyết minh/vietsub chuẩn 4K, hỗ trợ lưu lịch sử và xem tiếp.
   - Hướng dẫn cài đặt trên Android TV, Google TV, Android Box, Smart TV và iOS.
2. Link tải APK trực tiếp vĩnh viễn (luôn là bản mới nhất): https://kenhlive-dl.htuananh153.workers.dev/apk
3. Cách cập nhật: Trong app chọn Cài đặt ➔ Kiểm tra cập nhật ➔ TẢI NGAY.
4. Phong cách trả lời: Thân thiện, ngắn gọn, súc tích, định dạng gạch đầu dòng rõ ràng, dùng tiếng Việt chuẩn."""

def tg_request(method, payload=None):
    url = f"{TELEGRAM_API}/{method}"
    headers = {"User-Agent": "KenhLiveBot/1.0"}
    data = None
    if payload:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logging.error(f"Telegram API {method} error: {e}")
        return None

def send_chat_action(chat_id, action="typing"):
    tg_request("sendChatAction", {"chat_id": chat_id, "action": action})

def send_message(chat_id, text, reply_to_message_id=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    return tg_request("sendMessage", payload)

def ask_deepseek(user_prompt):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    try:
        req_data = json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "max_tokens": 650,
            "temperature": 0.7
        }).encode("utf-8")
        cloud_req = urllib.request.Request(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            }
        )
        with urllib.request.urlopen(cloud_req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            ans = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if ans:
                return ans
    except Exception as e:
        logging.error(f"DeepSeek API error: {e}")

    return "Dạ hiện tại AI DeepSeek đang bận xử lý, bạn vui lòng thử lại sau chút xíu nhé! Bạn có thể tải ngay app KenhLive bản mới nhất tại: https://kenhlive-dl.htuananh153.workers.dev/apk"

def get_last_sent_version():
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

def set_last_sent_version(ver):
    try:
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(ver.strip())
    except Exception as e:
        logging.error(f"Error saving last version: {e}")

def check_and_broadcast_new_apk():
    """Kiểm tra và CHỈ gửi APK khi có phiên bản mới hơn phiên bản đã gửi lần trước."""
    try:
        req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "KenhLiveBot"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latest_tag = data.get("tag", "").strip()
        if not latest_tag:
            return

        last_sent = get_last_sent_version()
        if last_sent == latest_tag:
            return  # Đã gửi bản này rồi, không gửi lặp lại!

        logging.info(f"Phát hiện phiên bản mới: {latest_tag} (Bản cũ đã gửi: {last_sent}). Tải và phát sóng APK...")
        temp_apk = os.path.join(BASE_DIR, f"KenhLive-{latest_tag}.apk")
        
        # Tải file APK mới
        dl_req = urllib.request.Request(APK_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(dl_req, timeout=60) as dl_resp:
            with open(temp_apk, "wb") as f:
                f.write(dl_resp.read())

        fsize_mb = round(os.path.getsize(temp_apk) / (1024 * 1024), 2)
        caption = (
            f"🚀 <b>PHÁT HÀNH BẢN MỚI: KenhLive TV {latest_tag}</b>\n\n"
            f"📦 <i>Dung lượng: {fsize_mb} MB (Universal APK cho Android TV & TV Box)</i>\n"
            f"• Tự động cập nhật trực tiếp trên app: <b>Cài đặt ➔ Kiểm tra cập nhật</b>\n"
            f"• Link tải trực tiếp vĩnh viễn: https://kenhlive-dl.htuananh153.workers.dev/apk\n\n"
            f"<i>Cài đè trực tiếp file APK đính kèm bên dưới để nâng cấp!</i>"
        )

        cmd = [
            "curl", "-s", "-S",
            "-F", f"chat_id={DEFAULT_CHAT_ID}",
            "-F", "parse_mode=HTML",
            "-F", f"caption={caption}",
            "-F", f"document=@{temp_apk}",
            f"{TELEGRAM_API}/sendDocument"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if '"ok":true' in res.stdout:
            logging.info(f"Gửi thành công APK {latest_tag} vào nhóm {DEFAULT_CHAT_ID}")
            set_last_sent_version(latest_tag)
        else:
            logging.error(f"Lỗi khi gửi APK: {res.stdout}")

        if os.path.exists(temp_apk):
            os.remove(temp_apk)

    except Exception as e:
        logging.error(f"Lỗi kiểm tra phiên bản mới: {e}")

def version_watcher_loop():
    while True:
        try:
            check_and_broadcast_new_apk()
        except Exception as e:
            logging.error(f"Watcher loop error: {e}")
        time.sleep(120)

def handle_message(msg):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type", "")
    msg_id = msg.get("message_id")
    text = (msg.get("text") or msg.get("caption") or "").strip()

    if not text or not chat_id:
        return

    is_private = (chat_type == "private")
    reply_to = msg.get("reply_to_message", {})
    is_reply_to_bot = reply_to.get("from", {}).get("username") == BOT_USERNAME
    is_mentioned = f"@{BOT_USERNAME}".lower() in text.lower()
    is_command = text.startswith("/")

    if not (is_private or is_reply_to_bot or is_mentioned or is_command):
        return

    clean_text = text.replace(f"@{BOT_USERNAME}", "").strip()

    if clean_text.startswith("/start") or clean_text.startswith("/help"):
        intro = (
            "👋 <b>Xin chào bạn! Mình là Bot Trợ Lý KenhLive TV</b> 🤖\n\n"
            "✨ <b>Tích hợp DeepSeek AI</b> hỗ trợ 24/7 mọi thắc mắc về:\n"
            "• ⚽ Xem trực tiếp 4 nhà đài: Socolive, ColaTV, Gà Vàng 33, Giờ Vàng TV\n"
            "• 🎬 Kho phim truyện KKPhim hơn 33.000 phim chuẩn 4K\n"
            "• 📺 Hướng dẫn cài đặt và tối ưu Android TV, TV Box & iOS\n\n"
            "📥 <b>Lệnh nhanh:</b>\n"
            "• /apk hoặc /link : Lấy link tải bản APK mới nhất\n"
            "• Cứ chat hoặc tag @KenhLiveTv_bot trong nhóm để trò chuyện cùng DeepSeek AI nhé!"
        )
        send_message(chat_id, intro, reply_to_message_id=msg_id)
        return

    if clean_text.startswith("/apk") or clean_text.startswith("/link") or clean_text.startswith("/capnhat"):
        try:
            req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "KenhLiveBot"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tag = data.get("tag", "v7.8.0")
        except Exception:
            tag = "Mới nhất"

        apk_msg = (
            f"🚀 <b>KENHLIVE TV ({tag}) — BẢN CẬP NHẬT MỚI NHẤT</b>\n\n"
            f"🔗 <b>Link tải APK trực tiếp:</b>\n"
            f"👉 https://kenhlive-dl.htuananh153.workers.dev/apk\n\n"
            f"💡 <b>Cập nhật trên Android TV / Box:</b>\n"
            f"1. Vào mục <b>Cài đặt</b> trên thanh điều hướng bên trái\n"
            f"2. Chọn <b>Kiểm tra cập nhật</b> ➔ Bấm <b>TẢI NGAY</b>\n"
            f"3. Ứng dụng tự động tải ngầm và mở cài đặt đè giữ nguyên dữ liệu."
        )
        send_message(chat_id, apk_msg, reply_to_message_id=msg_id)
        return

    # Chat thông minh với DeepSeek AI
    send_chat_action(chat_id, "typing")
    prompt = clean_text.lstrip("/ask").lstrip("/ai").strip()
    if not prompt:
        prompt = "Xin chào! Bạn có thể giúp gì cho mình về KenhLive?"

    reply = ask_deepseek(prompt)
    send_message(chat_id, reply, reply_to_message_id=msg_id, parse_mode="Markdown")

def trigger_next_runner():
    """Tự động kích hoạt GitHub Actions runner tiếp theo trước khi runner hiện tại hết giờ."""
    if not GH_PAT:
        logging.warning("Không có GH_PAT, không thể tự động trigger runner tiếp theo.")
        return
    try:
        url = f"https://api.github.com/repos/{REPO}/actions/workflows/bot-247.yml/dispatches"
        req_data = json.dumps({"ref": "main"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {GH_PAT}",
                "User-Agent": "KenhLiveRelay"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            logging.info(f"Relay trigger runner tiếp theo thành công (Status: {resp.status})")
    except Exception as e:
        logging.error(f"Lỗi khi trigger runner tiếp theo: {e}")

def main():
    logging.info(f"Khởi động KenhLive Telegram Bot (@{BOT_USERNAME})...")
    
    # Khởi tạo bản ghim ban đầu để không gửi lại bản cũ
    try:
        req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "KenhLiveBot"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cur_tag = data.get("tag", "").strip()
            if cur_tag and not get_last_sent_version():
                set_last_sent_version(cur_tag)
                logging.info(f"Đã ghim phiên bản hiện tại: {cur_tag} (chỉ gửi APK khi có bản mới hơn)")
    except Exception as e:
        logging.warning(f"Không thể lấy tag ban đầu: {e}")

    # Bật watcher theo dõi phiên bản mới
    watcher = threading.Thread(target=version_watcher_loop, daemon=True)
    watcher.start()

    # Bỏ qua backlog cũ
    tg_request("getUpdates", {"offset": -1, "timeout": 1})

    offset = 0
    start_time = time.time()
    logging.info("Bot đang trực tuyến 24/7 và sẵn sàng chat DeepSeek AI!")

    while True:
        # Kiểm tra nếu chạy trên GitHub Actions runner và sắp đạt giới hạn thời gian (ví dụ 340 phút)
        if RUN_DURATION > 0:
            elapsed_minutes = (time.time() - start_time) / 60.0
            if elapsed_minutes >= RUN_DURATION:
                logging.info(f"Đã chạy đủ {RUN_DURATION} phút. Kích hoạt runner tiếp theo và bàn giao...")
                trigger_next_runner()
                time.sleep(10)
                sys.exit(0)

        try:
            updates = tg_request("getUpdates", {"offset": offset, "timeout": 20, "allowed_updates": ["message"]})
            if updates and updates.get("ok"):
                for item in updates.get("result", []):
                    offset = item["update_id"] + 1
                    msg = item.get("message")
                    if msg:
                        try:
                            handle_message(msg)
                        except Exception as ex:
                            logging.error(f"Error handling msg: {ex}")
            time.sleep(0.5)
        except Exception as e:
            logging.error(f"Polling exception: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
