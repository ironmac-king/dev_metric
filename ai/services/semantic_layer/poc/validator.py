"""
Phase 0 PoC 验证器 - 使用本地模型验证

验证本地模型能否替代当前11步的语义理解能力

目标指标：
- 覆盖率：本地模型能处理的查询数 / 总查询数
- 准确率：本地模型结果与11步结果一致的比例
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from ai.config.logging_config import get_logger

logger = get_logger("semantic_layer.poc")

# 导入测试用例
from ai.services.semantic_layer.poc.test_cases import ALL_TEST_CASES, INTENT_DISTRIBUTION

# 导入本地模型
try:
    from ai.engine.llm_v2.nodes.local_intent_model import get_local_intent_model
    LOCAL_MODEL_AVAILABLE = True
    logger.info("本地模型加载成功")
except Exception as e:
    LOCAL_MODEL_AVAILABLE = False
    logger.warning(f"本地模型加载失败: {e}，将跳过本地模型测试")


@dataclass
class ParseResult:
    """解析结果"""
    query: str
    intent: str
    metric: Optional[str] = None
    dimensions: List[str] = field(default_factory=list)
    time_expr: Optional[str] = None
    comparison_type: Optional[str] = None
    confidence: float = 0.0  # 置信度 0-1
    parse_method: str = ""  # local_model/snapshot/rule/llm/unknown
    entities: List[Dict[str, Any]] = field(default_factory=list)
    raw_result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ValidationResult:
    """验证结果"""
    total: int = 0
    covered: int = 0  # 本地模型能处理的
    uncovered: int = 0  # 本地模型不能处理的
    matched: int = 0  # 与11步意图一致的
    mismatched: int = 0  # 与11步意图不一致的

    coverage_rate: float = 0.0
    accuracy_rate: float = 0.0

    by_intent: Dict[str, Dict[str, int]] = field(default_factory=dict)  # 按意图统计
    cases: List[Dict[str, Any]] = field(default_factory=list)  # 详细case结果


class LocalModelEngine:
    """
    本地模型引擎 - 使用 Joint BERT 模型解析
    """

    def __init__(self):
        self.model = None
        if LOCAL_MODEL_AVAILABLE:
            try:
                self.model = get_local_intent_model()
                logger.info("LocalModelEngine 初始化成功")
            except Exception as e:
                logger.warning(f"LocalModelEngine 初始化失败: {e}")
                self.model = None

    def parse(self, query: str) -> ParseResult:
        """
        用本地模型解析查询
        """
        if not self.model:
            return ParseResult(
                query=query,
                intent="unknown",
                confidence=0.0,
                parse_method="model_unavailable",
                error="模型未加载"
            )

        try:
            result = self.model.predict(query)

            # 提取实体
            entities = result.get('entities', [])

            # 提取指标
            metric = None
            for ent in entities:
                if ent.get('type') == 'METRIC':
                    metric = ent.get('text')
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
                    dimensions.append(ent.get('text'))
                elif ent.get('type') == 'DIM_VALUE':
                    dimensions.append(ent.get('text'))

            return ParseResult(
                query=query,
                intent=result.get('intent', 'unknown'),
                metric=metric,
                dimensions=dimensions,
                time_expr=time_expr,
                confidence=result.get('confidence', 0.0),
                parse_method="local_model",
                entities=entities,
                raw_result=result
            )

        except Exception as e:
            logger.error(f"[LocalModelEngine] parse error for '{query}': {e}")
            return ParseResult(
                query=query,
                intent="unknown",
                confidence=0.0,
                parse_method="error",
                error=str(e)
            )


class POCValidator:
    """
    Phase 0 PoC 验证器
    """

    def __init__(self):
        self.local_model_engine = LocalModelEngine()

    def validate(self, test_cases: List[Dict[str, Any]]) -> ValidationResult:
        """
        执行验证
        """
        result = ValidationResult()
        result.total = len(test_cases)

        for case in test_cases:
            query = case["query"]
            expected_intent = case["expected_intent"]

            # 用本地模型解析
            parse_result = self.local_model_engine.parse(query)

            # 判断是否覆盖（confidence >= 0.5 算覆盖）
            covered = parse_result.confidence >= 0.5 and parse_result.intent != "unknown"

            # 判断是否匹配（意图一致）
            matched = parse_result.intent == expected_intent

            # 统计
            if covered:
                result.covered += 1
            else:
                result.uncovered += 1

            if matched:
                result.matched += 1
            else:
                result.mismatched += 1

            # 按意图统计
            intent_key = expected_intent
            if intent_key not in result.by_intent:
                result.by_intent[intent_key] = {"total": 0, "covered": 0, "matched": 0}

            result.by_intent[intent_key]["total"] += 1
            if covered:
                result.by_intent[intent_key]["covered"] += 1
            if matched:
                result.by_intent[intent_key]["matched"] += 1

            # 记录详细case
            result.cases.append({
                "query": query,
                "expected_intent": expected_intent,
                "parsed_intent": parse_result.intent,
                "confidence": parse_result.confidence,
                "parse_method": parse_result.parse_method,
                "covered": covered,
                "matched": matched,
                "metric": parse_result.metric,
                "dimensions": parse_result.dimensions,
                "time_expr": parse_result.time_expr,
                "entities": parse_result.entities,
                "note": case.get("note", ""),
            })

        # 计算比率
        result.coverage_rate = result.covered / result.total if result.total > 0 else 0
        result.accuracy_rate = result.matched / result.total if result.total > 0 else 0

        return result

    def generate_report(self, result: ValidationResult) -> str:
        """生成验证报告"""
        report = []
        report.append("=" * 80)
        report.append("Phase 0 PoC 验证报告 - 本地模型 vs 11步")
        report.append("=" * 80)
        report.append("")
        report.append(f"本地模型可用: {LOCAL_MODEL_AVAILABLE}")
        report.append("")

        # 总体指标
        report.append("【总体指标】")
        report.append(f"  总测试用例: {result.total}")
        report.append(f"  覆盖率: {result.coverage_rate:.1%} ({result.covered}/{result.total})")
        report.append(f"  准确率: {result.accuracy_rate:.1%} ({result.matched}/{result.total})")
        report.append(f"  未覆盖: {result.uncovered}")
        report.append(f"  不匹配: {result.mismatched}")
        report.append("")

        # 按意图统计
        report.append("【按意图统计】")
        report.append(f"{'意图':<20} {'总计':>8} {'覆盖':>8} {'匹配':>8} {'覆盖率高':>10} {'准确率高':>10}")
        report.append("-" * 70)

        for intent, stats in sorted(result.by_intent.items()):
            total = stats["total"]
            covered = stats["covered"]
            matched = stats["matched"]
            cov_rate = covered / total if total > 0 else 0
            acc_rate = matched / total if total > 0 else 0
            report.append(f"{intent:<20} {total:>8} {covered:>8} {matched:>8} {cov_rate:>10.1%} {acc_rate:>10.1%}")

        report.append("")

        # 不匹配的case（显示前10个）
        mismatched_cases = [c for c in result.cases if not c["matched"]]
        if mismatched_cases:
            report.append("【不匹配案例】")
            for i, c in enumerate(mismatched_cases[:10], 1):
                report.append(f"  {i}. 查询: {c['query'][:40]}...")
                report.append(f"     预期: {c['expected_intent']}, 实际: {c['parsed_intent']}, 置信度: {c['confidence']:.2f}")
                if c.get("note"):
                    report.append(f"     备注: {c['note']}")
            if len(mismatched_cases) > 10:
                report.append(f"  ... 还有 {len(mismatched_cases) - 10} 个不匹配案例")
            report.append("")

        # 未覆盖的case（显示前10个）
        uncovered_cases = [c for c in result.cases if not c["covered"]]
        if uncovered_cases:
            report.append("【未覆盖案例】")
            for i, c in enumerate(uncovered_cases[:10], 1):
                report.append(f"  {i}. 查询: {c['query'][:40]}...")
                report.append(f"     预期: {c['expected_intent']}, 置信度: {c['confidence']:.2f}")
            if len(uncovered_cases) > 10:
                report.append(f"  ... 还有 {len(uncovered_cases) - 10} 个未覆盖案例")
            report.append("")

        # 结论
        report.append("=" * 80)
        report.append("【结论】")

        if result.coverage_rate >= 0.7:
            report.append("  [PASS] 覆盖率 >= 70%，可以继续实施语义层架构")
        elif result.coverage_rate >= 0.5:
            report.append("  [WARN] 覆盖率 50-70%，需要加强规则引擎补全")
        else:
            report.append("  [FAIL] 覆盖率 < 50%，需要重新评估策略")

        if result.accuracy_rate >= 0.9:
            report.append("  [PASS] 准确率 >= 90%，语义层结果可信")
        elif result.accuracy_rate >= 0.7:
            report.append("  [WARN] 准确率 70-90%，需要分析错误案例改进解析逻辑")
        else:
            report.append("  [FAIL] 准确率 < 70%，需要大幅改进解析能力")

        report.append("=" * 80)

        return "\n".join(report)


def run_poc():
    """运行 PoC 验证"""
    print("开始 Phase 0 PoC 验证...")
    print(f"加载 {len(ALL_TEST_CASES)} 个测试用例")
    print(f"意图分布: {INTENT_DISTRIBUTION}")
    print(f"本地模型可用: {LOCAL_MODEL_AVAILABLE}")
    print("")

    if not LOCAL_MODEL_AVAILABLE:
        print("[ERROR] 本地模型不可用，无法进行验证")
        return None

    validator = POCValidator()
    result = validator.validate(ALL_TEST_CASES)

    report = validator.generate_report(result)
    print(report)

    # 保存详细结果到文件
    output_path = Path(__file__).parent / "poc_results_local_model.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": result.total,
                "covered": result.covered,
                "uncovered": result.uncovered,
                "matched": result.matched,
                "mismatched": result.mismatched,
                "coverage_rate": result.coverage_rate,
                "accuracy_rate": result.accuracy_rate,
                "local_model_available": LOCAL_MODEL_AVAILABLE,
            },
            "by_intent": result.by_intent,
            "cases": result.cases,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到: {output_path}")

    return result


if __name__ == "__main__":
    run_poc()
