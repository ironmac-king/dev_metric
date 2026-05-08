"""
相似问题推荐 - 基于向量相似度推荐相似问题
使用 TF-IDF + 余弦相似度
"""
import os
import pickle
import numpy as np
from typing import List, Dict, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SimilarQuestionRecommender:
    """相似问题推荐器"""

    def __init__(self, model_dir: str = None):
        self.model_dir = model_dir or os.path.join(os.path.dirname(__file__), "models")
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.question_vectors: Optional[np.ndarray] = None
        self.questions: List[str] = []

        # 内置常见问题模板
        self.sample_questions = [
            # 数值查询
            "广告转化率是多少",
            "访客数多少",
            "今天的订单量",
            "昨天的销售额",
            "本周新增用户",
            "本月收入",
            "有多少",
            "用户数呢",
            "转化率多少",

            # 元数据查询
            "业务口径是什么",
            "技术口径呢",
            "业务定义是什么",
            "怎么计算的",
            "指标定义",
            "规则是什么",

            # 趋势查询
            "趋势如何",
            "走势怎么样",
            "最近变化",
            "增长还是下降",

            # 对比查询
            "对比上周",
            "同比怎么样",
            "环比呢",
            "和昨天比",

            # 时间查询
            "昨天数据",
            "本周数据",
            "本月数据",
        ]

    def build_index(self, questions: List[str] = None) -> bool:
        """
        构建问题索引

        参数:
            questions: 问题列表，如果为None则使用内置问题
        """
        try:
            if questions is None:
                questions = self.sample_questions

            self.questions = questions

            # 创建TF-IDF向量化器
            self.vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=1000,
                min_df=1,
                sublinear_tf=True,
            )

            # 向量化所有问题
            self.question_vectors = self.vectorizer.fit_transform(questions)

            # 保存模型
            self.save()

            return True
        except Exception as e:
            print(f"[SimilarQuestionRecommender] 构建索引失败: {e}")
            return False

    def add_question(self, question: str) -> bool:
        """添加新问题到索引"""
        try:
            if question in self.questions:
                return True

            self.questions.append(question)

            # 重新向量化
            if self.vectorizer is None:
                return self.build_index(self.questions)

            # 只向量化新问题
            new_vector = self.vectorizer.transform([question])
            self.question_vectors = np.vstack([self.question_vectors.toarray(), new_vector.toarray()])

            return True
        except Exception as e:
            print(f"[SimilarQuestionRecommender] 添加问题失败: {e}")
            return False

    def find_similar(self, query: str, topk: int = 5, min_score: float = 0.3) -> List[Tuple[str, float]]:
        """
        查找相似问题

        参数:
            query: 查询问题
            topk: 返回前k个结果
            min_score: 最低相似度分数

        返回:
            [(相似问题, 相似度分数), ...]
        """
        try:
            if self.vectorizer is None or self.question_vectors is None:
                if not self.load():
                    self.build_index()

            if self.vectorizer is None:
                return []

            # 向量化查询
            query_vector = self.vectorizer.transform([query])

            # 计算余弦相似度
            scores = cosine_similarity(query_vector, self.question_vectors)[0]

            # 获取Top-K
            topk_indices = np.argsort(scores)[::-1][:topk]

            results = []
            for idx in topk_indices:
                score = float(scores[idx])
                if score >= min_score:
                    results.append((self.questions[idx], score))

            return results
        except Exception as e:
            print(f"[SimilarQuestionRecommender] 查找相似问题失败: {e}")
            return []

    def recommend_followup(self, current_question: str, intent: str = None) -> List[str]:
        """
        根据当前问题推荐后续问题

        参数:
            current_question: 当前问题
            intent: 当前意图

        返回:
            推荐的后续问题列表
        """
        # 先找相似问题
        similar = self.find_similar(current_question, topk=10, min_score=0.2)

        # 基于意图生成推荐
        recommendations = []

        if intent == "query_value":
            # 查询数值后，推荐元数据查询或趋势查询
            recommendations.extend([
                "业务口径是什么",
                "技术口径呢",
                "趋势如何",
            ])

        elif intent == "query_metadata":
            # 查询元数据后，推荐数值查询
            recommendations.extend([
                "最近数据是多少",
                "本周数据如何",
                "查看趋势",
            ])

        elif intent == "query_trend":
            # 查询趋势后，推荐对比或具体数值
            recommendations.extend([
                "对比上周",
                "具体数值多少",
                "原因是什么",
            ])

        # 添加相似问题
        for q, score in similar[:3]:
            if q != current_question and q not in recommendations:
                recommendations.append(q)

        return recommendations[:5]

    def save(self, path: str = None) -> bool:
        """保存模型"""
        try:
            os.makedirs(self.model_dir, exist_ok=True)
            model_path = path or os.path.join(self.model_dir, "similar_questions.pkl")

            data = {
                'vectorizer': self.vectorizer,
                'question_vectors': self.question_vectors,
                'questions': self.questions,
            }

            with open(model_path, 'wb') as f:
                pickle.dump(data, f)

            print(f"[SimilarQuestionRecommender] 模型已保存: {model_path}")
            return True
        except Exception as e:
            print(f"[SimilarQuestionRecommender] 保存失败: {e}")
            return False

    def load(self, path: str = None) -> bool:
        """加载模型"""
        try:
            model_path = path or os.path.join(self.model_dir, "similar_questions.pkl")

            if not os.path.exists(model_path):
                print(f"[SimilarQuestionRecommender] 模型文件不存在: {model_path}")
                return False

            with open(model_path, 'rb') as f:
                data = pickle.load(f)

            self.vectorizer = data.get('vectorizer')
            self.question_vectors = data.get('question_vectors')
            self.questions = data.get('questions', [])

            print(f"[SimilarQuestionRecommender] 模型已加载: {model_path}")
            return True
        except Exception as e:
            print(f"[SimilarQuestionRecommender] 加载失败: {e}")
            return False


# 全局单例
_similar_recommender: Optional[SimilarQuestionRecommender] = None


def get_similar_recommender() -> SimilarQuestionRecommender:
    """获取相似问题推荐器单例"""
    global _similar_recommender
    if _similar_recommender is None:
        _similar_recommender = SimilarQuestionRecommender()
        # 尝试加载已训练的模型，如果不存在则构建
        if not _similar_recommender.load():
            print("[SimilarQuestionRecommender] 开始构建问题索引...")
            _similar_recommender.build_index()
    return _similar_recommender


def find_similar_questions(query: str, topk: int = 5) -> List[Tuple[str, float]]:
    """快捷函数：查找相似问题"""
    recommender = get_similar_recommender()
    return recommender.find_similar(query, topk=topk)


def recommend_followup(current_question: str, intent: str = None) -> List[str]:
    """快捷函数：推荐后续问题"""
    recommender = get_similar_recommender()
    return recommender.recommend_followup(current_question, intent)
