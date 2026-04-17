"""
CKNode - 纠错节点（Node4）
输入：生成的 SQL + 对应指标 starrocks_sql 约束
输出：{ sql, is_valid, errors, corrected_sql }
职责：
1. 规则引擎初筛：字段存在性、表名、聚合方式
2. LLM 深度检查：SQL 逻辑是否匹配指标语义
3. 维度列名合法性校验（铁律三）
"""
import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..config_loader import get_config_loader
from ..prompts.ck_prompt import CK_PROMPT

logger = logging.getLogger("ai.llm_v1.ck_node")


@dataclass
class CKOutput:
    """CK 节点输出"""
    sql: str
    is_valid: bool
    errors: List[Dict[str, str]]
    warnings: List[str]
    corrected_sql: Optional[str]


class CKNode:
    """
    纠错节点（CK - Correction & Check）

    职责：
    1. **规则引擎初筛**：
       - SQL 语法检查
       - 字段存在性检查
       - 表名验证
       - 聚合方式验证

    2. **维度列名合法性校验**（铁律三）：
       - 检查 GROUP BY / SELECT 中的列名是否为有效的 column_name
       - 发现中文维度名 → 报错

    3. **LLM 深度检查**：
       - SQL 逻辑是否匹配指标语义
       - 是否符合业务规则

    4. **自动纠错**：
       - 如果发现可自动修复的问题，生成 corrected_sql
    """

    def __init__(self):
        self._config_loader = get_config_loader()
        self._llm_engine = None  # TODO: 后续初始化

    async def process(
        self,
        sql_output,  # SQLOutput
        metric_info: Optional[Dict] = None,
    ) -> CKOutput:
        """
        检查 SQL 是否正确

        Args:
            sql_output: SQL 节点输出
            metric_info: 指标信息（用于语义检查）

        Returns:
            CKOutput: 检查结果
        """
        logger.info(f"[CKNode] 检查 SQL: {sql_output.sql[:100]}...")

        errors = []
        warnings = []

        # Step 1: 规则引擎初筛
        rule_errors, rule_warnings = self._rule_check(sql_output.sql, sql_output.table)
        errors.extend(rule_errors)
        warnings.extend(rule_warnings)

        # Step 2: 维度列名合法性校验（铁律三）
        dimension_errors = self._check_dimension_columns(sql_output.sql)
        errors.extend(dimension_errors)

        # Step 3: LLM 深度检查（可选）
        if not errors and metric_info:
            llm_errors, llm_warnings = await self._llm_check(sql_output.sql, metric_info)
            errors.extend(llm_errors)
            warnings.extend(llm_warnings)

        # Step 4: 判断是否有效
        is_valid = len([e for e in errors if e.get("severity") == "error"]) == 0

        # Step 5: 如果有错误，生成纠错 SQL
        corrected_sql = None
        if errors:
            corrected_sql = self._generate_corrected_sql(sql_output.sql, errors)

        output = CKOutput(
            sql=sql_output.sql,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            corrected_sql=corrected_sql,
        )

        logger.info(
            f"[CKNode] 结果: is_valid={is_valid}, "
            f"errors={len(errors)}, warnings={len(warnings)}"
        )

        return output

    def _rule_check(self, sql: str, table: str) -> tuple:
        """
        规则引擎初筛
        """
        errors = []
        warnings = []

        # 检查是否为空
        if not sql or not sql.strip():
            errors.append({
                "severity": "error",
                "type": "empty_sql",
                "message": "SQL 为空",
            })
            return errors, warnings

        # 检查是否有 SELECT
        if not re.search(r'\bSELECT\b', sql, re.IGNORECASE):
            errors.append({
                "severity": "error",
                "type": "missing_select",
                "message": "SQL 缺少 SELECT 关键字",
            })

        # 检查是否有 FROM
        if not re.search(r'\bFROM\b', sql, re.IGNORECASE):
            errors.append({
                "severity": "error",
                "type": "missing_from",
                "message": "SQL 缺少 FROM 关键字",
            })

        # 检查是否有有效的聚合函数
        if not re.search(r'\b(SUM|AVG|COUNT|MAX|MIN)\s*\(', sql, re.IGNORECASE):
            warnings.append({
                "type": "no_aggregation",
                "message": "SQL 中没有发现聚合函数，可能导致数据异常",
            })

        # 检查时间条件
        if not re.search(r'\bFDATE\b', sql, re.IGNORECASE):
            warnings.append({
                "type": "no_time_condition",
                "message": "SQL 中没有发现时间条件，可能查询范围过大",
            })

        return errors, warnings

    def _check_dimension_columns(self, sql: str) -> List[Dict[str, str]]:
        """
        检查维度列名是否合法（铁律三）
        所有 GROUP BY / SELECT 中的非聚合列必须是数据库列名
        """
        errors = []

        # 获取所有有效的列名
        valid_columns = set(self._config_loader.get_dimension_map().values())
        # 添加一些基础列名
        valid_columns.update({"FDATE", "FSITE", "FSITECODE", "PLATFORM", "GROUP_1", "GROUP_2", "GROUP_3"})

        # 提取 GROUP BY 中的列
        group_by_match = re.search(r'GROUP BY\s+(.+?)(?:HAVING|ORDER|LIMIT|$)', sql, re.IGNORECASE)
        if group_by_match:
            group_by_cols = re.findall(r'\b([A-Z_][A-Z0-9_]*)\b', group_by_match.group(1))
            for col in group_by_cols:
                if col not in valid_columns:
                    # 尝试匹配中文维度名
                    if any('\u4e00' <= c <= '\u9fff' for c in col):
                        # 找到反向映射
                        reverse_map = self._config_loader.get_reverse_dimension_map()
                        column_name = reverse_map.get(col)
                        if column_name:
                            errors.append({
                                "severity": "error",
                                "type": "invalid_dimension_column",
                                "message": f"列名'{col}'是中文维度名，应使用数据库列名'{column_name}'",
                            })
                        else:
                            errors.append({
                                "severity": "error",
                                "type": "invalid_dimension_column",
                                "message": f"列名'{col}'不是有效的数据库列名",
                            })

        # 检查 SELECT 中的非聚合列
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE)
        if select_match:
            select_cols = re.findall(r'\b([A-Z_][A-Z0-9_]*)\b', select_match.group(1))
            for col in select_cols:
                if col not in valid_columns and col not in ["SUM", "AVG", "COUNT", "MAX", "MIN"]:
                    if any('\u4e00' <= c <= '\u9fff' for c in col):
                        reverse_map = self._config_loader.get_reverse_dimension_map()
                        column_name = reverse_map.get(col)
                        if column_name:
                            errors.append({
                                "severity": "error",
                                "type": "invalid_dimension_column",
                                "message": f"SELECT 中的'{col}'是中文维度名，应使用'{column_name}'",
                            })

        return errors

    async def _llm_check(
        self,
        sql: str,
        metric_info: Dict,
    ) -> tuple:
        """
        LLM 深度检查
        检查 SQL 逻辑是否匹配指标语义
        """
        # TODO: 后续实现
        logger.info("[CKNode] LLM 深度检查（TODO: 实现）")
        return [], []

    def _generate_corrected_sql(self, sql: str, errors: List[Dict[str, str]]) -> Optional[str]:
        """
        根据错误生成纠错后的 SQL
        """
        corrected = sql

        for error in errors:
            if error.get("type") == "invalid_dimension_column":
                # 尝试替换中文维度名为正确的列名
                message = error.get("message", "")
                # 提取中文名和正确列名
                match = re.search(r"'(.+?)'.*?'(.+?)'", message)
                if match:
                    wrong_name = match.group(1)
                    correct_name = match.group(2)
                    corrected = corrected.replace(wrong_name, correct_name)
                    logger.info(f"[CKNode] 自动纠错: {wrong_name} → {correct_name}")

        return corrected if corrected != sql else None


# 全局实例
_ck_node: Optional[CKNode] = None


def get_ck_node() -> CKNode:
    """获取 CK 节点单例"""
    global _ck_node
    if _ck_node is None:
        _ck_node = CKNode()
    return _ck_node
