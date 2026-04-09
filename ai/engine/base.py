"""对话引擎抽象接口"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class ConversationEngine(ABC):
    """对话引擎抽象接口 - A/B Test 切换"""

    @abstractmethod
    async def process(
        self,
        question: str,
        session_id: str,
        page: int = 1,
        page_size: int = 10,
        user_id: str = "default",
        dept_id: int = 0,
        data_filter: str = ""
    ) -> Dict[str, Any]:
        """
        处理对话请求，返回 AskResponse 格式的字典

        Args:
            question: 用户问题
            session_id: 会话 ID
            page: 页码
            page_size: 每页条数
            user_id: 用户ID，用于日志隔离
            dept_id: 部门ID，用于数据权限
            data_filter: 自定义SQL WHERE条件

        Returns:
            {
                "session_id": str,
                "answer": str,
                "suggest": List[str],
                "sql": Optional[str],
                "thinking_steps": List[Dict],
                ...
            }
        """
        pass

    @abstractmethod
    async def get_state(self, session_id: str) -> Optional[Any]:
        """获取会话状态"""
        pass


def get_engine(engine_type: str = "langgraph") -> ConversationEngine:
    """
    工厂函数：根据 engine_type 获取引擎

    Args:
        engine_type: "langgraph" | "llm"

    Returns:
        ConversationEngine 实例
    """
    if engine_type == "langgraph":
        from ai.engine.langgraph_engine import LangGraphEngine
        return LangGraphEngine()
    elif engine_type == "llm":
        from ai.engine.llm_query_engine import LLMQueryEngine
        return LLMQueryEngine()
    else:
        # 默认使用 langgraph
        from ai.engine.langgraph_engine import LangGraphEngine
        return LangGraphEngine()
