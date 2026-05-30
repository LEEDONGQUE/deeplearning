import time
import subprocess
import requests
import re
from collections import deque

# 🚨 < > 기호 지우고 딥러닝 PC 실제 IP 적기!
TARGET_DL_PC_URL = "http://220.67.124.129:5000/predict"
LOG_FILE = "/var/log/apache2/access.log"

window_buffer = deque(maxlen=6)

def mask_log(raw_log):
    # 1. IP 주소 마스킹
    log = re.sub(r'^\S+', '<<*>>', raw_log)

    # 2. 날짜 마스킹 [27/May/2026:18:30:01 +0900] -> <*> +<<*>>]
    log = re.sub(r'\[.*? \+', '<*> +', log)

    # 3. URL 경로 마스킹 (전체 HTTP 메서드 대응)
    log = re.sub(r'\"(GET|POST|HEAD|PUT|DELETE) \S+ HTTP', r'"\1 <*> HTTP', log)

    # 4. 응답 크기와 Referer 마스킹
    #    수정: HTTP 버전 \d\.\d+ 로 확장, Referer \"[^\"]*\" 로 빈값 포함
    log = re.sub(r'(HTTP/\d\.\d+\" \d+) \d+ \"[^\"]*\"', r'\1 <*> <*>', log)

    # 5. 남은 독립 숫자 마스킹
    log = re.sub(r'\b\d+\b', '<<*>>', log)

    return log.strip()

print("========================================")
print(f"[*] 실시간 로그 정형화 및 송신기 가동 시작")
print(f"[*] 목적지 서버: {TARGET_DL_PC_URL}")
print("========================================")

process = subprocess.Popen(['tail', '-F', LOG_FILE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

while True:
    line = process.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue

    raw_log = line.decode('utf-8')
    masked_log = mask_log(raw_log)
    window_buffer.append(masked_log)

    if len(window_buffer) == 6:
        payload = {'window': list(window_buffer)}
        try:
            res = requests.post(TARGET_DL_PC_URL, json=payload, timeout=2).json()

            status_code = res.get('status')
            ppl = res.get('ppl', 0)
            threshold = res.get('current_threshold', 0)

            if status_code == 'warmup':
                remaining = res.get('warmup_remaining', 0)
                print(f"⏳ [워밍업 중 - 잔여 {remaining:3d}개] PPL: {ppl:.2f} (임계치 수렴 중: {threshold:.2f})")
            elif res.get('is_anomaly'):
                print(f"🚨 [공격 탐지] PPL: {ppl:.2f} (임계치: {threshold:.2f})")
            else:
                print(f"✅ [정상 통과] PPL: {ppl:.2f} (임계치: {threshold:.2f})")

        except Exception as e:
            print(f"[!] 딥러닝 PC 통신 실패: {e}")
