"""测试 SSE 流式输出"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def test_streaming():
    """测试 SSE 流式输出"""
    import httpx

    url = "http://localhost:8081/api/v1/analysis/stream"

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            url,
            json={"query": "分析近30天广告投放效果", "session_id": "test_session"}
        ) as response:
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")

            chunk_count = 0
            thinking_count = 0
            last_chunk_time = None

            async for line in response.aiter_lines():
                if line.startswith("event: thinking"):
                    thinking_count += 1
                    print(f"[thinking {thinking_count}] {line[:60]}...")
                elif line.startswith("data:") and not line.startswith("data: [耗时]"):
                    data_preview = line[5:50] + "..." if len(line) > 50 else line[5:]
                    print(f"[chunk {chunk_count}] {data_preview}")
                    chunk_count += 1
                    if chunk_count >= 10:
                        print("\n... 收到10个 chunk，停止测试 ...")
                        break

            print(f"\n总计: {thinking_count} 个 thinking 事件, {chunk_count} 个 chunk")

asyncio.run(test_streaming())