"""
本地模型引擎

封装 LocalJointIntentModel，提供本地模型解析能力
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from typing import Optional, Dict, Any, List
from dataclasses import asdict

from ai.config.logging_config import get_logger
from ai.engine.llm_v2.nodes.local_intent_model import get_local_intent_model

from .base import BaseEngine
from ..api import ParseResult, Entity

logger = get_logger("semantic_layer.local_model_engine")


class LocalModelEngine(BaseEngine):
    """
    本地模型引擎

    封装 Joint BERT 本地模型，提供：
    - 意图识别
    - 实体提取 (NER)
    """

    def __init__(self):
        super().__init__("local_model_engine")
        self._model = None

    def _init(self):
        """初始化"""
        try:
            self._model = get_local_intent_model()
            logger.info("[LocalModelEngine] 初始化成功")
        except Exception as e:
            logger.warning(f"[LocalModelEngine] 初始化失败: {e}")
            self._model = None

    def parse(self, query: str, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        用本地模型解析查询

        Args:
            query: 用户问题
            context: 上下文（可选）

        Returns:
            ParseResult
        """
        self._ensure_init()

        if not self._model:
            logger.warning(f"[LocalModelEngine] 模型未加载，跳过查询: {query[:30]}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="local_model_unavailable",
                error="本地模型未加载"
            )

        try:
            result = self._model.predict(query)
            logger.info(f"[LocalModelEngine] predict完成: query='{query[:30]}', "
                       f"intent={result.get('intent')}, confidence={result.get('confidence', 0):.4f}, "
                       f"entities={[f\"{e.get('type')}:{e.get('text')}\" for e in result.get('entities', [])]}")

            # 提取实体
            entities = result.get('entities', [])

            # 提取指标
            metric_name = None
            for ent in entities:
                if ent.get('type') == 'METRIC':
                    metric_name = ent.get('text')
                    break

            # 提取时间
            time_expr = None
            for ent in entities:
                if ent.get('type') == 'TIME':
                    time_expr = ent.get('text')
                    break

            # 提取维度
            dimensions = []
            for ent in entities:
                if ent.get('type') == 'DIM':
                    dim_text = ent.get('text', '')
                    if dim_text:
                        dimensions.append({"type": dim_text, "value": None})
                elif ent.get('type') == 'DIM_VALUE':
                    dim_text = ent.get('text', '')
                    if dim_text:
                        dimensions.append({"type": "", "value": dim_text})

            # 检测对比类型
            comparison_types = self._detect_comparison(query)

            # 判断是否下钻
            drilldown_type = None
            if query.startswith("__DRILLDOWN__:"):
                drilldown_type = query.replace("__DRILLDOWN__:", "").replace("__", "").strip()

            return ParseResult(
                intent=result.get('intent', 'unknown'),
                confidence=result.get('confidence', 0.0),
                entities=[Entity(**e) if isinstance(e, dict) else e for e in entities],
                metric_name=metric_name,
                time_expr=time_expr,
                dimensions=dimensions,
                comparison_types=comparison_types,
                parse_method="local_model",
                drilldown_type=drilldown_type,
                raw_result=result,
            )

        except Exception as e:
            logger.error(f"[LocalModelEngine] parse error: {e}")
            return ParseResult(
                intent="unknown",
                confidence=0.0,
                parse_method="error",
                error=str(e)
            )

    def _detect_comparison(self, query: str) -> List[str]:
        """检测对比类型"""
        comparison_types = []
        query_lower = query.lower()

        if "同比" in query or "yoy" in query_lower:
            comparison_types.append("同比")
        if "环比" in query or "mom" in query_lower:
            comparison_types.append("环比")

        return comparison_types
