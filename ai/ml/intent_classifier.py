"""
意图分类器 - 基于 TF-IDF + 逻辑回归
用于识别用户问题的意图类型
"""
import os
import pickle
import numpy as np
from typing import List, Dict, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


class IntentClassifier:
    """意图分类器 - 使用 TF-IDF + 逻辑回归"""

    def __init__(self, model_dir: str = None):
        self.model_dir = model_dir or os.path.join(os.path.dirname(__file__), "models")
        self.model: Optional[Pipeline] = None
        self.intents: List[str] = []
        self.confidence_threshold = 0.5

        # 预定义意图列表
        self.available_intents = [
            "query_value",           # 查询数值
            "query_metadata",        # 查询元数据（业务口径、技术口径）
            "query_definition",      # 查询定义
            "query_trend",          # 查询趋势
            "query_comparison",      # 查询对比
            "query_yesterday",      # 查询昨天
            "query_today",          # 查询今天
            "query_this_week",      # 查询本周
            "query_this_month",     # 查询本月
            "greeting",             # 打招呼
            "thanks",                # 感谢
            "bye",                  # 告别
            "unknown",              # 未知
        ]

        # 训练数据示例（实际项目中应该从数据库或标注平台获取）
        self.training_samples = self._get_training_samples()

    def _get_training_samples(self) -> List[Tuple[str, str]]:
        """获取训练样本"""
        return [
            # query_value - 查询数值
            ("广告转化率是多少", "query_value"),
            ("访客数多少", "query_value"),
            ("今天的订单量", "query_value"),
            ("昨天的销售额", "query_value"),
            ("本周新增用户", "query_value"),
            ("本月收入", "query_value"),
            ("有多少", "query_value"),
            ("帮我查一下", "query_value"),
            ("用户数呢", "query_value"),
            ("转化率多少", "query_value"),
            ("销售额多少", "query_value"),
            ("订单量多少", "query_value"),
            ("最近数据", "query_value"),

            # query_metadata - 查询元数据（大幅扩充）
            ("业务口径是什么", "query_metadata"),
            ("业务口径呢", "query_metadata"),
            ("业务口径查询", "query_metadata"),
            ("技术口径是什么", "query_metadata"),
            ("技术口径呢", "query_metadata"),
            ("技术口径查询", "query_metadata"),
            ("业务定义是什么", "query_metadata"),
            ("业务定义呢", "query_metadata"),
            ("技术定义是什么", "query_metadata"),
            ("技术定义呢", "query_metadata"),
            ("指标定义是什么", "query_metadata"),
            ("指标定义呢", "query_metadata"),
            ("怎么计算的", "query_metadata"),
            ("如何计算", "query_metadata"),
            ("计算公式", "query_metadata"),
            ("计算方法", "query_metadata"),
            ("规则是什么", "query_metadata"),
            ("口径是什么", "query_metadata"),
            ("口径呢", "query_metadata"),
            ("定义是什么", "query_metadata"),
            ("定义呢", "query_metadata"),

            # query_trend - 查询趋势
            ("趋势如何", "query_trend"),
            ("走势怎么样", "query_trend"),
            ("走势呢", "query_trend"),
            ("最近变化", "query_trend"),
            ("增长还是下降", "query_trend"),
            ("趋势分析", "query_trend"),
            ("变化趋势", "query_trend"),
            ("呈上升还是下降", "query_trend"),

            # query_comparison - 对比查询
            ("对比上周", "query_comparison"),
            ("对比上期", "query_comparison"),
            ("同比怎么样", "query_comparison"),
            ("同比呢", "query_comparison"),
            ("环比呢", "query_comparison"),
            ("环比怎么样", "query_comparison"),
            ("和昨天比", "query_comparison"),
            ("和上周比", "query_comparison"),
            ("比较一下", "query_comparison"),
            ("对比一下", "query_comparison"),

            # query_yesterday - 昨天
            ("昨天数据", "query_yesterday"),
            ("昨天的", "query_yesterday"),
            ("昨日", "query_yesterday"),
            ("昨天的数据", "query_yesterday"),

            # query_today - 今天
            ("今天数据", "query_today"),
            ("今天的", "query_today"),
            ("今日", "query_today"),
            ("今天的情况", "query_today"),

            # query_this_week - 本周
            ("本周数据", "query_this_week"),
            ("本周的", "query_this_week"),
            ("这周", "query_this_week"),
            ("本周情况", "query_this_week"),

            # query_this_month - 本月
            ("本月数据", "query_this_month"),
            ("本月的", "query_this_month"),
            ("这月", "query_this_month"),
            ("本月情况", "query_this_month"),

            # greeting - 打招呼
            ("你好", "greeting"),
            ("早上好", "greeting"),
            ("您好", "greeting"),
            ("嗨", "greeting"),
            ("hi", "greeting"),
            ("hello", "greeting"),

            # thanks - 感谢
            ("谢谢", "thanks"),
            ("感谢", "thanks"),
            ("谢谢了", "thanks"),
            ("多谢", "thanks"),

            # bye - 告别
            ("再见", "bye"),
            ("拜拜", "bye"),
            ("下次见", "bye"),
            ("走了", "bye"),
        ]

    def train(self) -> bool:
        """训练模型"""
        try:
            texts = [s[0] for s in self.training_samples]
            labels = [s[1] for s in self.training_samples]

            # 转换为numpy数组
            texts = np.array(texts)
            labels = np.array(labels)

            # 创建TF-IDF + 逻辑回归管道
            self.model = Pipeline([
                ('tfidf', TfidfVectorizer(
                    ngram_range=(1, 2),      # 使用1-gram和2-gram
                    max_features=1000,        # 最大特征数
                    min_df=1,                 # 最小文档频率
                    max_df=0.95,              # 最大文档频率
                    sublinear_tf=True,        # 使用对数TF
                )),
                ('clf', LogisticRegression(
                    max_iter=1000,
                    solver='lbfgs',
                    class_weight='balanced',  # 处理类别不平衡
                ))
            ])

            # 训练模型
            self.model.fit(texts, labels)
            self.intents = list(self.model.classes_)

            # 保存模型
            self.save()

            return True
        except Exception as e:
            print(f"[IntentClassifier] 训练失败: {e}")
            return False

    def predict(self, text: str) -> Tuple[str, float]:
        """
        预测意图

        参数:
            text: 用户问题

        返回:
            (意图类型, 置信度)
        """
        # 如果模型未加载，尝试加载
        if self.model is None:
            if not self.load():
                # 加载失败，训练新模型
                self.train()

        if self.model is None:
            return "unknown", 0.0

        try:
            # 预测
            prediction = self.model.predict([text])[0]
            probabilities = self.model.predict_proba([text])[0]
            confidence = float(max(probabilities))

            return prediction, confidence
        except Exception as e:
            print(f"[IntentClassifier] 预测失败: {e}")
            return "unknown", 0.0

    def predict_topk(self, text: str, k: int = 3) -> List[Tuple[str, float]]:
        """
        预测Top-K个可能的意图

        参数:
            text: 用户问题
            k: 返回前k个结果

        返回:
            [(意图, 置信度), ...]
        """
        if self.model is None:
            if not self.load():
                self.train()

        if self.model is None:
            return [("unknown", 0.0)]

        try:
            probabilities = self.model.predict_proba([text])[0]
            classes = self.model.classes_

            # 获取Top-K
            topk_indices = np.argsort(probabilities)[::-1][:k]

            results = []
            for idx in topk_indices:
                results.append((classes[idx], float(probabilities[idx])))

            return results
        except Exception as e:
            print(f"[IntentClassifier] Top-K预测失败: {e}")
            return [("unknown", 0.0)]

    def save(self, path: str = None) -> bool:
        """保存模型"""
        if self.model is None:
            return False

        try:
            os.makedirs(self.model_dir, exist_ok=True)
            model_path = path or os.path.join(self.model_dir, "intent_classifier.pkl")

            with open(model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'intents': self.intents,
                }, f)

            print(f"[IntentClassifier] 模型已保存: {model_path}")
            return True
        except Exception as e:
            print(f"[IntentClassifier] 保存失败: {e}")
            return False

    def load(self, path: str = None) -> bool:
        """加载模型"""
        try:
            model_path = path or os.path.join(self.model_dir, "intent_classifier.pkl")

            if not os.path.exists(model_path):
                print(f"[IntentClassifier] 模型文件不存在: {model_path}")
                return False

            with open(model_path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.intents = data.get('intents', [])

            print(f"[IntentClassifier] 模型已加载: {model_path}")
            return True
        except Exception as e:
            print(f"[IntentClassifier] 加载失败: {e}")
            return False


# 全局单例
_intent_classifier: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    """获取意图分类器单例"""
    global _intent_classifier
    if _intent_classifier is None:
        _intent_classifier = IntentClassifier()
        # 尝试加载已训练的模型，如果不存在则训练
        if not _intent_classifier.load():
            print("[IntentClassifier] 开始训练模型...")
            _intent_classifier.train()
    return _intent_classifier


def predict_intent(text: str) -> Tuple[str, float]:
    """快捷函数：预测意图"""
    classifier = get_intent_classifier()
    return classifier.predict(text)


def predict_intent_topk(text: str, k: int = 3) -> List[Tuple[str, float]]:
    """快捷函数：预测Top-K意图"""
    classifier = get_intent_classifier()
    return classifier.predict_topk(text, k)
