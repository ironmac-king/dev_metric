"""
LLM 引擎

使用 LLM 进行语义解析，最后兜底
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

import json
from typing import Optional, Dict, Any

from ai.config.logging_config import get_logger
from ai.config.runtime import get_go_api_base
from .base import BaseEngine
from ..api import ParseResult

logger = get_logger("semantic_layer.llm_engine")


class LLMEngine(BaseEngine):
    """
    LLM 引擎

    使用 LLM 进行语义解析，作为最后兜底方案
    当本地模型、语义快照、规则引擎都无法处理时调用
    """

    def __init__(self):
        super().__init__("llm_engine")
        self._go_api_base = get_go_api_base()

    def parse(self, query: str, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        用 LLM 解析查询

        Args:
            query: 用户问题
            context: 上下文

        Returns:
            ParseResult
        """
        try:
            # 调用 Go 后端的意图识别接口
            import httpx
            import asyncio

            # 同步调用（简化处理）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._call_llm(query, context))
            finally:
                loop.close()

            if result:
                return result
            else:
                return ParseResult(
                    intent="unknown",
                    confidence=0.0,
                    parse_method="llm_failed",
                    error="LLM 调用失败"
                )

        except Exception as e:
            logger.error(f"[LLMEngine] parse error: {e}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="llm_error",
                error=str(e)
            )

    async def _call_llm(self, query: str, context: Optional[Dict[str, Any]]) -> Optional[ParseResult]:
        """调用 LLM"""
        try:
            import httpx

            url = f"{self._go_api_base}/api/v1/semantic/llm-parse"

            payload = {
                "question": query,
                "context": context or {},
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        result_data = data.get("data", {})
                        return ParseResult(
                            intent=result_data.get("intent", "unknown"),
                            confidence=result_data.get("confidence", 0.0),
                            metric_name=result_data.get("metric_name"),
                            metric_code=result_data.get("metric_code"),
                            dimensions=result_data.get("dimensions", []),
                            time_expr=result_data.get("time_expr"),
                            comparison_types=result_data.get("comparison_types", []),
                            parse_method="llm",
                            raw_result=result_data,
                        )

            return None

        except Exception as e:
            logger.error(f"[LLMEngine] _call_llm error: {e}")
            return None
