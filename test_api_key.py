"""
test_api_key.py - 測試 OpenAI API Key 是否正常
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

# 載入 .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY", "")

print(f"讀取到的 Key: {api_key[:15]}...{api_key[-4:]}")
print(f"Key 長度: {len(api_key)}")
print()

# 測試呼叫
try:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=5,
    )
    print("[OK] API Key 正常!")
    print(f"回應: {response.choices[0].message.content}")
except Exception as e:
    print(f"[FAIL] API Key 有問題!")
    print(f"錯誤: {e}")
