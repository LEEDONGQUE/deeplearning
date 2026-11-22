# LSTM을 활용한 비지도 학습 기반 서버 로그 이상 탐지

한국외국어대학교 정보통신공학과 졸업논문 (2026년 8월, 지도교수 전홍배)
2인 팀: 이동규, 강태훈

정상 웹 로그의 흐름만 학습한 LSTM이 실시간으로 들어오는 Apache 로그에서 이상한 흐름을 찾아내고,
이상으로 판정되면 원문 로그를 로컬 sLLM(Gemma)에 넘겨 공격 유형과 대응 방안을 바로 알려 주는 시스템입니다.
공격 레이블 없이 정상 로그만으로 학습하기 때문에, 학습 때 보지 못한 신종 공격도 잡아낼 수 있는지를 함께 실험했습니다.

## 결과

하이퍼파라미터 조합을 그리드 서치로 찾은 최종 설정입니다.

| 항목 | 값 |
|---|---|
| 학습 데이터 | 13,000개 |
| 슬라이딩 윈도우 | 6 (앞 5줄로 6번째 로그 예측) |
| 학습률 | 0.0001 |
| Epochs | 5 |
| 검증 데이터 비율 | 20% |
| 결과 | 오탐률(FPR) 3.24%, 정탐률(TPR) 100% |

기존 머신러닝 모델과의 비교 실험 결과입니다. A는 알려진 공격, B는 공격처럼 보이는 정상 노이즈, C는 학습에서 완전히 뺀 신종 공격(PortScan)입니다.

| 모델 | A 정탐률 | A 오탐률 | B 오탐률 | C 탐지율 |
|---|---|---|---|---|
| Isolation Forest | 1.000 | 0.055 | 0.118 | 0.056 |
| One-Class SVM | 1.000 | 0.055 | 0.131 | 0.097 |
| Random Forest (지도학습) | 1.000 | 0.000 | 0.000 | 0.000 |
| LSTM (제안) | 1.000 | 0.014 | 0.044 | 0.375 |

LSTM은 노이즈 환경 오탐률이 4.4%로 가장 낮았고, 학습에 없던 신종 공격을 의미 있게 잡아낸 유일한 모델이었습니다.

실시간 연동 시연에서는 정상 트래픽에서 임계치가 안정적으로 자리 잡았고, SQL 인젝션과 무차별 대입 공격을 주입하자 바로 탐지한 뒤 Gemma가 공격 유형과 대응 방안을 터미널에 출력했습니다.

## 시스템 구조

```
[Linux VM, Apache 웹 서버]
  access.log 실시간 감시 (log_streamer.py)
  로그 한 줄마다 가변값 마스킹, 최근 6줄을 모아서
        |
        |  HTTP POST /predict  { 마스킹된 6줄, 원문 6줄 }
        v
[GPU 서버, 탐지 서버 (server/realtime_server.py)]
  템플릿 번호로 바꿔 LSTM에 넣고 PPL 계산
  PPL이 동적 임계치를 넘으면 원문 6줄을 attack_detected.log 에 기록
        |
        v
[GPU 서버, Gemma 분석기 (gemma/gemma_responder.py)]
  attack_detected.log 를 감시하다가 새 내용이 오면
  공격 유형과 대응 방안을 생성해 터미널에 출력
```

## 동작 방식

1. 전처리: Drain 알고리즘으로 로그를 템플릿으로 정형화하고, IP 주소, 날짜, URL 경로, 응답 크기, 숫자 같은 가변값을 가립니다. 같은 모양의 로그는 같은 템플릿 번호를 받습니다.
2. 모델: Embedding(64) 다음 LSTM(hidden 128) 구조의 언어 모델입니다. 앞 5줄의 템플릿 번호로 6번째 로그의 확률을 예측하고, 실제 로그와의 교차 엔트로피로 퍼플렉서티(PPL)를 계산합니다. 학습한 정상 흐름에서 벗어날수록 PPL이 크게 오릅니다.
3. 동적 임계치: 처음 정상 로그 100개로 워밍업하면서 IQR 기준으로 튀는 값은 뺍니다. 그 뒤에는 최근 정상 PPL 3,000개의 평균 + 3 표준편차를 임계치로 씁니다. 같은 공격이 이어질 때 알림이 쏟아지지 않도록 5초 간격을 둡니다.
4. 대응책 생성: 마스킹 전 원문(IP와 공격 페이로드 포함)을 Gemma(gemma-2b-it, 4비트 양자화)에 넣어 공격 유형과 대응 방안을 짧게 생성합니다. GPU 메모리를 넘지 않도록 최근 1,500자만 넣습니다.

