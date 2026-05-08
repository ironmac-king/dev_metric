"""
Joint Intent + NER API Service
支持意图分类和实体抽取的Flask API
"""

from flask import Flask, request, jsonify
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inference_service import JointInferenceService
from config import INTENTS

app = Flask(__name__)

# 全局推理服务实例
service = None


def init_service():
    """初始化推理服务"""
    global service
    print("Initializing Joint Intent + NER service...")
    service = JointInferenceService(model_path="best_model/joint_v2")
    print("Service initialized successfully!")


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'model': 'joint_intent_ner',
        'intents': len(INTENTS)
    })


@app.route('/recognize', methods=['POST'])
def recognize_intent():
    """
    联合意图识别 + 实体抽取

    请求参数:
    {
        "text": "今日亚马逊销售额是多少",
        "top_k": 3,
        "include_entities": true
    }

    响应:
    {
        "success": true,
        "data": {
            "text": "今日亚马逊销售额是多少",
            "intent": "query_value",
            "confidence": 0.95,
            "top_intents": [...],
            "entities": [
                {"text": "今日", "type": "TIME", "start": 0, "end": 2},
                {"text": "亚马逊", "type": "PLATFORM", "start": 2, "end": 5},
                {"text": "销售额", "type": "METRIC", "start": 5, "end": 8}
            ]
        }
    }
    """
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({'error': 'Missing text parameter'}), 400

        text = data['text']
        top_k = data.get('top_k', 3)
        include_entities = data.get('include_entities', True)

        result = service.predict(text, top_k=top_k, use_ner=include_entities)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/batch_recognize', methods=['POST'])
def batch_recognize():
    """
    批量联合识别

    请求参数:
    {
        "texts": ["今日销售额", "本月GMV"],
        "top_k": 3
    }
    """
    try:
        data = request.get_json()

        if not data or 'texts' not in data:
            return jsonify({'error': 'Missing texts parameter'}), 400

        texts = data['texts']
        top_k = data.get('top_k', 3)

        results = service.batch_predict(texts, top_k=top_k)

        return jsonify({
            'success': True,
            'data': results
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/intent_list', methods=['GET'])
def get_intent_list():
    """获取意图列表"""
    intent_names = {
        'query_value': '查询指标数值',
        'query_trend': '查询趋势变化',
        'query_comparison': '对比分析',
        'query_ranking': '排名分析',
        'query_ratio': '占比分析',
        'query_aggregate': '聚合统计',
        'query_filter': '筛选过滤',
        'query_forecast': '预测分析',
        'query_drilldown': '下钻/上卷分析',
        'query_anomaly': '异常检测',
        'query_explain': '归因/解释分析',
        'query_target': '目标达成分析'
    }

    return jsonify({
        'success': True,
        'intents': [
            {'id': intent, 'name': intent_names.get(intent, intent)}
            for intent in INTENTS
        ]
    })


@app.route('/entity_types', methods=['GET'])
def get_entity_types():
    """获取实体类型列表"""
    entity_types = {
        'METRIC': '指标（如销售额、GMV）',
        'TIME': '时间表达式（如今日、本月）',
        'PLATFORM': '平台（如Amazon、eBay）',
        'DIM': '维度类型（如店铺、国家）',
        'DIM_VALUE': '维度值（如美国站、深圳）',
        'FULFILL': '履约类型（FBA、FBM）',
        'SKU_VALUE': 'SKU编码（如SKU-12345）'
    }

    return jsonify({
        'success': True,
        'entity_types': [
            {'id': etype, 'name': ename}
            for etype, ename in entity_types.items()
        ]
    })


@app.route('/reload_dicts', methods=['POST'])
def reload_dicts():
    """重新加载词典（metrics、business_terms、dim_values等），修改数据库后调用此接口生效"""
    try:
        service._build_rule_dict()
        return jsonify({'success': True, 'message': '词典已重新加载'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    init_service()

    print("\n" + "="*60)
    print("跨境电商意图识别 + 实体抽取 API 服务")
    print("="*60)
    print("API地址: http://localhost:5000")
    print("\n接口说明:")
    print("  GET  /health           - 健康检查")
    print("  POST /recognize        - 联合识别（intent + entities）")
    print("  POST /batch_recognize  - 批量联合识别")
    print("  GET  /intent_list      - 获取意图列表")
    print("  GET  /entity_types     - 获取实体类型列表")
    print("  POST /reload_dicts     - 重新加载词典（修改business_terms等后用）")
    print("="*60)
    print("\n调用示例:")
    print("  curl -X POST http://localhost:5000/recognize \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"text\": \"亚马逊美国站销售额是多少\", \"top_k\": 3}'")
    print("="*60)

    app.run(host='0.0.0.0', port=18082, debug=False, threaded=False)
