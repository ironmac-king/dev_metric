"""
pytest 配置和 fixtures
"""
import pytest
import asyncio
import sys
import importlib
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入 mock fixtures 模块以注册到 pytest
from tests.mocks import mock_go_api, mock_starrocks, mock_llm  # noqa: F401


def _load_optional_engine(module_name: str, class_name: str):
    """Load optional engine modules lazily so unrelated tests can still run."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        pytest.skip(f"optional engine module unavailable: {module_name} ({exc})")
    return getattr(module, class_name)


@pytest.fixture(autouse=True)
def reset_singletons():
    """每个测试后重置单例"""
    import ai.engine.llm as llm_module
    import ai.engine.rule_engine as rule_module

    llm_module._llm_engine = None
    rule_module._instance = None
    yield
    llm_module._llm_engine = None
    rule_module._instance = None


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环 fixture"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def legacy_engine():
    """Legacy 引擎 fixture"""
    engine_cls = _load_optional_engine("ai.engine.legacy_engine", "LegacyEngine")
    return engine_cls()


@pytest.fixture
def langgraph_engine():
    """LangGraph 引擎 fixture"""
    engine_cls = _load_optional_engine("ai.engine.langgraph_engine", "LangGraphEngine")
    return engine_cls()


@pytest.fixture
def session_id():
    """生成唯一 session_id"""
    import uuid
    return f"test-{uuid.uuid4().hex[:8]}"
