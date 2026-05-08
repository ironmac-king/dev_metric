"""
语义层引擎基类
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ai.services.semantic_layer.api import ParseResult


class BaseEngine(ABC):
    """
    语义层引擎基类

    所有引擎（本地模型引擎、语义快照引擎、规则引擎、LLM引擎）都继承此基类
    """

    def __init__(self, name: str = "base"):
        self.name = name
        self._initialized = False

    @abstractmethod
    def parse(self, query: str, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        解析查询

        Args:
            query: 用户问题
            context: 上下文信息

        Returns:
            ParseResult: 解析结果
        """
        pass

    def _ensure_init(self):
        """确保引擎已初始化"""
        if not self._initialized:
            self._init()
            self._initialized = True

    def _init(self):
        """初始化引擎（子类实现）"""
        pass
