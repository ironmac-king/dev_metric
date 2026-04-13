"""
基于 AC 自动机的维度 NER
"""
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger("ai.ner")


class TrieNode:
    """Trie 树节点"""

    def __init__(self):
        self.children: Dict[str, TrieNode] = {}  # 字符 -> 子节点
        self.fail: Optional[TrieNode] = None  # 失败指针
        self.output: List[Dict] = []  # 输出列表（匹配到的词）


class TrieNER:
    """
    基于 AC 自动机（Aho-Corasick）的维度 NER

    使用场景：
    - 一次扫描找出文本中所有已知的维度值
    - 支持同义词映射
    """

    def __init__(self):
        self.root = TrieNode()
        self._built = False

    def _insert(self, word: str, dim_field: str, dim_value: str, standard_name: str = None):
        """
        插入一个词到 Trie 树

        Args:
            word: 要匹配的词（如 "Amazon"、"亚马逊"）
            dim_field: 维度字段（如 "GROUP_3"）
            dim_value: 维度值（如 "有线网卡"）
            standard_name: 标准名（用于同义词映射）
        """
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        # 在节点上存储输出信息
        node.output.append({
            "dim_field": dim_field,
            "dim_value": dim_value,
            "matched": word,
            "standard_name": standard_name or word
        })

    def build(self):
        """构建 AC 自动机的失败指针"""
        from collections import deque

        queue = deque()

        # 初始化第一层失败指针
        for child in self.root.children.values():
            child.fail = self.root
            queue.append(child)

        # BFS 构建失败指针
        while queue:
            current = queue.popleft()

            for char, child in current.children.items():
                queue.append(child)

                # 找到父节点的失败指针
                fail = current.fail
                while fail and char not in fail.children:
                    fail = fail.fail

                # 设置失败指针
                child.fail = fail.children[char] if fail and char in fail.children else self.root

                # 合并失败指针的输出
                if child.fail.output:
                    child.output.extend(child.fail.output)

        self._built = True
        logger.info(f"[TrieNER] AC 自动机构建完成")

    def search(self, text: str) -> List[Dict]:
        """
        在文本中搜索所有已知的维度值

        Args:
            text: 用户输入文本

        Returns:
            List[Dict]: 匹配结果，如
            [{"dim_field": "GROUP_3", "dim_value": "有线网卡", "matched": "有线网卡", "standard_name": "有线网卡"}, ...]
        """
        if not self._built:
            self.build()

        results = []
        node = self.root

        for i, char in enumerate(text):
            # 沿着失败指针走，直到找到匹配或到达根节点
            while node and char not in node.children:
                node = node.fail

            if node is None:
                node = self.root
                continue

            node = node.children[char]

            # 收集所有输出
            for output in node.output:
                results.append({
                    "start": i - len(output["matched"]) + 1,
                    "end": i + 1,
                    "dim_field": output["dim_field"],
                    "dim_value": output["dim_value"],
                    "matched": output["matched"],
                    "standard_name": output["standard_name"]
                })

        return results

    def search_unique(self, text: str) -> List[Dict]:
        """
        搜索并去重，同一个 dim_value 只保留一个

        Returns:
            List[Dict]: 去重后的匹配结果
        """
        results = self.search(text)
        seen = set()
        unique_results = []

        for r in results:
            key = (r["dim_field"], r["dim_value"])
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        return unique_results


class DimNER:
    """
    维度 NER 包装类

    提供更高级的接口：
    - 自动去重
    - 按维度字段分组
    - 支持过滤
    """

    def __init__(self):
        self.trie_ner = TrieNER()
        self._terms_loaded = False

    def load_terms(self, terms: List[Dict]):
        """
        加载术语到 NER

        Args:
            terms: business_terms 表的数据，格式如：
            [{
                "term": "有线网卡",
                "synonyms": ["网卡", "网络卡"],
                "dimension_field": "GROUP_3",
                "dimension_value": "有线网卡"
            }, ...]
        """
        for term in terms:
            term_text = term.get("term", "")
            synonyms = term.get("synonyms", []) or []
            dim_field = term.get("dimension_field", "")
            dim_value = term.get("dimension_value", "")

            if not term_text or not dim_field:
                continue

            # 插入标准词
            self.trie_ner._insert(term_text, dim_field, dim_value, term_text)

            # 插入同义词
            for syn in synonyms:
                if syn and syn != term_text:
                    self.trie_ner._insert(syn, dim_field, dim_value, term_text)

        # 构建 AC 自动机
        self.trie_ner.build()
        self._terms_loaded = True

        logger.info(f"[DimNER] 加载 {len(terms)} 个术语")

    def load_metrics(self, metrics: List[Dict]):
        """
        加载指标名到 NER

        Args:
            metrics: 指标列表，格式如：
            [{
                "name": "总销售额",
                "name_en": "Total Sales",
                "metric_code": "MKI-02-0009"
            }, ...]
        """
        for metric in metrics:
            name = metric.get("name", "")
            name_en = metric.get("name_en", "")
            metric_code = metric.get("metric_code", "")

            if name:
                # 插入中文指标名，类型标记为 "metric"
                self.trie_ner._insert(name, "__METRIC__", metric_code, name)
            if name_en:
                # 插入英文指标名
                self.trie_ner._insert(name_en, "__METRIC__", metric_code, name_en)

        logger.info(f"[DimNER] 加载 {len(metrics)} 个指标")

    def recognize(self, text: str) -> List[Dict]:
        """
        识别文本中的维度

        Args:
            text: 用户输入

        Returns:
            List[Dict]: 识别结果，如
            [{"dim_field": "GROUP_3", "dim_value": "有线网卡", "matched": "有线网卡"}, ...]
        """
        if not self._terms_loaded:
            logger.warning("[DimNER] 术语未加载，返回空结果")
            return []

        return self.trie_ner.search_unique(text)

    def get_dimension_fields(self, text: str) -> List[str]:
        """
        获取文本中涉及的维度字段列表

        Returns:
            List[str]: 如 ["GROUP_3", "FSITE"]
        """
        results = self.recognize(text)
        fields = list(set(r["dim_field"] for r in results))
        return fields

    def get_dimension_values(self, text: str, dim_field: str = None) -> List[str]:
        """
        获取文本中涉及的维度值列表

        Args:
            dim_field: 可选，只返回指定维度的值

        Returns:
            List[str]: 如 ["有线网卡", "无线网卡"]
        """
        results = self.recognize(text)
        if dim_field:
            results = [r for r in results if r["dim_field"] == dim_field]
        values = list(set(r["dim_value"] for r in results))
        return values
