"""
A/B 测试框架

支持：
1. 基于 user_id hash 的均匀分流
2. 多 variant 支持
3. 转化指标记录
4. 实验统计分析
"""
import hashlib
import random
import statistics
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from ai.config.logging_config import get_logger

logger = get_logger("ai.feedback.ab_test")


class ExperimentStatus(Enum):
    """实验状态"""
    DRAFT = "draft"           # 草稿
    RUNNING = "running"        # 运行中
    PAUSED = "paused"          # 暂停
    COMPLETED = "completed"     # 已完成


@dataclass
class TestVariant:
    """测试变体"""
    name: str                   # 变体名称（如 control / treatment_a）
    description: str = ""       # 变体描述
    prompt_template: str = ""   # 使用的 prompt 模板
    weight: float = 1.0        # 分流权重（相对于其他 variant）
    is_control: bool = False   # 是否是对照组


@dataclass
class ConversionMetric:
    """转化指标"""
    name: str                   # 指标名称
    value: float                # 指标值
    timestamp: str = ""         # 记录时间


@dataclass
class ABExperiment:
    """A/B 实验"""
    experiment_id: str
    name: str
    description: str = ""
    variants: List[TestVariant] = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    start_time: str = ""
    end_time: str = ""
    created_at: str = ""
    metrics: List[ConversionMetric] = None

    def __post_init__(self):
        if self.variants is None:
            self.variants = []
        if self.metrics is None:
            self.metrics = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "variants": [
                {
                    "name": v.name,
                    "description": v.description,
                    "weight": v.weight,
                    "is_control": v.is_control,
                }
                for v in self.variants
            ],
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "created_at": self.created_at,
        }


