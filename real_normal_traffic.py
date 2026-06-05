import requests
import time
import random

TARGET_URL = "http://127.0.0.1"
normal_paths = ["/"]  # 경로도 템플릿에 맞게 고정

# id_map.json의 219번 템플릿과 일치하는 User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.131 Safari/537.36"
}

print("========================================")
print(" 🟢 정상 웹 트래픽 자동 발생기 가동 🟢")
print("========================================")

try:
    while True:
        path = random.choice(normal_paths)
        try:
            res = requests.get(TARGET_URL + path, headers=HEADERS, timeout=2)
            print(f"[정상 접속] {path} -> 응답: {res.status_code}")
        except Exception:
            print(f"[접속 실패] 아파치 서버 확인 필요")

        time.sleep(random.uniform(1, 3))
except KeyboardInterrupt:
    print("\n[!] 정상 트래픽 발생 중지 (Ctrl+C)")
