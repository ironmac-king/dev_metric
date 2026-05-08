"""
Joint Intent + NER Inference Service
支持意图分类和实体抽取的联合推理服务
"""

import os
import re
import sys
import json
import pymysql
import psycopg2
import numpy as np
import torch
from collections import defaultdict
from transformers import AutoTokenizer, AutoModel
import torch.nn as nn
from joint_trainer import JointBERTModel

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MODEL_NAME, MAX_LEN, DB_CONFIG, INTENTS, TIME_EXPRESSIONS

# ============== 语义映射表 ==============

SEMANTIC_MAPPINGS = {
    # 销售额/营收
    '销售额': {
        '卖的最好': '销售额最高', '最热销': '销售额最高', '热卖': '销售额最高',
        '爆款': '销售额最高', '热销款': '销售额最高', '业绩最高': '销售额最高',
        '卖的最火': '销售额最高', '最受欢迎': '销售额最高',
        '卖的最差': '销售额最低', '滞销': '销售额最低', '冷门': '销售额最低',
        '卖不动': '销售额最低', '业绩最差': '销售额最低',
        '业绩': '销售额', '营收': '销售额', '营业收入': '销售额',
        '总成交': '销售额', '总成交额': '销售额', '平台销售额': '销售额',
        'GMV': '销售额', '商品成交总额': '销售额',
        '收入': '销售额', '营业额': '销售额',
    },
    # 销量
    '销量': {
        '订单量': '销量', '订单数': '销量', '下单量': '销量',
        '成交笔数': '销量', '交易笔数': '销量', '卖出多少': '销量',
        '销售数量': '销量', '销售件数': '销量', '件数': '销量',
        '售出数量': '销量', '成交数量': '销量',
    },
    # 利润
    '利润': {
        '净利润': '利润', '净利': '利润', '纯利润': '利润',
        '盈利': '利润', '赚了多少': '利润', '赚了': '利润',
        '亏损': '亏损', '亏了多少': '亏损', '亏了': '亏损',
        '税前利润': '利润', '税后利润': '利润',
    },
    # 成本
    '成本': {
        '花费': '成本', '花费多少': '成本', '费用': '成本',
        '支出': '成本', '支出多少': '成本',
    },
    # 增长
    '增长': {
        '涨了': '增长', '上升了': '增长', '增加了': '增长', '上涨': '增长',
        '增长了多少': '增长', '涨了多少': '增长', '上升多少': '增长',
        '增长了吗': '增长', '上涨了吗': '增长',
    },
    # 下降
    '下降': {
        '跌了': '下降', '下滑了': '下降', '下降了': '下降', '下跌': '下降',
        '跌了多少': '下降', '下滑多少': '下降', '下降多少': '下降',
        '跌了吗': '下降', '下滑了吗': '下降',
    },
    # 占比
    '占比': {
        '比例': '占比', '占比多少': '占比', '比率': '占比',
        '占比情况': '占比', '比例情况': '占比',
    },
    # 排名
    '排名': {
        '排行': '排名', '排行榜': '排名', '排名情况': '排名',
        '排第几': '排名', '排第几了': '排名',
    },
    # 趋势
    '趋势': {
        '趋势如何': '趋势', '走势': '趋势', '走向': '趋势',
        '趋势怎么样': '趋势', '近来趋势': '趋势',
    },
    # 平均
    '平均': {
        '平均值': '平均', '平均数': '平均', '均值': '平均',
        '日均': '平均', '月均': '平均', '年均': '平均',
    },
    # 汇总
    '汇总': {
        '合计': '汇总', '总计': '汇总', '总和': '汇总',
        '加起来': '汇总', '加起来': '汇总', '总共': '汇总',
    },
    # 目标达成
    '目标达成': {
        '完成率': '目标达成', '达标': '目标达成', '目标完成': '目标达成',
        '达成情况': '目标达成', '完成情况': '目标达成',
        '目标差距': '目标达成', '还差多少': '目标达成',
    },
}

SKU_PATTERN = re.compile(r'\w+-\d+')


