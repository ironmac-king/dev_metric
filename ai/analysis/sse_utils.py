"""
SSE 流式输出工具
"""
from dataclasses import dataclass
from typing import AsyncIterator
import json
import asyncio


@dataclass
class SSEEvent:
    """SSE 事件"""
    event: str
    data: str


async def sse_generator(events: AsyncIterator[SSEEvent]) -> AsyncIterator[bytes]:
    """将事件流转换为 SSE 格式"""
    yield b"event: connected\ndata: {}\n\n"

    try:
        async for event in events:
            # 格式化事件，多行数据需要每行都以 data: 开头
            lines = event.data.split('\n')
            # 空行用 'data:' 表示（不带尾随空格），避免前端拼接问题
            data_lines = '\n'.join(f'data: {line}' if line else 'data:' for line in lines)
            message = f"event: {event.event}\n{data_lines}\n\n"
            yield message.encode("utf-8")
            # 小延迟避免前端处理不过来
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        yield "event: cancelled\ndata: User cancelled\n\n".encode("utf-8")
        raise
    except Exception as e:
        error_msg = f"分析出错: {str(e)}"
        yield f"event: error\ndata: {error_msg}\n\n".encode("utf-8")


def create_sse_event(event_type: str, data: any) -> SSEEvent:
    """创建 SSE 事件"""
    if isinstance(data, (dict, list)):
        return SSEEvent(event=event_type, data=json.dumps(data, ensure_ascii=False))
    elif isinstance(data, str):
        return SSEEvent(event=event_type, data=data)
    else:
        return SSEEvent(event=event_type, data=str(data))
