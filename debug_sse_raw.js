// 调试 SSE 流式输出 - 直接检查原始数据
const http = require('http');

const postData = JSON.stringify({
  query: '广告',
  session_id: ''
});

const options = {
  hostname: 'localhost',
  port: 8081,
  path: '/api/v1/analysis/stream',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(postData),
    'Accept': 'text/event-stream'
  }
};

const req = http.request(options, (res) => {
  let data = '';

  res.on('data', (chunk) => {
    data += chunk.toString();

    // 每收到一个 chunk 就打印
    const lines = chunk.toString().split('\n');
    for (const line of lines) {
      if (line.startsWith('data:')) {
        console.log('RAW:', JSON.stringify(line));
      }
    }
  });

  res.on('end', () => {
    console.log('\n=== 完整数据前 2000 字符 ===');
    console.log(data.substring(0, 2000));
    console.log('\n=== 换行符数量:', (data.match(/\n/g) || []).length);
  });
});

req.on('error', (e) => {
  console.error('请求错误:', e.message);
});

req.write(postData);
req.end();
