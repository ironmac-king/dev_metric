"""
RecommendationEngine - 引导式提问推荐引擎
"规则骨架 + LLM 润色"混合架构

1. 状态捕获：解析当前查询上下文
2. 规则过滤：根据 common_dimensions 筛选可用维度
3. 意图模板化：生成结构化指令（下钻/排行/趋势/对比）
4. LLM 润色：将结构化指令转化为口语化的追问文本
"""
import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .metric_client import get_metric_client
from .config_loader import get_config_loader

logger = logging.getLogger("ai.llm_v1.recommendation_engine")


@dataclass
class RecommendationIntent:
    """结构化推荐意图"""
    intent_type: str   # drill_down | ranking | trend | compare | percentage
    dimension: str    # 维度中文名（仅 drill_down 类型使用）
    metric: str       # 指标名称
    time_range: str   # 时间范围描述
    instruction: str  # 结构化指令（给 LLM 润色用）


# LLM 润色 Prompt
RECOMMENDATION_PROMPT = """你是一个专业的数据分析助手，擅长生成有吸引力的追问建议。

用户刚刚查询了数据，你的工作是将以下结构化指令转化为简短、口语化、有吸引力的追问按钮文本。

## 规则
1. 每个建议不超过20个字
2. 要像朋友说话一样自然，不要生硬
3. 使用"👉"或"💡"等 emoji 开头增加吸引力
4. 突出数据的价值，让用户想点击

## 结构化指令列表
{instructions}

## 输出要求
直接输出 JSON 数组格式的建议文本列表，每个元素是一个字符串。不要解释。

输出示例：
["👉 看看各地区的销售额占比", "💡 查看销量前5的商品", "📈 销售额的月度趋势如何"]
"""


