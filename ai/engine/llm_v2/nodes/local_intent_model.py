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
from ai.config.runtime import get_go_api_base
from ai.services.dimension_service import DimensionService

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
    '本季度', '上季度', '本年', '去年', '今年',
    '近7天', '近30天', '近3个月', '最近一周', '最近7天',
    '2024年1月', '2023年Q4',
    '本月至今', '本年至今', '今日实时',
    # 季度表达式
    'Q1', 'Q2', 'Q3', 'Q4',
    '一季度', '二季度', '三季度', '四季度',
    '本季度初', '上季度末',
]

# ============== SKU 格式 ==============

SKU_PATTERN = re.compile(r'\w+-\d+')
# ASIN: Amazon Standard Identification Number, 10位字母数字, 通常以B0开头
ASIN_PATTERN = re.compile(r'(?<![A-Z0-9])[A-Z0-9]{10}(?![A-Z0-9])', re.IGNORECASE)


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

    # 置信度阈值（降低到0.5，让中等置信度的预测也能通过，走本地模型结果）
    # 注意：本地模型预测 intent=query_value + METRIC实体已经足够可靠
    # 之前 0.85 过高，导致几乎所有 query 都走 LLM fallback，而 LLM fallback 经常失败
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, model_path: str = "D:/py/test/intent_trainer/best_model/joint_v2"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"[LocalJointIntentModel] 使用设备: {self.device}")

        self.model_path = model_path
        self._load_model()
        self._build_rule_dict()  # 构建规则词典

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

                # 解码 NER（传入原始 question 用于规则纠偏）
                entities = self._decode_ner(inputs, ner_preds, question)

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

    def _decode_ner(self, inputs, ner_preds, original_text: str = None) -> List[Dict[str, Any]]:
        """解码 NER 预测结果"""
        entities = []

        # 获取 offset_mapping，将 token 索引映射到字符偏移
        offset_mapping = inputs.get('offset_mapping')
        if offset_mapping is not None:
            offset_mapping = offset_mapping[0].cpu().numpy()
        else:
            # 重新 tokenize 获取 offset_mapping
            inputs_for_offset = self.tokenizer(
                original_text,
                max_length=128,
                padding='max_length',
                truncation=True,
                return_offsets_mapping=True,
                return_tensors='pt'
            )
            offset_mapping = inputs_for_offset['offset_mapping'][0].cpu().numpy()

        tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
        current_entity = None
        entity_start_char = None

        for i, (token, pred_id) in enumerate(zip(tokens, ner_preds)):
            if i == 0:  # Skip [CLS]
                continue
            if i >= 128 - 1:  # Skip [SEP] and padding
                break
            if offset_mapping is not None:
                start_char, end_char = offset_mapping[i]
                if start_char == end_char == 0:  # Skip special tokens
                    continue

            tag = self.id2tag.get(pred_id, 'O')

            if tag.startswith('B-'):
                # 保存前一个实体
                if current_entity and entity_start_char is not None:
                    char_end = last_char_end
                    entity_text = original_text[entity_start_char:char_end] if original_text else self._convert_tokens_to_string(tokens[entity_start_char:i])
                    if entity_text:
                        entities.append({
                            'text': entity_text,
                            'type': current_entity,
                            'start': entity_start_char,
                            'end': char_end
                        })
                # 开始新实体
                current_entity = tag[2:]
                entity_start_char = start_char
                last_char_end = end_char

            elif tag.startswith('I-') and current_entity:
                if tag[2:] != current_entity:
                    # I-标签与当前 B-标签不匹配，重新开始
                    if current_entity and entity_start_char is not None:
                        char_end = last_char_end
                        entity_text = original_text[entity_start_char:char_end] if original_text else self._convert_tokens_to_string(tokens[entity_start_char:i])
                        if entity_text:
                            entities.append({
                                'text': entity_text,
                                'type': current_entity,
                                'start': entity_start_char,
                                'end': char_end
                            })
                    current_entity = tag[2:]
                    entity_start_char = start_char
                    last_char_end = end_char
                else:
                    # 继续当前实体，更新 last_char_end
                    last_char_end = end_char

            else:
                # O标签，保存当前实体
                if current_entity and entity_start_char is not None:
                    char_end = last_char_end
                    entity_text = original_text[entity_start_char:char_end] if original_text else self._convert_tokens_to_string(tokens[entity_start_char:i])
                    if entity_text:
                        entities.append({
                            'text': entity_text,
                            'type': current_entity,
                            'start': entity_start_char,
                            'end': char_end
                        })
                current_entity = None
                entity_start_char = None
                last_char_end = None

        # 处理最后一个实体
        if current_entity and entity_start_char is not None:
            if offset_mapping is not None and len(offset_mapping) > i:
                char_end = offset_mapping[i][1]
            else:
                char_end = len(original_text) if original_text else len(tokens)
            entity_text = original_text[entity_start_char:char_end] if original_text else self._convert_tokens_to_string(tokens[entity_start_char:])
            if entity_text:
                entities.append({
                    'text': entity_text,
                    'type': current_entity,
                    'start': entity_start_char,
                    'end': char_end
                })

        # 规则补充：提取 SKU
        for match in SKU_PATTERN.finditer(original_text):
            entities.append({
                'text': match.group(),
                'type': 'SKU_VALUE',
                'start': match.start(),
                'end': match.end()
            })

        # 规则补充：提取 ASIN (10位字母数字, 通常B0开头)
        # 直接用原始 question 匹配，避免 tokenizer decode 改变大小写
        for match in ASIN_PATTERN.finditer(original_text):
            asin_val = match.group().upper()
            # 跳过纯数字的（避免匹配时间等）
            if asin_val.isdigit():
                continue
            # 跳过已识别为SKU的
            if any(e['text'] == asin_val and e['type'] == 'SKU_VALUE' for e in entities):
                continue
            entities.append({
                'text': asin_val,
                'type': 'ASIN_VALUE',
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

        # 规则纠偏：用词典匹配修正实体边界（使用原始文本）
        text = original_text if original_text else self.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=True)
        unique_entities = self._rule_based_correct(text, unique_entities)

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

    def _build_rule_dict(self):
        """构建规则匹配的词典（从业务术语表加载同义词等）"""
        self.rule_entities = {'TIME': set(TIME_EXPRESSIONS), 'METRIC': set(), 'DIM': set(), 'DIM_VALUE': set(), 'PLATFORM': set(), 'FULFILL': set()}

        # 常见指标作为兜底
        common_metrics = ['销售额', 'GMV', '销量', '收入', '利润', '成本', 'ACOS', 'ROAS', 'CPC', 'CTR', '曝光量', '点击量', '会话量', '订单量', '转化率', '客单价', '毛利率', '净利率', '业绩', '利润额']
        for m in common_metrics:
            self.rule_entities['METRIC'].add(m)

        # 尝试从 Go API 加载业务术语同义词
        try:
            import httpx
            response = httpx.get(f"{get_go_api_base()}/api/v1/metadata/terms", timeout=5)
            if response.status_code == 200:
                terms = response.json().get('data', [])
                for term_info in terms:
                    term = term_info.get('term', '')
                    synonyms = term_info.get('synonyms', '')
                    dim_field = term_info.get('dimension_field', '')  # 维度字段名，非空则表示是维度类型
                    if not term:
                        continue

                    # 解析同义词列表
                    def parse_synonyms(syns):
                        if isinstance(syns, list):
                            return [s.strip() for s in syns if s and len(s.strip()) >= 2]
                        elif isinstance(syns, str):
                            return [s.strip() for s in syns.split(',') if s.strip() and len(s.strip()) >= 2]
                        return []

                    syn_list = parse_synonyms(synonyms)

                    if dim_field and dim_field.strip():
                        # 有 dimension_field → 该 term 是维度字段，主词入 DIM，同义词入 DIM_VALUE
                        if len(term) >= 2:
                            self.rule_entities['DIM'].add(term)
                        for s in syn_list:
                            if s != term:
                                self.rule_entities['DIM_VALUE'].add(s)
                    else:
                        # 无 dimension_field → 作为指标处理
                        if term not in self.rule_entities['METRIC']:
                            self.rule_entities['METRIC'].add(term)
                        for s in syn_list:
                            if s not in self.rule_entities['METRIC']:
                                self.rule_entities['METRIC'].add(s)
                logger.info(f"[LocalJointIntentModel] 从 API 加载了 {len(terms)} 个业务术语")
        except Exception as e:
            logger.warning(f"[LocalJointIntentModel] 加载业务术语失败: {e}")

        # 尝试从 Go API 加载维度值（遍历所有 column_name）
        try:
            dim_service = DimensionService()
            # 先获取所有 column_name + dimension_type 对
            all_types = dim_service.get_all_types(use_cache=True)
            total_values = 0
            for type_info in all_types:
                column_name = type_info.get('column_name', '')
                if not column_name:
                    continue
                # 跳过空 dimension_value 的记录
                values = dim_service.get_by_column_name(column_name, use_cache=True)
                for item in values:
                    val = item.get('dimension_value', '')
                    if val and len(val) >= 2:
                        self.rule_entities['DIM_VALUE'].add(val)
                total_values += len(values)
            logger.info(f"[LocalJointIntentModel] 从 {len(all_types)} 个列加载了 {total_values} 个维度值")
        except Exception as e:
            logger.warning(f"[LocalJointIntentModel] 加载维度值失败: {e}")

        # 平台和履约类型
        platform_fulfill = {
            'PLATFORM': ['Amazon', '亚马逊', 'eBay', 'EBay', 'AliExpress', '速卖通', 'Wish', 'Shopee', '虾皮', 'Lazada', 'MercadoLibre'],
            'FULFILL': ['FBA', 'FBM', 'MFN', 'SFP']
        }
        for etype, values in platform_fulfill.items():
            for v in values:
                self.rule_entities[etype].add(v)

        logger.info(f"[LocalJointIntentModel] 规则词典: METRIC={len(self.rule_entities['METRIC'])}, DIM_VALUE={len(self.rule_entities['DIM_VALUE'])}, TIME={len(self.rule_entities['TIME'])}")

    def _rule_based_correct(self, text: str, model_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        用规则词典修正实体边界
        1. 主动在文本中查找所有词典条目
        2. 与模型预测合并，优先使用词典匹配
        """
        model_set = set()
        for e in model_entities:
            model_set.add((e['text'], e['type'], e['start'], e['end']))

        # 主动匹配：遍历词典，在文本中查找
        rule_matches = []
        for etype, dict_values in self.rule_entities.items():
            for val in dict_values:
                start = 0
                while True:
                    pos = text.find(val, start)
                    if pos < 0:
                        break
                    rule_matches.append({
                        'text': val,
                        'type': etype,
                        'start': pos,
                        'end': pos + len(val)
                    })
                    start = pos + 1

        # 正则匹配：补充识别 \d{4}年 系列（本地模型未训练的时间表达式）
        year_patterns = [
            (r'(\d{4})年(\d{1,2})月', 'TIME'),  # 2024年7月
            (r'(\d{4})年', 'TIME'),              # 2025年
        ]
        for pattern, etype in year_patterns:
            for match in re.finditer(pattern, text):
                rule_matches.append({
                    'text': match.group(0),
                    'type': etype,
                    'start': match.start(),
                    'end': match.end()
                })

        # 合并：词典匹配优先，模型预测补充
        all_entities = []
        covered_ranges = []

        # 先加入词典匹配（更长更准确）
        for rm in sorted(rule_matches, key=lambda x: -len(x['text'])):
            all_entities.append(rm)
            covered_ranges.append((rm['start'], rm['end']))

        # 补充模型预测中与词典不重叠的实体
        for e in model_entities:
            overlaps = False
            for c_start, c_end in covered_ranges:
                if not (e['end'] <= c_start or e['start'] >= c_end):
                    overlaps = True
                    break
            if not overlaps:
                all_entities.append(e)
                covered_ranges.append((e['start'], e['end']))

        # 按 start 排序
        all_entities.sort(key=lambda x: (x['start'], -x['end']))

        # 去重 + 类型优先级：DIM > METRIC > DIM_VALUE > TIME > PLATFORM > FULFILL
        type_priority = {'DIM': 0, 'METRIC': 2, 'DIM_VALUE': 1, 'TIME': 3, 'PLATFORM': 4, 'FULFILL': 5, 'SKU_VALUE': 6, 'ASIN_VALUE': 7}
        seen = set()
        final = []
        for e in all_entities:
            key = (e['start'], e['end'])
            if key not in seen:
                # 检查是否与已有实体重叠，重叠则按优先级决定是否替换
                replace_idx = None
                for i, f in enumerate(final):
                    if e['start'] < f['end'] and e['end'] > f['start']:
                        p1 = type_priority.get(e['type'], 99)
                        p2 = type_priority.get(f['type'], 99)
                        if p1 < p2:
                            replace_idx = i
                        break
                if replace_idx is not None:
                    final[replace_idx] = e
                else:
                    final.append(e)
                seen.add(key)
            else:
                pass  # 完全相同的 key 已跳过

        # 过滤太短的实体（长度 < 2）
        final = [e for e in final if len(e['text']) >= 2]

        return final


# ============== 单例模式 ==============

_instance: Optional[LocalJointIntentModel] = None


def get_local_intent_model(model_path: str = None) -> LocalJointIntentModel:
    """获取本地意图识别模型单例"""
    global _instance

    if _instance is None:
        if model_path is None:
            # 从配置读取
            model_path = "D:/py/test/intent_trainer/best_model/joint_v2"
        _instance = LocalJointIntentModel(model_path=model_path)

    return _instance
