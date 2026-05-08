"""
NER 模块 - 基于 AC 自动机的维度实体识别
"""
from ai.ner.trie_ner import TrieNER, DimNER
from ai.ner.ner_service import get_ner_service, reload_ner_service

__all__ = ["TrieNER", "DimNER", "get_ner_service", "reload_ner_service"]
