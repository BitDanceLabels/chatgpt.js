# FastAPI bridge for chatgpt.js

Backend nhỏ dùng Playwright để mở ChatGPT web, inject `chatgpt.js` và cung cấp API đơn giản.

## Cấu trúc
```
server/
  app/
    main.py       # FastAPI endpoints
    chatgpt.py    # Quản lý phiên Playwright + chatgpt.js
    schemas.py    # Pydantic models
  requirements.txt
```

## Chuẩn bị
```bash
cd /mnt/d/NHUTPHAM-GIT-D/chatgpt.js
pip install -r server/requirements.txt
python -m playwright install chromium
```

Tạo môi trường ảo (tuỳ chọn, khuyến nghị):
```bash
cd /mnt/d/NHUTPHAM-GIT-D/chatgpt.js
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r server/requirements.txt
python -m playwright install chromium
```

Biến môi trường (tùy chọn):
- `HEADLESS` (mặc định true) – để login lần đầu, đặt `false`.
- `USER_DATA_DIR` (mặc định `./.chatgpt-session`) – nơi lưu session ChatGPT.
- `NAV_TIMEOUT_MS` (mặc định 30000).
- `CHROME_EXECUTABLE` – nếu muốn chỉ định trình duyệt.
- `BYPASS_CSP` (mặc định true) – bật bypass CSP cho Playwright để inject `chatgpt.js`.
- `IGNORE_AUTOMATION_FLAG` (mặc định true) – bỏ cờ `--disable-blink-features=AutomationControlled` để giảm banner “controlled by automated test software”.
- `CHROMIUM_ARGS` – chuỗi arg bổ sung, ví dụ `--lang=en-US`.

### Dùng Chrome thật + profile riêng (khuyến nghị nếu muốn tránh nghi ngờ tự động)
- Tạo một profile Chrome phụ, đăng nhập ChatGPT trong profile đó.
- Đặt env:
  - `CHROME_EXECUTABLE="C:\Program Files\Google\Chrome\Application\chrome.exe"` (Windows) hoặc đường dẫn Chrome bạn dùng.
  - `USER_DATA_DIR="C:\Users\<you>\AppData\Local\Google\Chrome\User Data\Profile GPT"` (thay đường dẫn profile phụ).
  - `HEADLESS=false` lần đầu để login/captcha; sau đó có thể `HEADLESS=true`.
- Lưu ý: không nên dùng profile chính chứa dữ liệu cá nhân; giữ `USER_DATA_DIR` cố định để tái dùng phiên, tránh phải login lại.
- Nếu không dùng profile phụ, vẫn có thể chạy với session riêng trong repo:
```bat
set CHROME_EXECUTABLE=C:\Program Files\Google\Chrome\Application\chrome.exe
set HEADLESS=false
set USER_DATA_DIR=./.chatgpt-session
set BYPASS_CSP=true
set IGNORE_AUTOMATION_FLAG=true
uvicorn server.app.main:app --port 8033
```
  Login/captcha xong, lần sau đổi `HEADLESS=true` (hoặc bỏ biến) và có thể dùng port khác tuỳ ý.

## Đăng nhập lần đầu
Chạy headful để tự nhập tài khoản, sau đó tái dùng session:
```bash
HEADLESS=false USER_DATA_DIR=./.chatgpt-session uvicorn server.app.main:app --reload --port 8000
```
Một cửa sổ Chromium mở ra → đăng nhập ChatGPT → giữ nguyên thư mục `.chatgpt-session`.

## Chạy server headless (sau khi đã login)
```bash
HEADLESS=true USER_DATA_DIR=./.chatgpt-session uvicorn server.app.main:app --reload --port 8000
```

## Dùng trình duyệt riêng (Chrome/Edge)
Ví dụ Linux/macOS:
```bash
CHROME_EXECUTABLE="/usr/bin/google-chrome" HEADLESS=true USER_DATA_DIR=./.chatgpt-session uvicorn server.app.main:app --reload --port 8000
```
Ví dụ Windows (cmd):
```bat
set CHROME_EXECUTABLE=C:\Program Files\Google\Chrome\Application\chrome.exe
set HEADLESS=true
set USER_DATA_DIR=./.chatgpt-session
uvicorn server.app.main:app --reload --port 8000
```
Ví dụ Windows (PowerShell):
```powershell
$env:CHROME_EXECUTABLE="C:\Program Files\Google\Chrome\Application\chrome.exe"
$env:HEADLESS="true"
$env:USER_DATA_DIR="./.chatgpt-session"
uvicorn server.app.main:app --reload --port 8000
```
Nếu cần login headful trên Windows, đổi `HEADLESS` thành `false` và có thể dùng port khác (ví dụ 8033).

**Lưu ý Windows:** code đã set Proactor event loop trong `main.py`; nếu vẫn gặp lỗi `NotImplementedError` khi khởi động Playwright, thử tắt `--reload`.

## Endpoints
- `GET /healthz` – kiểm tra server sống.
- `GET /status` – trạng thái phiên, idle hay không.
- `POST /ask` – body `{ "prompt": "...", "timeout": 60 }`.
- `POST /continue` – yêu cầu ChatGPT viết tiếp.
- `POST /stop` – dừng generate.
- `GET /history` – lấy dữ liệu chat (tùy chatgpt.js hỗ trợ).
- `GET /last-reply` – lấy reply mới nhất.
- `POST /clear` – bắt đầu chat mới/clear.

## Curl nhanh
```bash
# health
curl http://localhost:8000/healthz

# status
curl http://localhost:8000/status

# ask
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello from curl","timeout":60}'

# continue
curl -X POST http://localhost:8000/continue

# stop
curl -X POST http://localhost:8000/stop

# history
curl http://localhost:8000/history

# last reply
curl http://localhost:8000/last-reply

# clear
curl -X POST http://localhost:8000/clear
```

## Hướng dẫn Postman (dễ copy)
1. New Request → Method GET → URL `http://localhost:8000/status` → Send.
2. New Request → Method POST → URL `http://localhost:8000/ask` → Body → raw → JSON:
   ```json
   { "prompt": "Viết mô tả sản phẩm về Bumbee AI", "timeout": 60 }
   ```
   Headers: `Content-Type: application/json`.
3. POST `http://localhost:8000/continue` → Body none.
4. POST `http://localhost:8000/stop` → Body none.
5. GET `http://localhost:8000/history`.
6. GET `http://localhost:8000/last-reply`.
7. POST `http://localhost:8000/clear` → Body none.

## Lưu ý
- Phải có phiên ChatGPT đã đăng nhập; nếu cookie hết hạn, chạy lại headful để đăng nhập.
- CORS đang mở để dev, cần khóa lại origin khi chạy production.
- Mọi call đều điều khiển DOM, nên dùng `asyncio.Lock` để nối tiếp yêu cầu (đã có sẵn).
