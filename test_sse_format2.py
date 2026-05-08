"""简单测试 SSE 格式"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def test_sse_format():
    """测试 SSE 格式是否正确"""
    import httpx

    url = "http://localhost:8081/api/v1/analysis/stream"

    async with httpx.AsyncClient(timeout=30) as client:
        # 只发送请求，不等待完成
        response = await client.post(
            url,
            json={"query": "测试", "session_id": "test"}
        )

        content = response.text
        print(f"响应长度: {len(content)}")

        # 检查 SSE 格式
        lines = content.split('\n')
        print(f"总行数: {len(lines)}")

        # 显示前20行
        print("\n前20行:")
        for i, line in enumerate(lines[:20]):
            preview = line[:80] if len(line) > 80 else line
            print(f"{i}: {repr(preview)}")

asyncio.run(test_sse_format())