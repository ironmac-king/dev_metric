"""
Relation Miner
Uses LLM to extract metric relationships from business definitions
"""

import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ExtractedRelation:
    """Extracted relation from LLM"""
    source: str  # Source metric name
    target: str  # Target metric name
    relation_type: str  # derives_from, impacts, correlates_with
    description: str = ""


class RelationMiner:
    """Extract metric relationships using LLM"""

    def __init__(self, llm_engine=None):
        """
        Initialize RelationMiner

        Args:
            llm_engine: LLM engine instance (optional, will import if not provided)
        """
        self.llm_engine = llm_engine

    def _get_llm_engine(self):
        """Lazy load LLM engine"""
        if self.llm_engine is None:
            from ai.engine.llm import LLMEngine
            self.llm_engine = LLMEngine()
        return self.llm_engine

    def mine_from_business_definition(self, metric: Dict) -> List[ExtractedRelation]:
        """
        Analyze business definition to extract causal/correlation relationships

        Args:
            metric: Metric dictionary with 'name' and 'business_definition' keys

        Returns:
            List of ExtractedRelation objects
        """
        business_def = metric.get("business_definition", "")
        metric_name = metric.get("name", "")

        if not business_def:
            return []

        llm = self._get_llm_engine()

        prompt = f"""分析以下指标的业务定义，提取指标间的因果/相关关系。

指标名称：{metric_name}
业务定义：{business_def}

请找出：
1. 这个指标依赖于哪些上游指标（derives_from）
2. 这个指标会影响哪些下游指标（impacts）
3. 这个指标与哪些指标相关（correlates_with）

注意：
- derives_from 表示"A由B推导而出"，如：转化率 derives_from 点击量
- impacts 表示"A影响B"，如：广告投放 impacts 曝光量
- correlates_with 表示"A与B相关"，如：转化率 correlates_with 复购率
- 只需要返回与该指标直接相关的上下游指标，不需要返回整条链路

以JSON数组格式返回，格式如下：
[
  {{"source": "上游指标名", "target": "当前指标名", "relation_type": "derives_from", "description": "关系描述"}},
  {{"source": "当前指标名", "target": "下游指标名", "relation_type": "impacts", "description": "关系描述"}},
  {{"source": "当前指标名", "target": "相关指标名", "relation_type": "correlates_with", "description": "关系描述"}}
]

如果该指标没有明显的上下游关系或相关指标，返回空数组 []。"""

        try:
            result = llm.call(prompt)
            return self._parse_relations(result)
        except Exception as e:
            print(f"[RelationMiner] LLM call failed: {e}")
            return []

    def _parse_relations(self, llm_output: str) -> List[ExtractedRelation]:
        """Parse LLM output to extract relations"""
        relations = []

        # Try to extract JSON from the output
        json_match = re.search(r'\[.*\]', llm_output, re.DOTALL)
        if not json_match:
            return relations

        try:
            data = json.loads(json_match.group(0))
            if not isinstance(data, list):
                return relations

            for item in data:
                if not isinstance(item, dict):
                    continue

                source = item.get("source", "").strip()
                target = item.get("target", "").strip()
                rel_type = item.get("relation_type", "").strip().lower()
                description = item.get("description", "").strip()

                # Normalize relation type
                if rel_type in ("derives_from", "derives from"):
                    rel_type = "derives_from"
                elif rel_type in ("impacts", "impact"):
                    rel_type = "impacts"
                elif rel_type in ("correlates_with", "correlates with", "correlated"):
                    rel_type = "correlates_with"
                else:
                    continue

                if source and target and rel_type:
                    relations.append(ExtractedRelation(
                        source=source,
                        target=target,
                        relation_type=rel_type,
                        description=description
                    ))

        except json.JSONDecodeError as e:
            print(f"[RelationMiner] JSON parse failed: {e}")

        return relations

    def mine_batch(self, metrics: List[Dict], metric_name_map: Dict[str, str]) -> List[Dict]:
        """
        Mine relationships for a batch of metrics

        Args:
            metrics: List of metric dictionaries
            metric_name_map: Mapping from metric name to metric code

        Returns:
            List of relation dictionaries ready for database storage
        """
        all_relations = []

        for metric in metrics:
            relations = self.mine_from_business_definition(metric)

            for rel in relations:
                # Look up metric codes by name
                source_code = self._find_metric_code(rel.source, metric_name_map)
                target_code = self._find_metric_code(rel.target, metric_name_map)

                if source_code and target_code:
                    all_relations.append({
                        "source_metric_code": source_code,
                        "target_metric_code": target_code,
                        "relation_type": rel.relation_type.upper(),
                        "weight": 1.0,
                        "description": rel.description
                    })

        return all_relations

    def _find_metric_code(self, name: str, name_map: Dict[str, str]) -> Optional[str]:
        """Find metric code by name"""
        # Direct match
        if name in name_map:
            return name_map[name]

        # Case-insensitive match
        name_lower = name.lower()
        for metric_name, code in name_map.items():
            if metric_name.lower() == name_lower:
                return code

        # Partial match
        for metric_name, code in name_map.items():
            if name_lower in metric_name.lower() or metric_name.lower() in name_lower:
                return code

        return None


if __name__ == "__main__":
    # Test with a sample metric
    miner = RelationMiner()

    test_metric = {
        "name": "广告转化率",
        "business_definition": "广告转化率 = 点击次数 / 曝光次数 × 100%。该指标受广告投放策略、落地页质量、用户定向精度等因素影响，与自然转化率存在一定相关性。"
    }

    relations = miner.mine_from_business_definition(test_metric)
    print(f"Extracted {len(relations)} relations:")
    for r in relations:
        print(f"  {r.source} --[{r.relation_type}]--> {r.target}: {r.description}")