class RecommendationEngine:
    """
    引导式提问推荐引擎

    采用"规则骨架 + LLM 润色"的混合架构：
    1. 规则过滤：根据元数据生成结构化意图
    2. LLM 润色：将结构化指令转化为口语化的自然语言
    """

    def __init__(self):
        self._metric_client = None
        self._config_loader = None

    def _get_metric_client(self):
        """获取指标客户端"""
        if self._metric_client is None:
            self._metric_client = get_metric_client()
        return self._metric_client

    def _get_config_loader(self):
        """获取配置加载器"""
        if self._config_loader is None:
            self._config_loader = get_config_loader()
        return self._config_loader

    def _extract_current_dimensions(self, slots: Dict[str, Any]) -> List[str]:
        """提取当前已用的维度列表"""
        dimensions_val = slots.get("dimensions", {})
        if isinstance(dimensions_val, list):
            return dimensions_val
        elif isinstance(dimensions_val, dict):
            return list(dimensions_val.keys())
        return []

    def _get_available_dimensions(self, metric: str) -> List[str]:
        """从指标元数据获取可用维度"""
        metric_client = self._get_metric_client()

        # 尝试通过指标名获取详情
        metric_info = metric_client.get_metric_by_name(metric)

        if metric_info and metric_info.get("common_dimensions"):
            dims = metric_info["common_dimensions"]
            if isinstance(dims, str):
                return [d.strip() for d in dims.split(",") if d.strip()]
            elif isinstance(dims, list):
                return dims

        # 默认维度列表（兜底）
        return ["平台", "店铺", "一级品类", "二级品类", "三级品类"]

    def generate_intents(
        self,
        slots: Dict[str, Any],
        ex_output,
    ) -> List[RecommendationIntent]:
        """
        生成结构化意图列表

        Args:
            slots: 槽位信息
            ex_output: 执行节点输出（包含 row_count 等）

        Returns:
            结构化意图列表
        """
        intents = []

        metric = slots.get("metric", "")
        current_dims = self._extract_current_dimensions(slots)
        time_range = slots.get("time_range", {}).get("original", "当前")

        # 如果没有指标，无法生成建议
        if not metric:
            return intents

        # 1. 获取指标可用维度
        available_dims = self._get_available_dimensions(metric)

        # 2. 过滤未使用的维度
        unused_dims = [d for d in available_dims if d not in current_dims]

        # 3. 生成下钻意图（最多3个）
        for dim in unused_dims[:3]:
            intents.append(RecommendationIntent(
                intent_type="drill_down",
                dimension=dim,
                metric=metric,
                time_range=time_range,
                instruction=f"查询{time_range}，{metric}按{dim}分布的占比"
            ))

        # 4. 基于数据特征生成排行意图
        row_count = getattr(ex_output, 'row_count', 0) or 0
        if row_count > 5:
            intents.append(RecommendationIntent(
                intent_type="ranking",
                dimension="",
                metric=metric,
                time_range=time_range,
                instruction=f"查询{time_range}，{metric}排名前5的明细"
            ))

        # 5. 生成趋势和对比意图
        intents.append(RecommendationIntent(
            intent_type="trend",
            dimension="",
            metric=metric,
            time_range=time_range,
            instruction=f"查询{time_range}，{metric}的变化趋势"
        ))

        intents.append(RecommendationIntent(
            intent_type="compare",
            dimension="",
            metric=metric,
            time_range=time_range,
            instruction=f"对比{metric}的同比环比变化"
        ))

        return intents

    async def polish_with_llm(
        self,
        intents: List[RecommendationIntent],
    ) -> List[str]:
        """
        使用 LLM 润色结构化意图，生成口语化的建议文本

        Args:
            intents: 结构化意图列表

        Returns:
            口语化的建议文本列表
        """
        if not intents:
            logger.info("[RecommendationEngine] intents 为空，跳过 LLM 润色")
            return []

        # 构建指令文本
        instructions = "\n".join([
            f"- {i+1}. {intent.instruction}"
            for i, intent in enumerate(intents)
        ])
        logger.info(f"[RecommendationEngine] 构建指令: {instructions[:200]}")

        # 从配置获取 Prompt，没有则用默认值
        config_loader = self._get_config_loader()
        prompt_template = config_loader.get_prompt_template("recommendation_suggestions")
        if prompt_template and prompt_template.content:
            prompt = prompt_template.content.format(instructions=instructions)
        else:
            prompt = RECOMMENDATION_PROMPT.format(instructions=instructions)
        logger.info(f"[RecommendationEngine] 使用 Prompt 长度: {len(prompt)}")

        try:
            from .llm_client import get_llm_client
            llm_client = get_llm_client()
            logger.info("[RecommendationEngine] 开始调用 LLM...")
            result = await llm_client.call(prompt, temperature=0.7, max_tokens=500)
            logger.info(f"[RecommendationEngine] LLM 返回原始结果: {result[:500] if result else 'None'}")

            # 解析 JSON 数组
            suggestions = json.loads(result)
            if isinstance(suggestions, list):
                logger.info(f"[RecommendationEngine] LLM 润色成功，返回 {len(suggestions)} 条建议")
                return [str(s) for s in suggestions[:4]]

            logger.warning(f"[RecommendationEngine] LLM 返回格式错误: {result[:200]}")
            return []

        except json.JSONDecodeError as e:
            logger.warning(f"[RecommendationEngine] JSON 解析失败: {e}")
            return []
        except Exception as e:
            logger.error(f"[RecommendationEngine] LLM 调用异常: {e}", exc_info=True)
            return []

    def generate_suggestions_template(
        self,
        slots: Dict[str, Any],
        ex_output,
    ) -> List[str]:
        """
        模板生成建议（LLM 失败时的降级方案）

        Args:
            slots: 槽位信息
            ex_output: 执行节点输出

        Returns:
            建议文本列表
        """
        suggestions = []

        metric = slots.get("metric", "")
        current_dims = self._extract_current_dimensions(slots)
        time_range = slots.get("time_range", {}).get("original", "")

        # 基于当前维度生成下钻建议
        all_dimensions = ["平台", "店铺", "一级品类", "二级品类", "三级品类"]
        available_dims = [d for d in all_dimensions if d not in current_dims]

        if available_dims and metric:
            suggestions.append(f"👉 分{available_dims[0]}看{metric}")

        # 基于数据特征生成建议
        row_count = getattr(ex_output, 'row_count', 0) or 0
        if row_count > 5:
            suggestions.append(f"💡 查看{metric}排名")

        if metric:
            suggestions.append(f"📈 查看{metric}的趋势")
            suggestions.append(f"🔄 对比{metric}的同比/环比")

        return suggestions[:3]


# 全局实例
_recommendation_engine: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    """获取推荐引擎单例"""
    global _recommendation_engine
    if _recommendation_engine is None:
        _recommendation_engine = RecommendationEngine()
    return _recommendation_engine
