"""完整调试 SSE 流式输出"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def test_sse_full():
    """测试完整的 SSE 响应"""
    url = "http://localhost:8081/api/v1/analysis/stream"

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            url,
            json={"query": "分析近30天广告投放效果", "session_id": "test_session"}
        )

        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")

        # 获取原始字节
        content = response.content
        print(f"\n原始字节长度: {len(content)}")

        # 尝试解码为文本
        text = content.decode('utf-8')
        print(f"解码后长度: {len(text)}")

        # 按行分割
        lines = text.split('\n')
        print(f"总行数: {len(lines)}")

        # 显示前50行
        print("\n=== 前50行 ===")
        for i, line in enumerate(lines[:50]):
            if line.startswith('event:'):
                print(f"{i}: [EVENT] {line}")
            elif line.startswith('data:'):
                data_preview = line[5:80] + "..." if len(line) > 80 else line[5:]
                print(f"{i}: [DATA] {data_preview}")
            else:
                print(f"{i}: {line[:80]}")

        # 查找 chunk 事件的数据
        print("\n=== 分析 chunk 数据块 ===")
        chunk_count = 0
        for i, line in enumerate(lines):
            if line.startswith('event: chunk'):
                print(f"行{i}: 发现 chunk 事件")
                # 找对应的数据行
                for j in range(i+1, min(i+10, len(lines))):
                    if lines[j].startswith('data:'):
                        data_content = lines[j][5:]
                        print(f"  数据行{j}: {repr(data_content[:100])}")
                        chunk_count += 1
                        if chunk_count >= 3:
                            break
                if chunk_count >= 3:
                    break

asyncio.run(test_sse_full())