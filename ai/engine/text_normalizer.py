"""
文本预处理器 - 输入标准化 + 纠错
在意图识别之前执行文本清洗，提升NL2SQL鲁棒性

功能：
1. 文本标准化（全角→半角、去除emoji、统一空白符）
2. 中文数字标准化（复用 time_parser 的 CHINESE_DIGITS）
3. 同义词预处理替换（从 business_terms 表加载）
4. 错别字纠正（集成 pycorrector）
"""
import re
import time
from typing import Dict, Optional

from ai.config.logging_config import get_logger
from ai.client.http_client import get_http_client

logger = get_logger("ai.text_normalizer")


class TextNormalizer:
    """输入文本预处理器 - 同步版本，兼容现有同步调用"""

    # 中文数字映射（复用 time_parser.py 的逻辑）
    CHINESE_DIGITS = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '零': '0', '两': '2',
    }

    # Emoji 正则（预编译）
    _emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F]"  # emoticons
        "[\U0001F300-\U0001F5FF]"  # symbols & pictographs
        "[\U0001F680-\U0001F6FF]"  # transport & map symbols
        "[\U0001F700-\U0001F77F]"  # alchemical symbols
        "[\U0001F780-\U0001F7FF]"  # Geometric Shapes Extended
        "[\U0001F800-\U0001F8FF]"  # Supplemental Arrows-C
        "[\U0001F900-\U0001F9FF]"  # Supplemental Symbols and Pictographs
        "[\U0001FA00-\U0001FA6F]"  # Chess Symbols
        "[\U0001FA70-\U0001FAFF]"  # Symbols and Pictographs Extended-A
        "[\U00002702-\U000027B0]"  # Dingbats
        "[\U00002460-\U000024FF]"  # Enclosed Alphanumeric Supplement
        "|[\U00002600-\U000026FF]"  # Miscellaneous Symbols
    )

    def __init__(self, api_base: str = "http://localhost:8080"):
        self.api_base = api_base
        self._synonyms_cache: Dict[str, str] = {}  # {同义词(小写): 标准术语}
        self._synonyms_cache_time: float = 0
        self._synonyms_ttl: float = 3600  # 1小时缓存

        self._typo_cache: Dict[str, str] = {}  # {原始文本: 纠错后文本}
        self._typo_cache_ttl: float = 300  # 5分钟缓存

        self._pycorrector_loaded = False
        self._pycorrector = None

    def normalize_sync(self, text: str) -> str:
        """
        同步预处理主入口 - 供 intent_node 调用

        Args:
            text: 原始用户输入

        Returns:
            预处理后的文本
        """
        if not text:
            return text

        original = text
        logger.debug(f"[TextNormalizer] 原始输入: '{text}'")

        # Step 1: 简单规则（高性能）
        text = self._fullwidth_to_halfwidth(text)
        text = self._remove_emoji(text)
        text = self._normalize_whitespace(text)

        # Step 2: 中文数字标准化
        text = self._normalize_chinese_numbers(text)

        # Step 3: 同义词预处理替换
        text = self._expand_synonyms(text)

        # Step 4: 错别字纠正
        text = self._correct_typos(text)

        if text != original:
            logger.debug(f"[TextNormalizer] 预处理后: '{text}'")

        return text

    def _fullwidth_to_halfwidth(self, text: str) -> str:
        """全角转半角 - 数字、字母、符号、空格"""
        result = []
        for char in text:
            code = ord(char)
            # 全角数字 (0-9): 65296-65305 → 半角
            if 0xFF10 <= code <= 0xFF19:
                result.append(chr(code - 0xFEE0))
            # 全角大写字母 (A-Z): 65313-65338 → 半角
            elif 0xFF21 <= code <= 0xFF3A:
                result.append(chr(code - 0xFEE0))
            # 全角小写字母 (a-z): 65345-65370 → 半角
            elif 0xFF41 <= code <= 0xFF5A:
                result.append(chr(code - 0xFEE0))
            # 全角空格 → 半角空格
            elif code == 0x3000:
                result.append(' ')
            else:
                result.append(char)
        return ''.join(result)

    def _remove_emoji(self, text: str) -> str:
        """去除表情符号"""
        return self._emoji_pattern.sub('', text)

    def _normalize_whitespace(self, text: str) -> str:
        """统一空白字符 - 多个空格合并为首尾空格去除"""
        # 多个空白符 → 单个空格
        text = re.sub(r'\s+', ' ', text)
        # 去除首尾空格
        return text.strip()

    def _normalize_chinese_numbers(self, text: str) -> str:
        """
        中文数字标准化 - 将中文数字替换为阿拉伯数字

        转换模式：
        - 近七天 → 近7天
        - 三月份 → 3月份
        - 近三十天 → 近30天
        """
        # 时间表达式中的数量词模式
        quantity_patterns = [
            # 近X天/周/月/年
            (r'近([零一二两三四五六七八九十]+)个?[天日周月年]', self._replace_chinese_number),
            # 最近X天/周/月/年
            (r'最近([零一二两三四五六七八九十]+)个?[天日周月年]', self._replace_chinese_number),
            # 上X天/周/月/年
            (r'上([零一二两三四五六七八九十]+)个?[天日周月年]', self._replace_chinese_number),
            # 过去X天/周/月/年
            (r'过去([零一二两三四五六七八九十]+)个?[天日周月年]', self._replace_chinese_number),
            # X月份（X月）
            (r'([零一二两三四五六七八九十]+)月份?', self._replace_chinese_number),
            # 第X（排名等）
            (r'第([零一二两三四五六七八九十]+)', self._replace_chinese_number),
        ]

        for pattern, replacer in quantity_patterns:
            text = re.sub(pattern, replacer, text)

        return text

    def _replace_chinese_number(self, match) -> str:
        """替换中文数字为阿拉伯数字"""
        chinese_num = match.group(1)
        result = []
        for char in chinese_num:
            result.append(self.CHINESE_DIGITS.get(char, char))
        return ''.join(result)

    def _load_synonyms(self) -> Dict[str, str]:
        """从 Go API 加载同义词映射，缓存1小时"""
        # 检查缓存
        if self._synonyms_cache and (time.time() - self._synonyms_cache_time) < self._synonyms_ttl:
            return self._synonyms_cache

        synonyms_map: Dict[str, str] = {}
        try:
            client = get_http_client()
            response = client.get(f"{self.api_base}/api/v1/metadata/terms", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    terms = data.get("data", [])
                    for t in terms:
                        term = t.get("term", "")
                        if not term:
                            continue

                        # 处理 synonyms 可能是字符串（PostgreSQL数组格式）或列表
                        synonyms_raw = t.get("synonyms", [])
                        if isinstance(synonyms_raw, str):
                            synonyms_raw = synonyms_raw.strip("{}").split(",") if synonyms_raw else []
                        synonyms = synonyms_raw if isinstance(synonyms_raw, list) else []

                        # 建立同义词 → 标准术语 的映射
                        for syn in synonyms:
                            syn = syn.strip()
                            if syn and len(syn) > 1:  # 跳过单字符
                                synonyms_map[syn.lower()] = term

                        # 也建立 term_lower → term 的映射
                        synonyms_map[term.lower()] = term

            self._synonyms_cache = synonyms_map
            self._synonyms_cache_time = time.time()
            logger.info(f"[TextNormalizer] 加载了 {len(synonyms_map)} 个同义词映射")
        except Exception as e:
            logger.warning(f"[TextNormalizer] 加载同义词失败: {e}")
            # 返回已有缓存（即使过期）
            if self._synonyms_cache:
                return self._synonyms_cache

        return synonyms_map

    def _expand_synonyms(self, text: str) -> str:
        """
        同义词预处理替换 - 将用户输入的同义词替换为标准术语

        按同义词长度降序排列，优先匹配更长的同义词
        """
        synonyms_map = self._load_synonyms()
        if not synonyms_map:
            return text

        text_lower = text.lower()

        # 按长度降序排列（优先匹配更长的同义词）
        sorted_synonyms = sorted(synonyms_map.keys(), key=len, reverse=True)

        for syn in sorted_synonyms:
            if len(syn) <= 1:  # 跳过单字符同义词
                continue
            if syn in text_lower:
                # 替换时保持原始大小写格式
                standard_term = synonyms_map[syn]
                # 使用正则进行大小写不敏感替换
                pattern = re.compile(re.escape(syn), re.IGNORECASE)
                new_text = pattern.sub(standard_term, text)
                if new_text != text:
                    logger.debug(f"[TextNormalizer] 同义词替换: '{syn}' → '{standard_term}'")
                    text = new_text
                    text_lower = text.lower()  # 更新小写版本

        return text

    def _correct_typos(self, text: str) -> str:
        """
        错别字纠正 - 集成 pycorrector，带缓存
        """
        # 检查缓存
        if text in self._typo_cache:
            cached = self._typo_cache[text]
            if cached != text:
                logger.debug(f"[TextNormalizer] 错别字缓存命中: '{text}' → '{cached}'")
            return cached

        # 懒加载 pycorrector
        if not self._pycorrector_loaded:
            try:
                import pycorrector
                self._pycorrector = pycorrector
                self._pycorrector_loaded = True
                logger.info("[TextNormalizer] pycorrector 加载成功")
            except ImportError:
                logger.warning("[TextNormalizer] pycorrector 未安装，跳过错别字纠正")
                self._typo_cache[text] = text
                return text
            except Exception as e:
                logger.warning(f"[TextNormalizer] pycorrector 加载失败: {e}")
                self._typo_cache[text] = text
                return text

        try:
            corrected, detail = self._pycorrector.correct(text)

            if corrected != text:
                logger.info(f"[TextNormalizer] 错别字纠正: '{text}' → '{corrected}'")
                logger.debug(f"[TextNormalizer] 纠错详情: {detail}")

            # 缓存结果（即使是原文本也缓存，避免重复检查）
            self._typo_cache[text] = corrected
            return corrected

        except Exception as e:
            logger.warning(f"[TextNormalizer] 错别字纠正失败: {e}")
            self._typo_cache[text] = text
            return text

    def clear_cache(self):
        """清除所有缓存"""
        self._synonyms_cache = {}
        self._synonyms_cache_time = 0
        self._typo_cache = {}
        logger.info("[TextNormalizer] 缓存已清除")
