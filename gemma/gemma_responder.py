import os
import time
import gc
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

# [메모리 단편화 방지]
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

MODEL_ID = os.environ.get("GEMMA_MODEL", "google/gemma-2b-it")
LOG_PATH = os.environ.get("ATTACK_LOG_FILE", "attack_detected.log")

print("[*] Gemma AI 보안 관제사 로딩 중... (글자수 강제 제한 Failsafe 모드)")

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, 
    quantization_config=bnb_config, 
    attn_implementation="eager", 
    device_map="cuda"
)
model.eval()
print("[+] 로딩 완료! 7.6GB VRAM 내에서 방어벽 가동 중.")

def analyze_with_gemma(attack_logs):
    # 🌟 [최후의 방어벽] 파일이 아무리 거대해도, 무조건 뒷부분(가장 최신 로그) 1,500자만 자릅니다.
    # 슬라이딩 윈도우 6줄은 보통 800~1000자이므로, 문맥은 100% 보존되면서 24GB 폭발은 원천 차단됩니다.
    safe_logs = attack_logs[-1500:] if len(attack_logs) > 1500 else attack_logs

    prompt = f"당신은 AI 보안 관제 전문가입니다. 다음 웹 로그를 분석하여 공격 유형과 대응 방안을 간결하게 작성하세요.\n\n[로그]\n{safe_logs}\n\n[출력]\n1. 공격 유형:\n2. 대응 방안:"
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    
    gc.collect()
    torch.cuda.empty_cache()
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs, 
            max_new_tokens=150, 
            do_sample=False,
            use_cache=True
        )
        
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    del inputs, outputs
    gc.collect()
    torch.cuda.empty_cache()
    
    return generated_text.split("[출력]")[-1].strip() if "[출력]" in generated_text else generated_text.strip()

while True:
    if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 0:
        time.sleep(0.2) 
        
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            if content:
                print("\n" + "🔥" * 30)
                print("🚨 [Gemma 긴급 AI 보안 분석 보고서 발행] 🚨")
                print("🔥" * 30)
                print(analyze_with_gemma(content))
                print("=" * 60 + "\n")
                
            open(LOG_PATH, "w", encoding="utf-8").close()
            
        except Exception as e:
            pass # 에러 메시지 출력 생략 (조용히 재시도)
            
    time.sleep(1)