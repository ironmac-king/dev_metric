"""
本地 Joint BERT 意图识别模型封装

职责：
- 封装本地 Joint BERT 模型调用
- 实现意图类型映射（本地 → MQLSchema）
- 实现实体类型映射（BIO → MQLSchema）
- 提供精准匹配判断（置信度 + 实体完整性）
"""

import os
import json
import re
import torch
import numpy as np
from typing import Dict, Any, Optional, List
from transformers import AutoTokenizer, AutoModel

from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.local_intent_model")

# ============== 意图类型映射 ==============

LOCAL_TO_MQL_INTENT = {
    "query_value": "query_value",
    "query_trend": "query_trend",
    "query_comparison": "query_comparison",
    "query_ranking": "query_ranking",
    "query_ratio": "query_ratio",
    "query_aggregate": "query_aggregate",
    "query_filter": "query_value",  # query_filter → query_value（带维度过滤的查值）
    "query_forecast": "query_forecast",
    "query_drilldown": "query_drilldown",
    "query_anomaly": "query_anomaly",
    "query_explain": "query_metadata",  # 本地 query_explain → MQL query_metadata
    "query_target": "query_target",
}

# ============== BIO 标签定义 ==============

BIO_TAGS = ['O', 'B-METRIC', 'I-METRIC', 'B-TIME', 'I-TIME',
            'B-DIM', 'I-DIM', 'B-DIM_VALUE', 'I-DIM_VALUE']

TAG2ID = {tag: i for i, tag in enumerate(BIO_TAGS)}
ID2TAG = {i: tag for i, tag in enumerate(BIO_TAGS)}

# ============== 时间表达式词典 ==============

TIME_EXPRESSIONS = [
    '今日', '昨日', '本周', '上周', '本月', '上月',
    '本季度', '上季度', '本年', '去年',
    '近7天', '近30天', '近3个月',
    '2024年1月', '2023年Q4',
    '本月至今', '本年至今', '今日实时'
]

# ============== SKU 格式 ==============

SKU_PATTERN = re.compile(r'\w+-\d+')


class JointBERTModel(torch.nn.Module):
    """Joint BERT 模型定义"""

    def __init__(self, model_name: str, num_intents: int, num_ner_tags: int, dropout: float = 0.1):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name, local_files_only=True)
        self.hidden_size = self.bert.config.hidden_size

        self.intent_dropout = torch.nn.Dropout(dropout)
        self.intent_classifier = torch.nn.Linear(self.hidden_size, num_intents)

        self.ner_dropout = torch.nn.Dropout(dropout)
        self.ner_classifier = torch.nn.Linear(self.hidden_size, num_ner_tags)

    def forward(self, input_ids, attention_mask, token_type_ids=None):
        # token_type_ids 可能为 None，忽略它
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        sequence_output = outputs.last_hidden_state
        pooled_output = outputs.pooler_output

        intent_logits = self.intent_classifier(self.intent_dropout(pooled_output))
        ner_logits = self.ner_classifier(self.ner_dropout(sequence_output))

        return {
            'intent_logits': intent_logits,
            'ner_logits': ner_logits
        }