## 데이터셋

- 학습과 Gemma 연동용: 공개 웹 서버 로그 데이터셋과 Apache 서버 실시간 트래픽을 합친 정상 로그 20,000줄, SQL 인젝션과 무차별 대입 같은 악성 로그
- 독립 평가용: 정상 로그 2,000줄, 악성 로그 200줄
- 벤치마크용: 정상 20,000줄, SQL 인젝션 24,184줄(sqlmap), 신종 공격 PortScan 6,000줄(모든 학습에서 제외), 공격처럼 보이는 정상 노이즈 3,000줄

combined_20k_logs.txt 에 보이는 외부 IP는 공개 데이터셋에 원래 들어 있는 값이고, access.log 는 테스트용으로 만든 로그라 모두 127.0.0.1 입니다.

## 역할

이동규
- 공개 데이터셋과 Apache 로그를 합친 20,000줄 데이터셋 구축, 독립 평가 데이터셋 설계
- Drain 파싱과 가변값 마스킹, 실시간 슬라이딩 윈도우 전처리 파이프라인
- 하이퍼파라미터 5개(학습 데이터 크기, 윈도우 크기, 학습률, Epochs, 검증 데이터 크기) 그리드 서치
- VM과 GPU 서버 사이 실시간 HTTP 연동, 이상 로그 원문을 Gemma로 넘기는 구조
- Gemma 기반 공격 유형 판별과 대응 방안 출력

강태훈
- VM Apache 서버에서 정상 트래픽(세션 패턴 7가지, 경로 21종)과 공격 로그 생성
- Isolation Forest, One-Class SVM, Random Forest 벤치마크 구현과 비교 실험

## 파일 구성

| 파일 | 내용 |
|---|---|
| log_streamer.py | VM에서 실행. access.log 감시, 마스킹, 탐지 서버로 전송 |
| server/realtime_server.py | GPU 서버에서 실행. LSTM 추론, PPL 계산, 동적 임계치 판정 |
| gemma/gemma_responder.py | GPU 서버에서 실행. 이상 로그 원문을 Gemma로 분석 |
| lstm_model.py | LSTM 언어 모델과 PPL 계산 함수 |
| lstm_model2.py, lstm_model3.py | 시점별 PPL 분석, 윈도우 크기 비교 실험 |
| train_full.py | 학습 스크립트 (실험 중 버전이라 학습률과 Epochs가 최종 설정과 다릅니다) |
| real_normal_traffic.py, real_attack_traffic.py | 시연용 정상, 공격 트래픽 발생기 |
| attack/ | 공격 로그와 Drain 처리 결과 |
| combined_20k_logs*.txt, id_map.json, *.npy | 정상 로그 원본, Drain 처리 결과, 템플릿 번호 사전, 학습용 배열 |

## 실행 방법

필요한 것: Python 3, PyTorch, Flask, requests, transformers, bitsandbytes, CUDA GPU (Gemma용)

```bash
# GPU 서버: 탐지 서버 (id_map.json 과 가중치 파일이 있는 폴더를 MODEL_DIR 로)
MODEL_DIR=. python server/realtime_server.py

# GPU 서버: Gemma 분석기 (탐지 서버와 같은 attack_detected.log 를 보도록)
ATTACK_LOG_FILE=./attack_detected.log python gemma/gemma_responder.py

# VM: 로그 송신기
DL_SERVER_URL=http://<탐지서버_주소>:5000/predict python log_streamer.py
```

탐지 서버는 MODEL_DIR 안의 best_lstm_model.pth 를 불러옵니다. 최종 가중치는 이 저장소에 없고, lstm_final.pth 는 실험 중 가중치입니다.
