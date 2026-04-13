"""
模板加载器 - 从 prompt_configs 表加载决策分析模板
"""
from typing import Dict, List, Optional, Any
import httpx
import json
import os
import time
from functools import lru_cache
from ai.client.http_client import get_http_client


class TemplateLoader:
    """决策分析模板加载器"""

    def __init__(self, api_base: str = "http://localhost:8080"):
        self.api_base = api_base
        self._cache: Dict[str, Any] = {}
        self._cache_time = 0
        self._cache_ttl = 300  # 5分钟缓存

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        return time.time() - self._cache_time < self._cache_ttl

    def get_templates(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有决策分析模板

        Returns:
            [{
                "id": 1,
                "name": "ad_analysis",
                "prompt_text": "...",
                "category": "decision_analysis",
                "keywords": "广告,ROAS,ACOS"
            }]
        """
        if not force_refresh and self._cache and self._is_cache_valid():
            return self._cache.get("templates", [])

        try:
            client = get_http_client()
            response = client.get(
                f"{self.api_base}/api/v1/prompt-configs",
                params={"category": "decision_analysis"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    templates = data.get("data", [])
                    self._cache = {
                        "templates": templates,
                        "time": time.time()
                    }
                    return templates
        except Exception as e:
            print(f"[TemplateLoader] 获取模板失败: {e}")

        return []

    def get_template_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取模板"""
        templates = self.get_templates()
        for t in templates:
            if t.get("name") == name:
                return t
        return None

    def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取模板"""
        templates = self.get_templates()
        for t in templates:
            if t.get("id") == template_id:
                return t
        return None

    def parse_placeholder(self, prompt_text: str) -> Dict[str, Any]:
        """
        解析模板占位符

        Returns:
            {
                "metrics": ["MKI-02-0020", "MKI-02-0023"],  # 指标代码列表
                "insights": ["findings", "trend", "anomaly", "suggestion"],
                "raw_text": "..."  # 清理后的文本
            }
        """
        import re

        # 提取指标占位符 {metric_MKI-02-xxx} 或 {metric_xxx}
        metric_pattern = re.findall(r'\{metric_([MKI0-9\-]+)\}', prompt_text)

        # 提取洞察占位符 {insight_xxx}
        insight_pattern = re.findall(r'\{insight_(\w+)\}', prompt_text)

        # 提取基准占位符 {benchmark_MKI-02-xxx}
        benchmark_pattern = re.findall(r'\{benchmark_([MKI0-9\-]+)\}', prompt_text)

        # 清理文本中的占位符标记
        clean_text = prompt_text
        for pattern in [r'\{insights:\s*\[.*?\]\}', r'\{benchmark_[^}]+\}']:
            clean_text = re.sub(pattern, '', clean_text)

        return {
            "metrics": list(set(metric_pattern)),
            "insights": list(set(insight_pattern)),
            "benchmarks": list(set(benchmark_pattern)),
            "raw_text": clean_text.strip()
        }

    def get_template_config(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取模板完整配置（从 variables 字段解析）

        Returns:
            {
                "indicators": [...],  # 指标配置列表
                "max_data_items": 5,   # 最大数据条目
                "benchmark": {...}      # 行业基准
            }
        """
        variables_str = template.get("variables", "{}")
        try:
            variables = json.loads(variables_str)
        except:
            variables = {}

        return {
            "indicators": variables.get("indicators", []),
            "max_data_items": variables.get("max_data_items", 5),
            "benchmark": variables.get("benchmark", {})
        }

    def get_indicators(self, template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取指标配置列表"""
        config = self.get_template_config(template)
        return config.get("indicators", [])

    def get_max_data_items(self, template: Dict[str, Any]) -> int:
        """获取最大数据条目限制"""
        config = self.get_template_config(template)
        return config.get("max_data_items", 5)

    def get_benchmark(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """获取行业基准配置"""
        config = self.get_template_config(template)
        return config.get("benchmark", {})


# 全局实例
template_loader = TemplateLoader()
