"""调试 SSE 流式输出"""
import asyncio
import httpx

async def test_sse():
    """测试 SSE 流式输出"""
    url = "http://localhost:8081/api/v1/analysis/stream"

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            url,
            json={"query": "分析近30天广告投放效果", "session_id": "test_session"}
        ) as response:
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")

            chunk_count = 0
            total_data = ""

            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    print(f"[{chunk_count}] Event: {line}")
                elif line.startswith("data:"):
                    data_content = line[5:] if line.startswith("data:") else line
                    print(f"[{chunk_count}] Data: {repr(data_content[:100])}...")
                    total_data += data_content
                    chunk_count += 1
                    if chunk_count >= 5:
                        print("\n--- 前5个数据块已显示，停止测试 ---\n")
                        break

            print(f"\n总共收到 {chunk_count} 个数据块")
            print(f"前200字符: {repr(total_data[:200])}")

asyncio.run(test_sse())