"""意图→片段映射配置"""
from typing import Dict, List, Type
from .fragments.base import SQLFragment
from .fragments.measure import MeasureFragment
from .fragments.where import WhereFragment
from .fragments.group_by import GroupByFragment
from .fragments.window import WindowFragment


# 意图→片段配置
INTENT_FRAGMENTS: Dict[str, List[Type[SQLFragment]]] = {
    "query_value": [MeasureFragment],
    "query_trend": [MeasureFragment, WhereFragment, GroupByFragment],
    "query_ranking": [MeasureFragment, WhereFragment, GroupByFragment],
    "query_comparison": [MeasureFragment, WhereFragment],
}


def get_composer_for_intent(intent: str):
    """根据意图获取配置好的 Composer"""
    from .composer import FragmentComposer

    composer = FragmentComposer()
    fragment_types = INTENT_FRAGMENTS.get(intent, [MeasureFragment])

    for ft in fragment_types:
        composer.add(ft())

    # 特殊处理需要参数的片段（在主片段之后追加）
    if intent == "query_trend":
        composer.add(WindowFragment("LAG"))
    elif intent == "query_ranking":
        composer.add(WindowFragment("RANK"))
    elif intent == "query_comparison":
        composer.add(WindowFragment("YoY"))

    return composer
