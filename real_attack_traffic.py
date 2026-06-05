import requests
import time

TARGET_URL = "http://127.0.0.1"

print("========================================")
print(" 🚨 실환경 웹 공격 페이로드 주입 스크립트 🚨")
print("========================================")
input("엔터를 누르면 아파치 서버로 즉시 3단계 연속 공격 통신을 발생시킵니다...")

print("[*] 1단계: 악성 SQL Injection 페이로드 주입 중...")
for _ in range(10):
    try:
        requests.get(TARGET_URL + "/admin.php?id=1' OR '1'='1", timeout=1)
    except Exception:
        pass
    time.sleep(0.1)

print("[*] 2단계: OOV(Out of Vocabulary) 페이로드 주입 중...")
for _ in range(5):
    try:
        requests.get(TARGET_URL + "/%00%00%00/etc/passwd' OR 1=1 --", timeout=1)
    except Exception:
        pass
    time.sleep(0.1)

print("[*] 3단계: 무차별 대입(Brute-Force) 공격 트래픽 발생 중...")
for _ in range(15):
    try:
        requests.post(TARGET_URL + "/login_failed.html", timeout=1)
    except Exception:
        pass
    time.sleep(0.1)

print("\n[+] 모든 공격 발송 완료! 딥러닝 PC 터미널에서 🚨 탐지 알람을 확인하세요.")