class ABTestManager:
    """
    A/B 测试管理器

    使用方式：
    1. 创建实验和 variant
    2. 为用户分配 variant
    3. 记录转化指标
    4. 分析实验结果
    """

    def __init__(self):
        self._experiments: Dict[str, ABExperiment] = {}
        self._user_assignments: Dict[str, Dict[str, str]] = {}  # {experiment_id: {user_id: variant_name}}
        self._variant_metrics: Dict[str, Dict[str, List[float]]] = {}  # {experiment_id: {variant_name: [metric_values]}}

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str = "",
        variants: List[TestVariant] = None,
    ) -> ABExperiment:
        """
        创建实验

        Args:
            experiment_id: 实验 ID
            name: 实验名称
            description: 实验描述
            variants: 测试变体列表

        Returns:
            ABExperiment
        """
        experiment = ABExperiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            variants=variants or [],
            created_at=datetime.now().isoformat(),
        )
        self._experiments[experiment_id] = experiment
        self._user_assignments[experiment_id] = {}
        self._variant_metrics[experiment_id] = {v.name: [] for v in variants}

        logger.info(f"[ABTestManager] 创建实验: {experiment_id} - {name}")
        return experiment

    def start_experiment(self, experiment_id: str) -> bool:
        """启动实验"""
        if experiment_id not in self._experiments:
            logger.warning(f"[ABTestManager] 实验不存在: {experiment_id}")
            return False

        experiment = self._experiments[experiment_id]
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_time = datetime.now().isoformat()

        logger.info(f"[ABTestManager] 启动实验: {experiment_id}")
        return True

    def stop_experiment(self, experiment_id: str) -> bool:
        """停止实验"""
        if experiment_id not in self._experiments:
            return False

        experiment = self._experiments[experiment_id]
        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_time = datetime.now().isoformat()

        logger.info(f"[ABTestManager] 停止实验: {experiment_id}")
        return True

    def assign_variant(self, experiment_id: str, user_id: str) -> Optional[str]:
        """
        为用户分配 variant（基于 hash 均匀分流）

        Args:
            experiment_id: 实验 ID
            user_id: 用户 ID

        Returns:
            variant 名称
        """
        if experiment_id not in self._experiments:
            return None

        experiment = self._experiments[experiment_id]
        if experiment.status != ExperimentStatus.RUNNING:
            return None

        # 检查是否已分配
        if user_id in self._user_assignments[experiment_id]:
            return self._user_assignments[experiment_id][user_id]

        # 计算 hash
        hash_input = f"{experiment_id}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        # 计算总权重
        total_weight = sum(v.weight for v in experiment.variants)

        # 根据 hash 分配 variant
        normalized_hash = (hash_value % 10000) / 10000.0  # 0 ~ 1
        cumulative = 0.0

        for variant in experiment.variants:
            cumulative += variant.weight / total_weight
            if normalized_hash < cumulative:
                self._user_assignments[experiment_id][user_id] = variant.name
                logger.info(f"[ABTestManager] 用户 {user_id} 分配到 variant {variant.name}")
                return variant.name

        # 兜底分配到第一个 variant
        self._user_assignments[experiment_id][user_id] = experiment.variants[0].name
        return experiment.variants[0].name

    def record_conversion(
        self,
        experiment_id: str,
        user_id: str,
        metric_name: str,
        metric_value: float,
    ) -> bool:
        """
        记录转化指标

        Args:
            experiment_id: 实验 ID
            user_id: 用户 ID
            metric_name: 指标名称
            metric_value: 指标值

        Returns:
            是否记录成功
        """
        if experiment_id not in self._experiments:
            return False

        variant_name = self._user_assignments.get(experiment_id, {}).get(user_id)
        if not variant_name:
            logger.warning(f"[ABTestManager] 用户 {user_id} 未分配 variant")
            return False

        if experiment_id not in self._variant_metrics:
            self._variant_metrics[experiment_id] = {}
        if variant_name not in self._variant_metrics[experiment_id]:
            self._variant_metrics[experiment_id][variant_name] = []

        self._variant_metrics[experiment_id][variant_name].append(metric_value)

        # 记录到 experiment
        experiment = self._experiments[experiment_id]
        experiment.metrics.append(ConversionMetric(
            name=metric_name,
            value=metric_value,
            timestamp=datetime.now().isoformat(),
        ))

        logger.info(f"[ABTestManager] 记录转化: {user_id} -> {variant_name}, {metric_name}={metric_value}")
        return True

    def get_variant(self, experiment_id: str, user_id: str) -> Optional[str]:
        """获取用户的 variant"""
        return self._user_assignments.get(experiment_id, {}).get(user_id)

    def analyze_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """
        分析实验结果

        Returns:
            分析报告
        """
        if experiment_id not in self._experiments:
            return {}

        experiment = self._experiments[experiment_id]
        variant_metrics = self._variant_metrics.get(experiment_id, {})

        results = {
            "experiment_id": experiment_id,
            "name": experiment.name,
            "status": experiment.status.value,
            "variants": [],
        }

        # 计算每个 variant 的统计信息
        for variant in experiment.variants:
            metrics = variant_metrics.get(variant.name, [])
            if metrics:
                variant_stats = {
                    "name": variant.name,
                    "is_control": variant.is_control,
                    "sample_size": len(metrics),
                    "mean": statistics.mean(metrics),
                    "median": statistics.median(metrics),
                    "stdev": statistics.stdev(metrics) if len(metrics) > 1 else 0,
                }

                # 如果有对照组，计算相对提升
                if not variant.is_control:
                    control_metrics = variant_metrics.get(
                        next((v.name for v in experiment.variants if v.is_control), ""),
                        [],
                    )
                    if control_metrics:
                        control_mean = statistics.mean(control_metrics)
                        if control_mean > 0:
                            lift = (variant_stats["mean"] - control_mean) / control_mean * 100
                            variant_stats["lift_percent"] = lift

                results["variants"].append(variant_stats)

        # 统计显著性检验（简单的 z-test）
        if len(results["variants"]) >= 2:
            results["significance"] = self._calculate_significance(
                variant_metrics,
                [v.name for v in experiment.variants if v.is_control],
                [v.name for v in experiment.variants if not v.is_control],
            )

        return results

    def _calculate_significance(
        self,
        variant_metrics: Dict[str, List[float]],
        control_names: List[str],
        treatment_names: List[str],
    ) -> Dict[str, Any]:
        """计算统计显著性（简化版）"""
        control_values = []
        for name in control_names:
            control_values.extend(variant_metrics.get(name, []))

        treatment_values = []
        for name in treatment_names:
            treatment_values.extend(variant_metrics.get(name, []))

        if not control_values or not treatment_values:
            return {"significant": False, "reason": "样本不足"}

        control_mean = statistics.mean(control_values)
        treatment_mean = statistics.mean(treatment_values)

        # 简化版 z-test
        if len(control_values) < 30 or len(treatment_values) < 30:
            return {
                "significant": False,
                "reason": "样本不足（需要至少30个样本）",
                "control_mean": control_mean,
                "treatment_mean": treatment_mean,
            }

        # 计算 z-score
        control_std = statistics.stdev(control_values)
        treatment_std = statistics.stdev(treatment_values)

        if control_std == 0 or treatment_std == 0:
            return {"significant": False, "reason": "标准差为0"}

        pooled_se = ((control_std ** 2) / len(control_values) + (treatment_std ** 2) / len(treatment_values)) ** 0.5
        if pooled_se == 0:
            return {"significant": False, "reason": "标准误为0"}

        z_score = abs(treatment_mean - control_mean) / pooled_se

        # |z| > 1.96 则 p < 0.05
        significant = z_score > 1.96

        return {
            "significant": significant,
            "z_score": z_score,
            "p_value": 2 * (1 - 0.5 * (1 + abs(z_score) ** 0.5)),  # 简化
            "control_mean": control_mean,
            "treatment_mean": treatment_mean,
        }

    def get_experiment(self, experiment_id: str) -> Optional[ABExperiment]:
        """获取实验"""
        return self._experiments.get(experiment_id)

    def list_experiments(self) -> List[ABExperiment]:
        """列出所有实验"""
        return list(self._experiments.values())


# 全局单例
_ab_test_manager: Optional[ABTestManager] = None


def get_ab_test_manager() -> ABTestManager:
    """获取全局 A/B 测试管理器"""
    global _ab_test_manager
    if _ab_test_manager is None:
        _ab_test_manager = ABTestManager()
    return _ab_test_manager
