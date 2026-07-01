"""
统一 LLM 客户端封装 - 支持 Azure OpenAI 与 OpenAI 兼容接口
- LLM_PROVIDER=azure（默认）时走 Azure OpenAI
- LLM_PROVIDER=openai 时走标准 OpenAI
- 无 Key 时自动回退到 Mock 响应
"""
import os
import time
from typing import Optional

PROVIDER = os.environ.get('LLM_PROVIDER', 'azure').lower().strip()
API_KEY = os.environ.get('OPENAI_API_KEY', '').strip() or os.environ.get('AZURE_OPENAI_API_KEY', '').strip()
AZURE_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT', 'https://tencent-azure-tmo-aidev-resource.services.ai.azure.com').strip()
API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-06-01').strip()
DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o').strip()
MODEL = os.environ.get('LLM_MODEL', DEPLOYMENT).strip()
OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').strip()

_client = None
_client_kind = None  # 'azure' | 'openai' | None

try:
    if API_KEY:
        if PROVIDER == 'azure':
            from openai import AzureOpenAI
            _client = AzureOpenAI(
                api_key=API_KEY,
                api_version=API_VERSION,
                azure_endpoint=AZURE_ENDPOINT,
            )
            _client_kind = 'azure'
        else:
            from openai import OpenAI
            _client = OpenAI(api_key=API_KEY, base_url=OPENAI_BASE_URL)
            _client_kind = 'openai'
except Exception as e:
    print(f'[LLM] 客户端初始化失败，回退 Mock: {e}')
    _client = None


def is_real_llm() -> bool:
    return _client is not None


def chat(system_prompt: str, user_prompt: str, temperature: float = 0.7,
         max_tokens: int = 1500, mock_fn=None) -> dict:
    start = time.time()

    if _client is None:
        content = mock_fn() if mock_fn else '（未配置 API Key，当前 Mock 模式）'
        return {'content': content, 'source': 'mock', 'elapsed': time.time() - start}

    try:
        # Azure 用 deployment 名字当 model，OpenAI 用真实模型名
        model_arg = DEPLOYMENT if _client_kind == 'azure' else MODEL
        resp = _client.chat.completions.create(
            model=model_arg,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        return {'content': content, 'source': 'real', 'elapsed': time.time() - start}
    except Exception as e:
        err = str(e)
        fallback = mock_fn() if mock_fn else ''
        return {
            'content': f'⚠️ AI 调用失败，已回退 Mock。\n错误：{err[:200]}\n\n{fallback}',
            'source': 'mock',
            'elapsed': time.time() - start,
        }