class JointInferenceService:
    """联合意图识别+实体抽取服务"""

    def __init__(self, model_path="best_model/joint"):
        print(f"Initializing Joint Intent + NER service...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        # 加载tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

        # 加载tag映射
        with open(os.path.join(model_path, "tag_mapping.json"), 'r', encoding='utf-8') as f:
            tag_mapping = json.load(f)
            self.id2tag = tag_mapping['id2tag']
            self.id2intent = tag_mapping['id2intent']
            num_intents = len(tag_mapping['intents'])
            num_ner_tags = len(tag_mapping['bio_tags'])

        # 加载模型 - 使用原始预训练模型加载BERT，然后加载训练好的state dict
        state_dict_path = os.path.join(model_path, "pytorch_model.bin")
        self.model = JointBERTModel(
            model_name=MODEL_NAME,
            num_intents=num_intents,
            num_ner_tags=num_ner_tags,
            state_dict_path=state_dict_path
        )
        self.model.to(self.device)
        self.model.eval()

        # 加载数据库词典
        self.metrics = self._load_postgres_metrics()
        self.dim_values = self._load_starrocks_dim_values()

        # 构建规则词典
        self._build_rule_dict()

        print("Service initialized successfully!")

    def _load_postgres_metrics(self):
        """从PostgreSQL加载指标名"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM metrics WHERE status = '在用'")
            metrics = [row[0] for row in cursor.fetchall() if row[0]]
            conn.close()
            print(f"[Metrics] Loaded {len(metrics)} metrics from PostgreSQL")
            return metrics
        except Exception as e:
            print(f"[WARN] Failed to load PostgreSQL metrics: {e}")
            return ['销售额', 'GMV', 'ACOS', '曝光量', '会话量']  # fallback

    def _load_starrocks_dim_values(self):
        """从StarRocks加载维度值（排除SKU）"""
        try:
            conn = pymysql.connect(
                host='192.168.1.178',
                port=9030,
                user='ugreenbireadonly',
                password='ugreenbireadonly_new2026!',
                database='ids',
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dimension_field, dimension_value
                FROM dim_value_mapping
                WHERE dimension_field NOT LIKE '%sku%'
                AND dimension_field NOT LIKE '%SKU%'
            """)
            results = cursor.fetchall()
            conn.close()

            # 按dimension_field分组
            dim_values_by_type = defaultdict(list)
            for field, value in results:
                if field and value:
                    dim_values_by_type[field].append(value)

            total = sum(len(v) for v in dim_values_by_type.values())
            print(f"[DimValues] Loaded {total} dimension values from StarRocks (excluding SKU)")
            return dim_values_by_type
        except Exception as e:
            print(f"[WARN] Failed to load StarRocks dim values: {e}")
            return {}

    def _build_rule_dict(self):
        """构建规则匹配的词典"""
        self.rule_entities = {'TIME': set(TIME_EXPRESSIONS), 'METRIC': set(), 'DIM': set(), 'DIM_VALUE': set(), 'PLATFORM': set(), 'FULFILL': set()}

        # METRIC: 从PostgreSQL加载的指标名
        for m in self.metrics:
            if m:
                self.rule_entities['METRIC'].add(m)

        # 同义词→标准词的映射，用于规范化输出
        self.synonym_to_std = {}

        # 从 business_terms 表加载同义词，分别加入 METRIC 和 DIM_VALUE
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute("SELECT term, synonyms, dimension_field FROM business_terms")
            results = cursor.fetchall()
            conn.close()

            for term, synonyms, dimension_field in results:
                if not term or not synonyms:
                    continue
                # 判断 term 是否属于 METRIC 类型（term 在 metrics 中或已知指标中）
                is_metric = term in self.metrics or term in self.rule_entities['METRIC']
                # 判断是否为维度字段（dimension_field 非空）
                is_dim = dimension_field and str(dimension_field).strip()

                def _add_synonyms(syns, target_set):
                    if isinstance(syns, list):
                        for syn in syns:
                            if syn and len(syn) >= 2:
                                target_set.add(syn)
                                self.synonym_to_std[syn] = term
                    elif isinstance(syns, str):
                        for syn in syns.split(','):
                            syn = syn.strip()
                            if syn and len(syn) >= 2:
                                target_set.add(syn)
                                self.synonym_to_std[syn] = term

                if is_metric:
                    _add_synonyms(synonyms, self.rule_entities['METRIC'])
                if is_dim:
                    # 维度字段的主词（如"站点"）加入 DIM，其同义词加入 DIM_VALUE
                    if len(term) >= 2:
                        self.rule_entities['DIM'].add(term)
                    syns = synonyms if isinstance(synonyms, list) else [s.strip() for s in synonyms.split(',') if s.strip()]
                    dim_syns = [s for s in syns if s and s != term]
                    for s in dim_syns:
                        if len(s) >= 2:
                            self.rule_entities['DIM_VALUE'].add(s)
                            self.synonym_to_std[s] = term

            print(f"[Synonyms] METRIC dict size: {len(self.rule_entities['METRIC'])}, DIM_VALUE dict size: {len(self.rule_entities['DIM_VALUE'])}")
        except Exception as e:
            print(f"[WARN] Failed to load business terms synonyms: {e}")

        # 加载的平台和履约类型
        platform_fulfill = {
            'PLATFORM': ['Amazon', '亚马逊', 'eBay', 'EBay', 'AliExpress', '速卖通', 'Wish', 'Shopee', '虾皮', 'Lazada', 'MercadoLibre'],
            'FULFILL': ['FBA', 'FBM', 'MFN', 'SFP']
        }
        for etype, values in platform_fulfill.items():
            for v in values:
                self.rule_entities[etype].add(v)

        # DIM_VALUE: 从StarRocks加载的维度值
        for field, values in self.dim_values.items():
            for v in values:
                if v:
                    self.rule_entities['DIM_VALUE'].add(v)

        # 过滤太短的
        for etype in self.rule_entities:
            self.rule_entities[etype] = {v for v in self.rule_entities[etype] if len(v) >= 2}

        # 添加常见指标作为兜底
        common_metrics = ['销售额', 'GMV', '销量', '收入', '利润', '成本', 'ACOS', 'ROAS', 'CPC', 'CTR', '曝光量', '点击量', '会话量', '订单量', '转化率', '客单价', '毛利率', '净利率']
        for m in common_metrics:
            self.rule_entities['METRIC'].add(m)

        # 常见时间表达
        common_times = ['今日', '昨日', '本周', '上周', '本月', '上月', '本季度', '上季度', '本年', '去年', '今年', '近7天', '近30天', '近3个月']
        for t in common_times:
            self.rule_entities['TIME'].add(t)

        # 添加语义映射到 synonym_to_std，同时把语义key加入对应实体类型
        for std_term, synonyms in SEMANTIC_MAPPINGS.items():
            for syn_key, syn_value in synonyms.items():
                if syn_key and len(syn_key) >= 2:
                    self.synonym_to_std[syn_key] = syn_value
                    # 把语义key加入对应实体类型（用于匹配）
                    if std_term in ['销售额', '销量', '利润', '成本', '曝光量', '点击量', '访客数', '会话量', '转化率', '点击率', '客单价', '复购率', '广告花费']:
                        self.rule_entities['METRIC'].add(syn_key)
                    elif std_term in ['增长', '下降']:
                        self.rule_entities['METRIC'].add(syn_key)
                    elif std_term in ['占比', '排名', '趋势', '平均', '汇总', '目标达成', '同比', '环比', '预测', '归因', '异常']:
                        # 这些是意图/动作词，不单独作为实体
                        pass

    def _rule_based_correct(self, text, model_entities):
        """
        用规则词典修正实体边界
        1. 主动在文本中查找所有词典条目
        2. 与模型预测合并，优先使用词典匹配
        """
        # 先收集模型预测的实体（用集合快速去重）
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
                    start = pos + 1  # 继续找下一个

        # 合并：词典匹配优先，模型预测补充
        all_entities = []
        covered_ranges = []

        # 先加入词典匹配（更长更准确），同时检查重叠
        for rm in sorted(rule_matches, key=lambda x: -len(x['text'])):
            # 检查是否与已有实体重叠
            overlap = False
            for start, end in covered_ranges:
                if rm['start'] < end and rm['end'] > start:
                    overlap = True
                    break
            if not overlap:
                all_entities.append(rm)
                covered_ranges.append((rm['start'], rm['end']))

        # 补充模型预测中与词典不重叠的实体
        for e in model_entities:
            overlaps = False
            for start, end in covered_ranges:
                if e['start'] < end and e['end'] > start:
                    overlaps = True
                    break
            if not overlaps:
                all_entities.append(e)
                covered_ranges.append((e['start'], e['end']))

        # 按位置排序
        all_entities.sort(key=lambda x: (x['start'], -x['end']))

        # 去重：同位置只保留一个实体（规则词典优先于模型预测，类型优先 DIM > METRIC > DIM_VALUE > TIME > PLATFORM > FULFILL）
        type_priority = {'DIM': 0, 'METRIC': 2, 'DIM_VALUE': 1, 'TIME': 3, 'PLATFORM': 4, 'FULFILL': 5, 'SKU_VALUE': 6}
        final = []
        covered = set()  # (start, end)
        for e in all_entities:
            key = (e['start'], e['end'])
            if key not in covered:
                # 如果已有点重叠，用优先级决定
                replace_idx = None
                for i, f in enumerate(final):
                    if e['start'] < f['end'] and e['end'] > f['start']:
                        # 重叠了，比较优先级
                        p1 = type_priority.get(e['type'], 99)
                        p2 = type_priority.get(f['type'], 99)
                        if p1 < p2:
                            replace_idx = i
                        break
                if replace_idx is not None:
                    final[replace_idx] = e
                else:
                    final.append(e)
                covered.add(key)
            else:
                pass  # 已有点完全相同，跳过

        return final

    def extract_entities_rule_based(self, text):
        """基于规则的实体提取（用于补充模型预测）"""
        entities = []

        # SKU匹配
        for match in SKU_PATTERN.finditer(text):
            entities.append({
                'text': match.group(),
                'type': 'SKU_VALUE',
                'start': match.start(),
                'end': match.end()
            })

        return entities

    def predict(self, text, top_k=3, use_ner=True):
        """
        联合预测：意图分类 + 实体抽取

        Args:
            text: 输入文本
            top_k: 返回前k个意图
            use_ner: 是否进行NER抽取

        Returns:
            {
                'text': 原文本,
                'intent': 预测意图,
                'confidence': 置信度,
                'top_intents': [...],
                'entities': [{'text': '', 'type': '', 'start': 0, 'end': 0}, ...]
            }
        """
        self.model.eval()

        # Tokenize
        inputs = self.tokenizer(
            text,
            max_length=MAX_LEN,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        ).to(self.device)

        # 移除token_type_ids（如果存在），因为模型不接受这个参数
        # 移除模型不需要的参数
        inputs = {k: v for k, v in inputs.items() if k not in ['token_type_ids', 'offset_mapping']}

        with torch.no_grad():
            outputs = self.model(**inputs)

            # Intent prediction
            intent_probs = torch.softmax(outputs['intent_logits'], dim=1)
            intent_pred_idx = torch.argmax(intent_probs, dim=1).item()
            intent_confidence = intent_probs[0][intent_pred_idx].item()

            # Top-k intents
            top_k_intents = torch.topk(intent_probs, min(top_k, len(INTENTS)), dim=1)
            top_intents = []
            for idx, conf in zip(top_k_intents.indices[0], top_k_intents.values[0]):
                top_intents.append({
                    'intent': self.id2intent.get(idx.item(), INTENTS[idx.item()]),
                    'confidence': conf.item()
                })

            # NER prediction
            entities = []
            if use_ner:
                ner_probs = torch.softmax(outputs['ner_logits'], dim=2)
                ner_preds = torch.argmax(ner_probs, dim=2)[0].cpu().numpy()

                # 使用 offset_mapping 从原文中提取，避免 subword 碎片化
                offset_mapping = inputs.pop('offset_mapping', None)
                if offset_mapping is None:
                    # 重新 tokenize 获取 offset_mapping
                    inputs = self.tokenizer(
                        text,
                        max_length=MAX_LEN,
                        padding='max_length',
                        truncation=True,
                        return_offsets_mapping=True,
                        return_tensors='pt'
                    ).to(self.device)
                    inputs = {k: v for k, v in inputs.items() if k not in ['token_type_ids']}
                    offset_mapping = inputs['offset_mapping'][0].cpu().numpy()

                current_entity = None
                entity_start_char = None

                for i, (start_char, end_char) in enumerate(offset_mapping):
                    if i == 0:  # Skip [CLS]
                        continue
                    if i >= MAX_LEN - 1:  # Skip [SEP] and padding
                        break
                    if start_char == end_char == 0:  # Skip special tokens
                        continue

                    pred_id = ner_preds[i]
                    tag = self.id2tag.get(pred_id, 'O')

                    if tag.startswith('B-'):
                        # 保存前一个实体
                        if current_entity and entity_start_char is not None:
                            entity_text = text[entity_start_char:end_char].strip()
                            if entity_text:
                                entities.append({
                                    'text': entity_text,
                                    'type': current_entity,
                                    'start': entity_start_char,
                                    'end': end_char
                                })
                        current_entity = tag[2:]
                        entity_start_char = start_char
                    elif tag.startswith('I-') and current_entity:
                        if tag[2:] != current_entity:
                            # I-标签与当前B-标签不匹配
                            if entity_start_char is not None:
                                entity_text = text[entity_start_char:end_char].strip()
                                if entity_text:
                                    entities.append({
                                        'text': entity_text,
                                        'type': current_entity,
                                        'start': entity_start_char,
                                        'end': end_char
                                    })
                            current_entity = tag[2:]
                            entity_start_char = start_char
                    else:
                        # O标签
                        if current_entity and entity_start_char is not None:
                            entity_text = text[entity_start_char:end_char].strip()
                            if entity_text:
                                entities.append({
                                    'text': entity_text,
                                    'type': current_entity,
                                    'start': entity_start_char,
                                    'end': end_char
                                })
                        current_entity = None
                        entity_start_char = None

                # 处理最后一个实体
                if current_entity and entity_start_char is not None:
                    entity_text = text[entity_start_char:].strip()
                    if entity_text:
                        entities.append({
                            'text': entity_text,
                            'type': current_entity,
                            'start': entity_start_char,
                            'end': len(text)
                        })

            # 规则补充：提取SKU等
            rule_entities = self.extract_entities_rule_based(text)
            entities.extend(rule_entities)

            # 按start位置排序
            entities.sort(key=lambda x: x['start'])

            # 去重 + 重叠处理
            seen = set()
            unique_entities = []
            for e in entities:
                key = (e['text'], e['type'])
                if key not in seen:
                    seen.add(key)
                    # 转换 numpy 类型为 Python 原生类型
                    unique_entities.append({
                        'text': e['text'],
                        'type': e['type'],
                        'start': int(e['start']),
                        'end': int(e['end'])
                    })

            # 解决实体重叠问题：移除被完全包含的实体
            filtered = []
            for e in sorted(unique_entities, key=lambda x: (x['start'], -x['end'])):
                overlaps = False
                for f in filtered:
                    # 检查是否重叠（start < f['end'] and end > f['start']）
                    if e['start'] < f['end'] and e['end'] > f['start']:
                        overlaps = True
                        break
                if not overlaps:
                    filtered.append(e)
            unique_entities = filtered

            # 规则纠偏：用词典匹配修正实体边界
            unique_entities = self._rule_based_correct(text, unique_entities)

            return {
                'text': text,
                'intent': self.id2intent.get(intent_pred_idx, INTENTS[intent_pred_idx]),
                'confidence': float(intent_confidence),
                'top_intents': [{'intent': ti['intent'], 'confidence': float(ti['confidence'])} for ti in top_intents],
                'entities': unique_entities
            }

    def batch_predict(self, texts, top_k=3, use_ner=True):
        """批量预测"""
        results = []
        for text in texts:
            result = self.predict(text, top_k, use_ner)
            results.append(result)
        return results
