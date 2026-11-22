from flask import Flask, request, jsonify
import torch
import torch.nn.functional as F
import numpy as np
import json
import os
import time
import torch.nn as nn
from collections import deque

BASE_DIR = os.environ.get('MODEL_DIR', '.')
ID_MAP_PATH = os.path.join(BASE_DIR, 'id_map.json')
MODEL_PATH = os.path.join(BASE_DIR, 'best_lstm_model.pth')
ATTACK_LOG_FILE = os.environ.get("ATTACK_LOG_FILE", os.path.join(BASE_DIR, "attack_detected.log"))

WINDOW_SIZE      = 6     
POPULATION_SIZE  = 3000
WARMUP_COUNT     = 100   
IQR_FENCE_FACTOR = 3.0   

class LSTMLM(nn.Module):
    def __init__(self, vocab_size, embed_size=64, hidden_size=128):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_size)
        self.lstm  = nn.LSTM(embed_size, hidden_size, batch_first=True)
        self.fc    = nn.Linear(hidden_size, vocab_size)

    def forward(self, x):
        x = self.embed(x)
        out, _ = self.lstm(x)
        return self.fc(out)

app = Flask(__name__)

try:
    with open(ID_MAP_PATH, 'r', encoding='utf-8') as f:
        id_map = json.load(f)
except FileNotFoundError:
    print(f"[!] 에러: 단어장 파일이 없습니다 -> {ID_MAP_PATH}")
    exit(1)

device     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
vocab_size = len(id_map)
model      = LSTMLM(vocab_size=vocab_size).to(device)

if os.path.exists(MODEL_PATH):
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    print(f"[*] 최적 학습 가중치 로드 완료")
else:
    print(f"[!] 초기 무작위 가중치 기동")
model.eval()

population_ppl   = deque(maxlen=POPULATION_SIZE)
warmup_accepted  = 0      
warmup_rejected  = 0      
warmup_done      = False

LAST_ALERT_TIME  = 0.0
ALERT_COOLDOWN   = 5.0

print(f"[*] 실시간 AI 탐지 서버 가동 완료 (Port: 5000)")

def is_warmup_outlier(ppl: float) -> bool:
    if len(population_ppl) < 10:
        return False
    arr = np.array(population_ppl)
    q1, q3 = np.percentile(arr, 25), np.percentile(arr, 75)
    upper_fence = q3 + IQR_FENCE_FACTOR * (q3 - q1)
    return ppl > upper_fence

@app.route('/predict', methods=['POST'])
def predict():
    global LAST_ALERT_TIME, warmup_accepted, warmup_rejected, warmup_done

    try:
        logs = request.json.get('window', [])
        # 🌟 스트리머가 보낸 원문을 받음 (없으면 기존 마스킹 로그 사용)
        raw_logs = request.json.get('raw_window', logs) 

        if len(logs) < WINDOW_SIZE:
            return jsonify({'status': 'error', 'msg': '데이터 부족'}), 400

        numeric_logs = [id_map.get(log, 0) for log in logs]
        X_input  = torch.LongTensor([numeric_logs[:WINDOW_SIZE - 1]]).to(device)
        y_target = torch.LongTensor([numeric_logs[WINDOW_SIZE - 1]]).to(device)

        with torch.no_grad():
            output     = model(X_input)
            prediction = output[:, -1, :]
            loss       = F.cross_entropy(prediction, y_target, reduction='none')
            ppl        = torch.exp(loss).item()

        if not warmup_done:
            if is_warmup_outlier(ppl):
                warmup_rejected += 1
            else:
                population_ppl.append(ppl)
                warmup_accepted += 1
                if warmup_accepted >= WARMUP_COUNT:
                    warmup_done = True
                    print(f"\n✅ 워밍업 완료! 실제 탐지를 시작합니다.")
            
            return jsonify({'status': 'warmup', 'ppl': ppl, 'is_anomaly': False, 
                            'warmup_remaining': max(0, WARMUP_COUNT - warmup_accepted)})

        current_mean      = np.mean(population_ppl)
        current_std       = np.std(population_ppl)
        current_threshold = current_mean + (3 * current_std)
        is_anomaly        = ppl > current_threshold
        current_time      = time.time()

        if is_anomaly:
            if current_time - LAST_ALERT_TIME > ALERT_COOLDOWN:
                # 🌟 핵심 수정: Gemma가 분석할 수 있도록 raw_logs(순수 원문)를 기록합니다.
                with open(ATTACK_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(raw_logs) + "\n\n")

                print("\n" + "=" * 52)
                print(f"🚨 [신규 공격 세션 탐지!] PPL: {ppl:.2f} (임계치: {current_threshold:.2f} 초과)")
                print(f"   -> [원문 로그 추출]:")
                for i, log_line in enumerate(raw_logs):
                    print(f"      [{i+1}] {log_line}")
                print("=" * 52 + "\n")
                LAST_ALERT_TIME = current_time
            else:
                print(f"   -> (연속 공격 수신 중...) PPL: {ppl:.2f}")
        else:
            population_ppl.append(ppl)
            print(f"✅ [정상 로그] PPL: {ppl:.2f} | 📊 임계치: {current_threshold:.2f}")

        return jsonify({'status': 'success', 'ppl': ppl, 'is_anomaly': bool(is_anomaly)})

    except Exception as e:
        print(f"[!] 서버 연산 에러: {str(e)}")
        return jsonify({'status': 'error', 'msg': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)