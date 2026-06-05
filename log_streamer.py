import time
import subprocess
import requests
import re
from collections import deque

# 🚨 <딥러닝_PC_IP_주소> 부분을 실제 딥러닝 PC의 IP로 변경하세요!
TARGET_DL_PC_URL = "http://220.67.124.129:5000/predict"
LOG_FILE = "/var/log/apache2/access.log"

window_buffer = deque(maxlen=6)
raw_window_buffer = deque(maxlen=6) # 🌟 추가: Gemma에게 보낼 원문 버퍼

def mask_log(raw_log):
    # 1. IP 주소 마스킹
    log = re.sub(r'^\S+', '<<*>>', raw_log)
    # 2. 날짜 마스킹
    log = re.sub(r'\[.*? \+', '<*> +', log)
    # 3. URL 경로 마스킹 (전체 HTTP 메서드 대응)
    log = re.sub(r'\"(GET|POST|HEAD|PUT|DELETE) \S+ HTTP', r'"\1 <*> HTTP', log)
    # 4. 응답 크기와 Referer 마스킹
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

    raw_log = line.decode('utf-8').strip() # 🌟 원문 추출
    masked_log = mask_log(raw_log)
    
    window_buffer.append(masked_log)
    raw_window_buffer.append(raw_log) # 🌟 원문 버퍼에 저장

    if len(window_buffer) == 6:
        # 🌟 딥러닝 PC로 두 가지 버퍼를 모두 전송
        payload = {
            'window': list(window_buffer), 
            'raw_window': list(raw_window_buffer)
        }
        
        try:
            res = requests.post(TARGET_DL_PC_URL, json=payload, timeout=2).json()
            status_code = res.get('status')
            ppl = res.get('ppl', 0)
            threshold = res.get('current_threshold', 0)

            if status_code == 'warmup':
                remaining = res.get('warmup_remaining', 0)
                print(f"⏳ [워밍업 중] 현재 PPL: {ppl:.2f} (남은 수집: {remaining}개)")
            else:
                is_anomaly = res.get('is_anomaly')
                status = "🚨 공격 탐지" if is_anomaly else "✅ 정상 통과"
                print(f"[{status}] 현재 측정 PPL: {ppl:.2f} (기준 임계치: {threshold:.2f})")
                
        except Exception as e:
            print(f"[!] 딥러닝 PC 통신 실패: {e}")
