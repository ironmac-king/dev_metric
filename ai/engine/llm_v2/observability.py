"""
V2 可观测性 - OpenTelemetry 链路追踪

提供：
1. 节点执行追踪
2. 分布式追踪
3. 错误追踪
4. 性能指标导出
"""
import time
import functools
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from contextvars import ContextVar

from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.observability")

# Trace context
_current_span: ContextVar[Optional["Span"]] = ContextVar("current_span", default=None)

# 全局追踪器实例
_tracer: Optional["OpenTelemetryTracer"] = None


class Span:
    """追踪跨度"""

    def __init__(
        self,
        name: str,
        trace_id: str = None,
        span_id: str = None,
        parent_span_id: str = None,
    ):
        self.name = name
        self.trace_id = trace_id or generate_id(16)
        self.span_id = span_id or generate_id(8)
        self.parent_span_id = parent_span_id
        self.start_time = datetime.now()
        self.end_time = None
        self.duration_ms = 0
        self.attributes: Dict[str, Any] = {}
        self.status = "ok"  # ok / error
        self.error_message = ""
        self.children: list = []

    def set_attribute(self, key: str, value: Any) -> None:
        """设置属性"""
        self.attributes[key] = value

    def set_status(self, status: str, error_message: str = "") -> None:
        """设置状态"""
        self.status = status
        self.error_message = error_message

    def end(self) -> None:
        """结束跨度"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "status": self.status,
            "error_message": self.error_message,
        }


class SpanContext:
    """Span context manager，用于 with 语句"""

    def __init__(self, tracer: "OpenTelemetryTracer", name: str, parent_span: Span = None):
        self._tracer = tracer
        self._name = name
        self._parent_span = parent_span
        self._span: Optional[Span] = None

    def __enter__(self) -> Span:
        self._span = self._tracer.start_span(self._name, self._parent_span)
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self._span.set_status("error", str(exc_val))
        self._span.end()
        return False

    async def __aenter__(self) -> Span:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


class OpenTelemetryTracer:
    """OpenTelemetry 追踪器

    提供类似 OpenTelemetry 的追踪接口。
    生产环境可替换为真正的 OpenTelemetry SDK。
    """

    def __init__(self, service_name: str = "v2-llm-service"):
        self.service_name = service_name
        self._spans: Dict[str, Span] = {}
        self._enabled = True

    def start_span(self, name: str, parent_span: Span = None) -> "Span":
        """开始一个新的跨度"""
        parent_span_id = parent_span.span_id if parent_span else None
        span = Span(
            name=name,
            parent_span_id=parent_span_id,
        )
        self._spans[span.span_id] = span
        return span

    def end_span(self, span: Span) -> None:
        """结束跨度"""
        span.end()

    def start_span_context(self, name: str, parent_span: Span = None) -> "SpanContext":
        """开始一个新的跨度并返回 context manager"""
        return SpanContext(self, name, parent_span)

    def get_trace(self, trace_id: str) -> Optional[Span]:
        """获取追踪"""
        for span in self._spans.values():
            if span.trace_id == trace_id:
                return span
        return None

    def get_all_spans(self) -> list:
        """获取所有跨度"""
        return [s.to_dict() for s in self._spans.values()]

    def clear(self) -> None:
        """清除所有追踪数据"""
        self._spans.clear()

    def export_to_jaeger(self, jaeger_endpoint: str = None) -> Dict[str, Any]:
        """导出追踪数据到 Jaeger

        生产环境使用真实的 Jaeger exporter。
        这里返回兼容格式。
        """
        traces = []
        for span in self._spans.values():
            traces.append({
                "traceID": span.trace_id,
                "spanID": span.span_id,
                "operationName": span.name,
                "startTime": int(span.start_time.timestamp() * 1000),
                "duration": int(span.duration_ms * 1000),
                "tags": [
                    {"key": k, "value": str(v)}
                    for k, v in span.attributes.items()
                ],
                "status": span.status,
                "error": span.error_message,
            })
        return {
            "serviceName": self.service_name,
            "traces": traces,
        }


def generate_id(length: int = 16) -> str:
    """生成随机 ID"""
    import random
    chars = "0123456789abcdef"
    return "".join(random.choice(chars) for _ in range(length))


def get_tracer() -> OpenTelemetryTracer:
    """获取全局追踪器"""
    global _tracer
    if _tracer is None:
        _tracer = OpenTelemetryTracer()
    return _tracer


def trace_node(node_name: str) -> Callable:
    """节点追踪装饰器

    用法：
    @trace_node("intent_router")
    async def intent_router(state):
        ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            parent_span = _current_span.get()

            with tracer.start_span_context(node_name, parent_span) as span:
                token = _current_span.set(span)
                try:
                    result = await func(*args, **kwargs)

                    # 记录结果属性
                    if hasattr(result, "error") and result.error:
                        span.set_status("error", result.error)
                    elif hasattr(result, "mql") and result.mql:
                        span.set_attribute("mql.intent", result.mql.intent.value)

                    return result
                except Exception as e:
                    span.set_status("error", str(e))
                    raise
                finally:
                    _current_span.reset(token)

        return wrapper
    return decorator


class TraceContext:
    """追踪上下文管理器"""

    def __init__(self, tracer: OpenTelemetryTracer, span_name: str):
        self.tracer = tracer
        self.span_name = span_name
        self.span: Optional[Span] = None
        self.token = None

    def __enter__(self):
        parent_span = _current_span.get()
        self.span = self.tracer.start_span(self.span_name, parent_span)
        self.token = _current_span.set(self.span)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.span.set_status("error", str(exc_val))
        self.span.end()
        _current_span.reset(self.token)
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)


def create_trace_context(span_name: str) -> TraceContext:
    """创建追踪上下文"""
    tracer = get_tracer()
    return TraceContext(tracer, span_name)
