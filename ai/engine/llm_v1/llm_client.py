"""
LLMClient - LLM.V1 的 LLM 调用封装
基于现有 ai/engine/llm.py 的调用模式，但完全重写 Prompt 逻辑
"""
import json
import re
import logging
from typing import Dict, Any, Optional

from ai.engine.llm import get_llm_engine

logger = logging.getLogger("ai.llm_v1.llm_client")


class LLMClient:
    """
    LLM 调用封装

    职责：
    1. 调用腾讯云 DeepSeek LLM
    2. JSON 响应解析
    3. 错误处理和重试
    """

    def __init__(self, use_case: str = "llm_v1"):
        self._llm_engine = get_llm_engine()
        self._use_case = use_case

    async def call(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """
        调用 LLM

        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            LLM 返回的文本
        """
        try:
            result = await self._llm_engine.generate(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return result
        except Exception as e:
            logger.error(f"[LLMClient] LLM 调用失败: {e}")
            raise

    async def call_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """
        调用 LLM 并解析 JSON 响应

        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            解析后的 JSON 对象
        """
        response_text = await self.call(prompt, temperature, max_tokens)
        return self.parse_json_response(response_text)

    def parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        从 LLM 响应中提取 JSON

        Args:
            response_text: LLM 返回的文本

        Returns:
            解析后的 JSON 对象
        """
        if not response_text:
            return {}

        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试从 Markdown 代码块中提取
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试从文本中提取 JSON 对象
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"[LLMClient] 无法解析 JSON 响应: {response_text[:200]}...")
        return {}

    def parse_json_array_response(self, response_text: str) -> list:
        """
        从 LLM 响应中提取 JSON 数组

        Args:
            response_text: LLM 返回的文本

        Returns:
            解析后的 JSON 数组
        """
        if not response_text:
            return []

        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试从 Markdown 代码块中提取
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试从文本中提取 JSON 数组
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"[LLMClient] 无法解析 JSON 数组响应: {response_text[:200]}...")
        return []


# 全局实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
