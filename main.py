import os
import time
import openai
import praw
from datetime import datetime

print("👋 Script booting...")

try:
    # 输出环境变量加载状态
    print("✅ OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY")[:6] if os.getenv("OPENAI_API_KEY") else "❌ Not set")
    print("✅ CLIENT_ID:", os.getenv("CLIENT_ID"))
    print("✅ CLIENT_SECRET:", "Loaded" if os.getenv("CLIENT_SECRET") else "❌ Not set")
    print("✅ REFRESH_TOKEN:", "Loaded" if os.getenv("REFRESH_TOKEN") else "❌ Not set")
    print("✅ USER_AGENT:", os.getenv("USER_AGENT"))

    openai.api_key = os.getenv("OPENAI_API_KEY")
    reddit = praw.Reddit(
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        refresh_token=os.getenv("REFRESH_TOKEN"),
        user_agent=os.getenv("USER_AGENT"),
    )

    print("🚀 Patrick Debug Bot running main loop...")

    while True:
        print(f"🕓 {datetime.utcnow().isoformat()} - Still running...")
        time.sleep(60)

except Exception as e:
    print("🔥 Uncaught error:", e)
