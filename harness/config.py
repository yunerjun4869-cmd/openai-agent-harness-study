"""配置只从明确的项目 .env 与环境变量读取，不递归寻找用户目录中的密钥。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gpt-6-astra"


def load_config():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    return {"model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL") or None}


def live_client():
    config = load_config()
    if not config["api_key"]:
        raise RuntimeError("未设置 OPENAI_API_KEY。复制 .env.example 为 .env 后填写，或使用 --demo。")
    from openai import OpenAI
    return OpenAI(api_key=config["api_key"], base_url=config["base_url"],
                  timeout=30.0, max_retries=2)
