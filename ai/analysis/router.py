"""
决策分析 API 路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio

from .agent import AnalysisAgent, run_analysis, AnalysisRequest
from .sse_utils import sse_generator
from .template_loader import template_loader
from .template_matcher import template_matcher


# 请求模型
class AnalysisRequestModel(BaseModel):
    session_id: str = ""
    query: str = ""
    metric_codes: List[str] = []
    time_range: str = "近30天"


class TemplateMatchRequest(BaseModel):
    session_id: str
    query: str = ""


# 响应模型
class TemplateMatchResponse(BaseModel):
    template_id: Optional[int]
    template_name: Optional[str]
    confidence: float
    matched_reason: str
    needs_confirmation: bool
    candidates: List[Dict[str, Any]]


# 路由
router = APIRouter(prefix="/api/v1/analysis", tags=["决策分析"])


@router.get("/templates")
async def get_templates():
    """获取所有可用的决策分析模板"""
    templates = template_loader.get_templates()
    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "description": t.get("description", ""),
                "keywords": t.get("keywords", ""),
                "category": t.get("category", "")
            }
            for t in templates
        ]
    }


@router.get("/match-template")
async def match_template(session_id: str, query: str = ""):
    """根据 session_id 和 query 匹配模板"""
    # 获取上下文
    # TODO: 从会话获取上下文信息

    context = {
        "metric_name": "",
        "metric_code": ""
    }

    templates = template_loader.get_templates()
    match_result = await template_matcher.match(query, context, templates)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "template_id": match_result.template.get("id") if match_result.template else None,
            "template_name": match_result.template.get("name") if match_result.template else None,
            "confidence": match_result.confidence,
            "matched_reason": match_result.matched_reason,
            "needs_confirmation": match_result.needs_confirmation,
            "candidates": [
                {"id": t.get("id"), "name": t.get("name")}
                for t in (match_result.candidates or [])
            ]
        }
    }


@router.post("/stream")
async def analysis_stream(request: AnalysisRequestModel):
    """
    SSE 流式分析接口

    返回 SSE 事件流：
    - thinking: 思考中状态
    - insight: 洞察计算结果
    - chunk: 文字片段
    - chart: 图表数据
    - done: 完成
    - error: 错误
    - confirm: 需要用户确认
    """
    # 创建分析请求
    analysis_request = AnalysisRequest(
        session_id=request.session_id,
        query=request.query,
        metric_codes=request.metric_codes,
        time_range=request.time_range
    )

    # 创建 agent
    agent = AnalysisAgent(analysis_request)

    async def event_generator():
        try:
            async for event in agent.run_streaming():
                # 将事件转换为 SSE 格式（多行数据需要每行都以 data: 开头）
                lines = event.data.split('\n')
                data_lines = '\n'.join(f'data: {line}' for line in lines)
                message = f"event: {event.event}\n{data_lines}\n\n"
                yield message.encode("utf-8")
                # 立即让出控制权，确保数据发送到网络
                await asyncio.sleep(0)
        except Exception as e:
            error_msg = f"分析出错: {str(e)}"
            yield f"event: error\ndata: {error_msg}\n\n".encode("utf-8")
        finally:
            # 显式发送终止信号，确保连接被正确关闭
            # 发送空数据表示流结束（符合 SSE 规范）
            yield b'event: close\ndata: \n\n'
            # 添加短暂延迟确保终止信号被发送
            await asyncio.sleep(0.05)
            # 关闭 agent（包含 HTTP 客户端等资源）
            await agent.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/analyze")
async def analysis_non_stream(request: AnalysisRequestModel):
    """
    非流式分析接口

    返回完整分析报告：
    - answer: markdown 格式报告
    - charts: 图表数据列表
    """
    # 创建分析请求
    analysis_request = AnalysisRequest(
        session_id=request.session_id,
        query=request.query,
        metric_codes=request.metric_codes,
        time_range=request.time_range
    )

    # 创建 agent
    agent = AnalysisAgent(analysis_request)

    try:
        # 执行分析（非流式）
        result = await agent.run()

        return {
            "code": 0,
            "message": "success",
            "data": {
                "answer": result.get("answer", ""),
                "charts": result.get("charts", [])
            }
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[Router] /analyze exception: {e}")
        print(f"[Router] Traceback: {tb}")
        return {
            "code": 500,
            "message": f"分析出错: {str(e)}",
            "data": None
        }
    finally:
        await agent.close()


@router.post("/match-and-stream")
async def match_and_stream(request: AnalysisRequestModel):
    """
    匹配模板并流式分析
    """
    # 先匹配模板
    templates = template_loader.get_templates()
    context = {"metric_name": "", "metric_code": ""}
    match_result = await template_matcher.match(
        request.query,
        context,
        templates
    )

    if match_result.needs_confirmation and not match_result.template:
        # 需要确认，返回候选模板
        return {
            "code": 202,
            "message": "需要确认模板",
            "data": {
                "candidates": [
                    {"id": t.get("id"), "name": t.get("name")}
                    for t in (match_result.candidates or [])
                ]
            }
        }

    # 执行分析
    analysis_request = AnalysisRequest(
        session_id=request.session_id,
        query=request.query,
        metric_codes=request.metric_codes or [],
        time_range=request.time_range
    )

    agent = AnalysisAgent(analysis_request)

    async def event_generator():
        try:
            async for event in agent.run_streaming():
                lines = event.data.split('\n')
                data_lines = '\n'.join(f'data: {line}' for line in lines)
                message = f"event: {event.event}\n{data_lines}\n\n"
                yield message.encode("utf-8")
                await asyncio.sleep(0.01)
        except Exception as e:
            error_msg = f"分析出错: {str(e)}"
            yield f"event: error\ndata: {error_msg}\n\n".encode("utf-8")
        finally:
            # 显式发送终止信号，确保连接被正确关闭
            yield b'event: close\ndata: \n\n'
            await asyncio.sleep(0.05)
            await agent.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