class LocalJointIntentModel:
    """
    本地 Joint BERT 意图识别模型封装

    使用本地模型做意图识别 + NER，匹配成功则跳过 LLM。
    """

    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.85

    def __init__(self, model_path: str = "D:/py/test/intent_trainer/best_model/joint"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"[LocalJointIntentModel] 使用设备: {self.device}")

        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        """加载模型、tokenizer、标签映射"""
        try:
            # 加载标签映射
            tag_mapping_path = os.path.join(self.model_path, "tag_mapping.json")
            if os.path.exists(tag_mapping_path):
                with open(tag_mapping_path, 'r', encoding='utf-8') as f:
                    tag_mapping = json.load(f)
                self.intents = tag_mapping['intents']
                self.id2intent = {int(k): v for k, v in tag_mapping['id2intent'].items()}
                self.id2tag = {int(k): v for k, v in tag_mapping['id2tag'].items()}
                logger.info(f"[LocalJointIntentModel] 加载标签映射: {len(self.intents)} 个意图, {len(self.id2tag)} 个 NER 标签")
            else:
                raise FileNotFoundError(f"tag_mapping.json 不存在于 {self.model_path}")

            # 加载 tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)

            # 创建模型
            self.model = JointBERTModel(
                model_name=self.model_path,
                num_intents=len(self.intents),
                num_ner_tags=len(self.id2tag)
            )

            # 加载模型权重
            pytorch_bin_path = os.path.join(self.model_path, "pytorch_model.bin")
            if os.path.exists(pytorch_bin_path):
                state_dict = torch.load(pytorch_bin_path, map_location=self.device, weights_only=True)
                self.model.load_state_dict(state_dict)
                logger.info(f"[LocalJointIntentModel] 加载 pytorch_model.bin 成功")
            else:
                # 回退到 safetensors
                from safetensors.torch import load_file
                safetensors_path = os.path.join(self.model_path, "model.safetensors")
                if os.path.exists(safetensors_path):
                    state_dict = load_file(safetensors_path, device=str(self.device))
                    # 添加 bert. 前缀
                    new_state_dict = {}
                    for k, v in state_dict.items():
                        if not k.startswith('bert.'):
                            new_state_dict['bert.' + k] = v
                        else:
                            new_state_dict[k] = v
                    self.model.load_state_dict(new_state_dict, strict=False)
                    logger.info(f"[LocalJointIntentModel] 加载 model.safetensors 成功")

            self.model.to(self.device)
            self.model.eval()
            logger.info(f"[LocalJointIntentModel] 模型加载成功")

        except Exception as e:
            logger.error(f"[LocalJointIntentModel] 模型加载失败: {e}")
            raise

    def predict(self, question: str) -> Dict[str, Any]:
        """
        预测意图和实体

        Args:
            question: 用户问题

        Returns:
            {
                'intent': 'query_value',
                'confidence': 0.92,
                'entities': [{'text': '销售额', 'type': 'METRIC'}, ...],
                'match_success': True/False
            }
        """
        if not question or not question.strip():
            return {
                'intent': 'unknown',
                'confidence': 0.0,
                'entities': [],
                'match_success': False
            }

        try:
            # Tokenize
            inputs = self.tokenizer(
                question,
                max_length=128,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

                # Intent prediction
                intent_probs = torch.softmax(outputs['intent_logits'], dim=1)
                intent_pred_idx = torch.argmax(intent_probs, dim=1).item()
                intent_confidence = intent_probs[0][intent_pred_idx].item()

                # NER prediction
                ner_probs = torch.softmax(outputs['ner_logits'], dim=2)
                ner_preds = torch.argmax(ner_probs, dim=2)[0].cpu().numpy()

                # 解码 NER
                entities = self._decode_ner(inputs, ner_preds)

                # 意图映射
                local_intent = self.id2intent.get(intent_pred_idx, self.intents[intent_pred_idx])
                mapped_intent = LOCAL_TO_MQL_INTENT.get(local_intent, local_intent)

                # 判断是否匹配成功（intent=unknown 时必须走 LLM）
                match_success = self._check_match_success(intent_confidence, entities, mapped_intent)

                result = {
                    'intent': mapped_intent,
                    'confidence': intent_confidence,
                    'local_intent': local_intent,  # 原始本地意图
                    'entities': entities,
                    'match_success': match_success,
                    'local_only': True  # 标记为本地模型结果
                }

                logger.info(f"[LocalJointIntentModel] 预测: intent={mapped_intent}, confidence={intent_confidence:.3f}, "
                           f"entities={len(entities)}, match_success={match_success}")

                return result

        except Exception as e:
            logger.error(f"[LocalJointIntentModel] 预测失败: {e}")
            return {
                'intent': 'unknown',
                'confidence': 0.0,
                'entities': [],
                'match_success': False,
                'error': str(e)
            }

    def _decode_ner(self, inputs, ner_preds) -> List[Dict[str, Any]]:
        """解码 NER 预测结果"""
        entities = []

        tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
        current_entity = None
        entity_start = None

        for i, (token, pred_id) in enumerate(zip(tokens, ner_preds)):
            if i == 0:  # Skip [CLS]
                continue
            if i >= 128 - 1:  # Skip [SEP] and padding
                break

            tag = self.id2tag.get(pred_id, 'O')

            if tag.startswith('B-'):
                # 保存前一个实体
                if current_entity:
                    entity_text = self._convert_tokens_to_string(tokens[entity_start:i])
                    if entity_text:
                        entities.append({
                            'text': entity_text,
                            'type': current_entity,
                            'start': entity_start,
                            'end': i
                        })
                # 开始新实体
                current_entity = tag[2:]
                entity_start = i

            elif tag.startswith('I-') and current_entity:
                if tag[2:] != current_entity:
                    # I-标签与当前 B-标签不匹配，重新开始
                    if current_entity:
                        entity_text = self._convert_tokens_to_string(tokens[entity_start:i])
                        if entity_text:
                            entities.append({
                                'text': entity_text,
                                'type': current_entity,
                                'start': entity_start,
                                'end': i
                            })
                    current_entity = tag[2:]
                    entity_start = i
                # 否则继续实体

            else:
                # O标签，保存当前实体
                if current_entity:
                    entity_text = self._convert_tokens_to_string(tokens[entity_start:i])
                    if entity_text:
                        entities.append({
                            'text': entity_text,
                            'type': current_entity,
                            'start': entity_start,
                            'end': i
                        })
                current_entity = None
                entity_start = None

        # 处理最后一个实体
        if current_entity:
            entity_text = self._convert_tokens_to_string(tokens[entity_start:])
            if entity_text:
                entities.append({
                    'text': entity_text,
                    'type': current_entity,
                    'start': entity_start,
                    'end': len(tokens)
                })

        # 规则补充：提取 SKU
        text = self.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=True)
        for match in SKU_PATTERN.finditer(text):
            entities.append({
                'text': match.group(),
                'type': 'SKU_VALUE',
                'start': match.start(),
                'end': match.end()
            })

        # 按 start 排序
        entities.sort(key=lambda x: x['start'])

        # 去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e['text'], e['type'])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        return unique_entities

    def _convert_tokens_to_string(self, tokens: List[str]) -> str:
        """将 tokens 转换为字符串"""
        # 移除 [CLS], [SEP], [PAD]
        clean_tokens = [t for t in tokens if t not in ['[CLS]', '[SEP]', '[PAD]']]
        if not clean_tokens:
            return ""

        # 处理 subword
        result = []
        for token in clean_tokens:
            if token.startswith('##'):
                result.append(token[2:])
            elif token.startswith('▁'):
                result.append(token[1:])
            else:
                if result:
                    result.append(token)
                else:
                    result.append(token)

        return ''.join(result).strip()

    def _check_match_success(self, confidence: float, entities: List[Dict[str, Any]], intent: str = None) -> bool:
        """
        判断本地模型匹配是否成功

        条件：
        1. 置信度 >= 0.85
        2. 识别到 METRIC 实体（指标必须识别到）
        3. 意图不能是 unknown（unknown 必须走 LLM）
        """
        # 条件0：意图不能是 unknown
        if intent == "unknown":
            return False

        # 条件1：置信度阈值
        if confidence < self.CONFIDENCE_THRESHOLD:
            return False

        # 条件2：必须有 METRIC 实体
        has_metric = any(e['type'] == 'METRIC' for e in entities)
        if not has_metric:
            return False

        return True


# ============== 单例模式 ==============

_instance: Optional[LocalJointIntentModel] = None


def get_local_intent_model(model_path: str = None) -> LocalJointIntentModel:
    """获取本地意图识别模型单例"""
    global _instance

    if _instance is None:
        if model_path is None:
            # 从配置读取
            model_path = "D:/py/test/intent_trainer/best_model/joint"
        _instance = LocalJointIntentModel(model_path=model_path)

    return _instance
