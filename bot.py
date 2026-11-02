#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KenhLive Telegram Bot 24/7 với FreeDeepseekAPI
- Tích hợp FreeDeepseekAPI (mô hình deepseek-v4-flash có sẵn Web Search miễn phí).
- Phong cách trò chuyện tự nhiên, thân thiện như một người bạn / support am hiểu.
- Hoạt động mượt mà cả trong Chat riêng (DM) lẫn trong Nhóm (Tag, Reply, Lệnh /ai, /hoi).
- Chỉ tự động phát sóng file APK khi có PHIÊN BẢN MỚI phát hành (chống spam).
- Vận hành liên tục 24/7 trên GitHub Actions với cơ chế Self-Relay nối tiếp.
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
import re
import html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(BASE_DIR, "last_version.txt")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1004461944549").strip()
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "http://127.0.0.1:9655/v1").strip()
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
VERSION_URL = os.environ.get("VERSION_CHECK_URL", "https://kenhlive-dl.htuananh153.workers.dev/version").strip()
APK_URL = os.environ.get("APK_DOWNLOAD_URL", "https://kenhlive-dl.htuananh153.workers.dev/apk").strip()
GH_PAT = os.environ.get("GH_PAT", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "hanhk112023-jpg/kenhlive-bot").strip()
RUN_DURATION = int(os.environ.get("RUN_DURATION_MINUTES", "0"))

if not BOT_TOKEN:
    cfg_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                BOT_TOKEN = cfg.get("bot_token", "")
        except Exception:
            pass

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOT_USERNAME = "KenhLiveTv_bot"

SYSTEM_PROMPT = """Bạn là một người bạn thông minh, thân thiện và là trợ lý hỗ trợ kỹ thuật nhiệt tình, am hiểu sâu rộng về công nghệ, thể thao, bóng đá và đời sống.

Tính cách & phong cách phản hồi:
1. Giao tiếp tự nhiên, gần gũi, hóm hỉnh và chân thành như một người bạn thân hoặc support chu đáo.
2. Trả lời thẳng vào trọng tâm câu hỏi của người dùng (dù là hỏi về học tập, code, bóng đá quốc tế, tin tức, tâm sự hay chém gió).
3. TUYỆT ĐỐI KHÔNG tự tiện chèn quảng cáo hoặc cố ép nhắc đến 'KenhLive' nếu người dùng không hỏi. Không lặp đi lặp lại những câu chào máy móc.
4. CHỈ KHI người dùng hỏi về: xem trực tiếp bóng đá ở đâu, link xem phim, app KenhLive bị lỗi gì, link tải app APK, hoặc cách cài đặt trên TV:
   - Lúc này mới nhiệt tình hỗ trợ và giới thiệu chi tiết như một người support có tâm.
   - KenhLive có 4 nhà đài thể thao (Socolive, ColaTV, Gà Vàng, Giờ Vàng) và kho phim KKPhim 33k phim.
   - Link tải APK trực tiếp vĩnh viễn: https://kenhlive-dl.htuananh153.workers.dev/apk
   - Cập nhật trong app: Cài đặt -> Kiểm tra cập nhật.
5. Định dạng văn bản gọn gàng, dùng gạch đầu dòng rõ ràng, ngắt dòng thoáng, dễ đọc trên điện thoại."""

def tg_request(method, payload=None):
    url = f"{TELEGRAM_API}/{method}"
    headers = {"User-Agent": "KenhLiveBot/2.0"}
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
    res = tg_request("sendMessage", payload)
    if not res or not res.get("ok"):
        payload["parse_mode"] = None
        res = tg_request("sendMessage", payload)
    return res

