"""
V2 行级权限控制

根据用户身份动态过滤数据，确保用户只能访问有权限的店铺/品牌/区域等。
"""
import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from ai.config.logging_config import get_logger

logger = get_logger("ai.llm_v2.permission")


@dataclass
class PermissionRule:
    """权限规则"""
    dimension: str           # 维度类型：SHOP / BRAND / REGION / PLATFORM
    allowed_values: Set[str] # 允许的值集合
    deny_all: bool = False  # 拒绝全部


class RowLevelPermission:
    """
    行级数据权限控制器

    用户权限配置示例：
    {
        "user_001": {
            "shops": ["店铺A", "店铺B"],
            "brands": ["品牌X"],
            "regions": ["华东", "华南"],
        }
    }
    """

    def __init__(self, user_permissions: Dict[str, Dict[str, List[str]]] = None):
        """
        初始化权限控制器

        Args:
            user_permissions: 用户权限映射 {
                user_id: {
                    "shops": [...],
                    "brands": [...],
                    "regions": [...],
                }
            }
        """
        self._user_permissions = user_permissions or {}
        self._default_dimensions = ["FSITE", "FBRANDS", "FREGION", "PLATFORM"]

    def get_user_permissions(self, user_id: str) -> Dict[str, List[str]]:
        """获取用户权限"""
        return self._user_permissions.get(user_id, {})

    def add_user_permission(
        self,
        user_id: str,
        dimension: str,
        values: List[str],
    ) -> None:
        """添加用户权限"""
        if user_id not in self._user_permissions:
            self._user_permissions[user_id] = {}
        if dimension not in self._user_permissions[user_id]:
            self._user_permissions[user_id][dimension] = []
        self._user_permissions[user_id][dimension].extend(values)

    def filter_sql(
        self,
        sql: str,
        user_id: str,
        dimension_column_map: Dict[str, str] = None,
    ) -> str:
        """
        为 SQL 添加行级过滤条件

        Args:
            sql: 原始 SQL
            user_id: 用户 ID
            dimension_column_map: 维度到列名的映射

        Returns:
            添加了权限过滤的 SQL
        """
        if dimension_column_map is None:
            dimension_column_map = {
                "shops": "FSITE",
                "brands": "FBRANDS",
                "regions": "FREGION",
                "platforms": "PLATFORM",
            }

        user_perms = self.get_user_permissions(user_id)

        # 如果用户没有任何权限限制，返回原始 SQL
        if not user_perms:
            return sql

        filter_conditions = []

        for perm_dim, perm_values in user_perms.items():
            if not perm_values:
                continue

            # 获取对应的列名
            column = dimension_column_map.get(perm_dim, perm_dim.upper())

            # 构造过滤条件
            values_str = "', '".join(perm_values)
            filter_conditions.append(f"{column} IN ('{values_str}')")

        if not filter_conditions:
            return sql

        # 将过滤条件添加到 SQL
        combined_filter = " AND ".join(filter_conditions)

        if "WHERE" in sql.upper():
            # 已有 WHERE 子句
            sql = re.sub(
                r'(\bWHERE\b)',
                f'WHERE {combined_filter} AND ',
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        elif "GROUP BY" in sql.upper():
            # 没有 WHERE 但有 GROUP BY
            sql = re.sub(
                r'(\bGROUP BY\b)',
                f'WHERE {combined_filter} GROUP BY ',
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        elif "ORDER BY" in sql.upper():
            # 没有 WHERE 和 GROUP BY 但有 ORDER BY
            sql = re.sub(
                r'(\bORDER BY\b)',
                f'WHERE {combined_filter} ORDER BY ',
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        elif "LIMIT" in sql.upper():
            # 没有 WHERE / GROUP BY / ORDER BY 但有 LIMIT
            sql = re.sub(
                r'(\bLIMIT\b)',
                f'WHERE {combined_filter} LIMIT ',
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            # 没有任何子句，直接在 FROM 后添加
            sql = sql + f" WHERE {combined_filter}"

        logger.info(f"[RowLevelPermission] 用户 {user_id} 的 SQL 已添加权限过滤")
        return sql

    def check_access(
        self,
        user_id: str,
        dimension: str,
        value: str,
    ) -> bool:
        """
        检查用户是否有权访问特定维度值

        Args:
            user_id: 用户 ID
            dimension: 维度类型
            value: 维度值

        Returns:
            True if user has access, False otherwise
        """
        user_perms = self.get_user_permissions(user_id)

        # 如果用户没有任何权限限制，允许访问
        if not user_perms:
            return True

        # 检查该维度是否有权限限制
        dim_permissions = user_perms.get(dimension, [])

        # 如果权限列表为空，允许访问（无限制）
        if not dim_permissions:
            return True

        # 检查值是否在允许列表中
        return value in dim_permissions


class DataMasker:
    """
    数据脱敏器

    对敏感数据进行脱敏处理：
    - 手机号：138****5678
    - 邮箱：t***@example.com
    - 金额：显示千/万单位
    """

    @staticmethod
    def mask_phone(phone: str) -> str:
        """脱敏手机号"""
        if not phone or len(phone) < 7:
            return "****"
        return f"{phone[:3]}****{phone[-4:]}"

    @staticmethod
    def mask_email(email: str) -> str:
        """脱敏邮箱"""
        if not email or "@" not in email:
            return "****"
        parts = email.split("@")
        if len(parts[0]) <= 1:
            return f"****@{parts[1]}"
        return f"{parts[0][0]}***@{parts[1]}"

    @staticmethod
    def mask_amount(amount: float, unit: str = "元") -> str:
        """脱敏金额"""
        if amount >= 10000:
            return f"{amount / 10000:.1f}万{unit}"
        elif amount >= 1000:
            return f"{amount / 1000:.1f}千{unit}"
        return f"{amount:.2f}{unit}"

    @staticmethod
    def mask_value(value: str, value_type: str = "text") -> str:
        """
        通用脱敏接口

        Args:
            value: 原始值
            value_type: 值类型 (phone / email / amount / text)
        """
        if value_type == "phone":
            return DataMasker.mask_phone(value)
        elif value_type == "email":
            return DataMasker.mask_email(value)
        elif value_type == "amount":
            try:
                amount = float(value)
                return DataMasker.mask_amount(amount)
            except (ValueError, TypeError):
                return value
        return value  # text 类型不脱敏
