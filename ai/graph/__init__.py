"""对话图模块

[DEPRECATED] V1（旧版）模块，已被 ai.engine.llm_v2 取代。
仅保留旧版状态类型定义，不建议在新代码中使用。
"""
from ai.graph.state import IntentResult, SQLGenerationResult, ClarificationDecision, ClarificationType

__all__ = ["IntentResult", "SQLGenerationResult", "ClarificationDecision", "ClarificationType"]