def search_web_ddg(query, max_results=3):
    """Tìm kiếm web nhanh qua DuckDuckGo để bổ sung thông tin thời gian thực."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            snippets = re.findall(r'<a[^>]+class=[\"\']result__snippet[\"\'][^>]*>(.*?)</a>', raw, re.DOTALL)
            results = []
            for s in snippets[:max_results]:
                clean = re.sub(r'<[^>]+>', '', s).strip()
                clean = html.unescape(clean)
                if clean:
                    results.append(clean)
            return results
    except Exception:
        return []

def ask_deepseek(user_prompt):
    """Gọi DeepSeek AI (FreeDeepseekAPI trên localhost:9655 hoặc proxy)."""
    search_context = ""
    keywords = ["kết quả", "bảng xếp hạng", "tin tức", "hôm nay", "mới nhất", "giá", "thời tiết", "tỉ số", "lịch thi đấu"]
    if any(k in user_prompt.lower() for k in keywords):
        snippets = search_web_ddg(user_prompt, max_results=3)
        if snippets:
            search_context = "\n\n[Dữ liệu tra cứu web thời gian thực]:\n" + "\n".join(f"- {s}" for s in snippets)

    prompt_content = user_prompt + search_context

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt_content}
    ]

    try:
        req_data = json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "max_tokens": 1200,
            "temperature": 0.7
        }).encode("utf-8")
        cloud_req = urllib.request.Request(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            data=req_data,
            headers={
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(cloud_req, timeout=40) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            ans = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if ans:
                return ans
    except Exception as e:
        logging.error(f"FreeDeepseekAPI error ({DEEPSEEK_BASE_URL}): {e}")

    return "Chào bạn! Hiện tại kết nối AI đang được kết nối lại trong giây lát. Nếu bạn cần tải app KenhLive mới nhất hoặc cần trợ giúp gấp, bạn có thể bấm /link hoặc hỏi lại mình sau 1 phút nhé!"

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
            return

        logging.info(f"Phát hiện phiên bản mới: {latest_tag} (Bản cũ đã gửi: {last_sent}). Tải và phát sóng APK...")
        temp_apk = os.path.join(BASE_DIR, f"KenhLive-{latest_tag}.apk")
        
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
    reply_from = reply_to.get("from", {})
    is_reply_to_bot = (reply_from.get("username") == BOT_USERNAME or reply_from.get("is_bot") and reply_from.get("id") == 9036540834)
    is_mentioned = f"@{BOT_USERNAME}".lower() in text.lower()
    is_command = text.startswith("/")

    if not (is_private or is_reply_to_bot or is_mentioned or is_command):
        return

    logging.info(f"Tin nhắn từ [{chat_id}] ({chat_type}): {text}")

    clean_text = text
    clean_text = re.sub(rf"@{BOT_USERNAME}\b", "", clean_text, flags=re.IGNORECASE).strip()

    lower_text = clean_text.lower()
    if lower_text.startswith("/start"):
        welcome = (
            "Chào bạn! 👋 Mình là trợ lý AI thông minh.\n\n"
            "Bạn có thể trò chuyện với mình về bất kỳ chủ đề gì: bóng đá, tin tức, công nghệ hay đời sống.\n\n"
            "📌 <b>Một số lệnh tiện ích:</b>\n"
            "• /link hoặc /apk - Lấy link tải KenhLive TV mới nhất\n"
            "• /ai [câu hỏi] - Hỏi đáp nhanh cùng AI (trong nhóm hoặc DM)\n"
            "• Trong nhóm: Tag @KenhLiveTv_bot hoặc Trả lời (Reply) tin nhắn của mình để trò chuyện nhé!"
        )
        send_message(chat_id, welcome, reply_to_message_id=msg_id)
        return

    if lower_text.startswith("/apk") or lower_text.startswith("/link") or "xin link" in lower_text or "tải app" in lower_text:
        msg_out = (
            "🚀 <b>TẢI ỨNG DỤNG KENHLIVE TV:</b>\n\n"
            "• <b>Link tải trực tiếp APK (bản mới nhất):</b>\n"
            "👉 https://kenhlive-dl.htuananh153.workers.dev/apk\n\n"
            "• <b>Tự động cập nhật:</b> Trên ứng dụng, vào <b>Cài đặt ➔ Kiểm tra cập nhật ➔ TẢI NGAY</b>.\n\n"
            "<i>(Hỗ trợ mượt mà trên tất cả Android TV, Smart TV, Google TV và TV Box)</i>"
        )
        send_message(chat_id, msg_out, reply_to_message_id=msg_id)
        return

    for cmd_prefix in ["/ai", "/hoi", "/chat", "/search"]:
        if clean_text.lower().startswith(cmd_prefix):
            clean_text = clean_text[len(cmd_prefix):].strip()
            break

    if not clean_text:
        send_message(chat_id, "Bạn cứ hỏi thoải mái nhé, mình đang lắng nghe đây! 😊", reply_to_message_id=msg_id)
        return

    send_chat_action(chat_id, "typing")
    reply = ask_deepseek(clean_text)
    send_message(chat_id, reply, reply_to_message_id=msg_id)

def trigger_next_runner():
    """Tự động kích hoạt GitHub Actions runner mới trước khi hết 330 phút."""
    if not GH_PAT or not REPO:
        logging.warning("Không có GH_PAT hoặc REPO để kích hoạt self-relay.")
        return

    logging.info("Chuẩn bị kích hoạt GitHub Actions runner mới để duy trì 24/7...")
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/bot-247.yml/dispatches"
    data = json.dumps({"ref": "main"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {GH_PAT}",
            "User-Agent": "KenhLive-Relay"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status in (200, 204):
                logging.info("Đã kích hoạt thành công runner mới! Bàn giao tiếp nối an toàn.")
            else:
                logging.warning(f"Self-relay response code: {resp.status}")
    except Exception as e:
        logging.error(f"Lỗi khi kích hoạt self-relay: {e}")

def main():
    logging.info("==========================================")
    logging.info("  KenhLive Bot 24/7 với FreeDeepseekAPI   ")
    logging.info("==========================================")
    logging.info(f"DeepSeek Base URL: {DEEPSEEK_BASE_URL} (Model: {DEEPSEEK_MODEL})")

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

    watcher = threading.Thread(target=version_watcher_loop, daemon=True)
    watcher.start()

    tg_request("getUpdates", {"offset": -1, "timeout": 1})

    offset = 0
    start_time = time.time()
    logging.info("Bot đang trực tuyến 24/7 và sẵn sàng hỗ trợ!")

    while True:
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
