"""
结果格式化模块 - 响应数据格式化、列重排列
"""
import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("ai.nodes")


class ResultFormatter:
    """结果格式化器"""

    def __init__(self, metric_client=None, dimension_resolver=None):
        self.metric_client = metric_client
        self.dimension_resolver = dimension_resolver

    def normalize_result_columns(
        self,
        result_data: List[Dict],
        metric_name: str,
        generated_sql: str
    ) -> List[Dict]:
        """
        规范化 result_data 的列名：
        1. 识别 GROUP BY 列（维度列）vs metric 列
        2. 将列名 rename 为中文
        3. 重排列顺序

        关键：列 rename 用赋值而非 pop，保留原列数据
        """
        if not result_data or not isinstance(result_data, list):
            return result_data

        logger.info(f"[normalize_result_columns] START result_data[0]={result_data[0] if result_data else 'empty'}, metric_name={metric_name}, generated_sql={generated_sql[:80] if generated_sql else 'None'}")

        # 深拷贝，避免修改原始数据（sql_result 是被缓存的）
        import copy
        result_data = copy.deepcopy(result_data)

        # Step 0: 获取 dim_configs（从 dimension_resolver 或直接）
        dim_configs = {}
        if self.dimension_resolver and generated_sql and generated_sql not in ['METADATA_QUERY', 'NONE']:
            import re
            table_match = re.search(r'FROM\s+([^\s\n;]+)', generated_sql, re.IGNORECASE)
            if table_match:
                table_name = table_match.group(1).strip()
                dim_configs = self.dimension_resolver.get_table_dimensions_cached(table_name)
                logger.info(f"[normalize_result_columns] table_name={table_name}, dim_configs_keys={list(dim_configs.keys())}")

        # Step 1: 构建 column_name -> dimension_name 映射
        # 注意：同时用 column_name 和 dimension_name 作为 key，以兼容两种输入：
        #   - result_data 列名是英文字段名（如 GROUP_2）
        #   - result_data 列名已是中文维度名（如 二级品类）
        col_to_dim_name = {}
        for dim_name, dim_info in dim_configs.items():
            col = dim_info.get("column_name", "")
            if col and dim_name != col:
                col_to_dim_name[col.upper()] = dim_name
                col_to_dim_name[dim_name] = dim_name  # 中文名也作为 key（中文 .upper() == 自身）
        logger.info(f"[normalize_result_columns] dim_configs={dim_configs}, col_to_dim_name={col_to_dim_name}")

        # Step 2: 从 SQL 提取 GROUP BY 列（用于识别维度列）
        sql_group_by_cols = set()
        if generated_sql and generated_sql not in ['METADATA_QUERY', 'NONE']:
            group_by_matches = re.findall(r'GROUP BY\s+([^\s,]+)', generated_sql, re.IGNORECASE)
            for g in group_by_matches:
                col = g.strip('`').upper()
                if col:
                    sql_group_by_cols.add(col)

        # Step 3: 分类列
        # 分类优先级：对比列 > 占比列 > 维度列 > metric列 > 其他列
        # metric列判断：用【数值特征】而非列名——metric列的值是数值，维度列的值是字符串
        dimension_cols = []
        metric_cols = []
        comparison_cols = []
        ratio_cols = []
        other_cols = []

        comparison_patterns = ['去年同期', '同比变化率', '上月同期', '环比变化率']
        ratio_patterns = ['占比', '比率']

        first_row = result_data[0]
        for k in first_row.keys():
            # 对比列
            if any(p in k for p in comparison_patterns):
                comparison_cols.append(k)
            # 占比列
            elif any(p in k for p in ratio_patterns):
                ratio_cols.append(k)
            # 维度列：SQL GROUP BY 列 或 dim_configs 映射的列
            elif k.upper() in sql_group_by_cols or k.upper() in col_to_dim_name:
                dimension_cols.append(k)
            else:
                # 其他列：需要判断是 metric 列还是真正的其他列
                # 判断方法：如果该列的【非空值都是数值】，则为 metric 列
                # 这是因为 GROUP BY 的维度列值是字符串（品类名/品牌名），metric 列值是数值
                is_metric = False
                for row in result_data:
                    v = row.get(k)
                    if v is not None and str(v).strip() not in ('', 'None'):
                        try:
                            float(str(v).replace(',', ''))
                            is_metric = True
                            break
                        except (ValueError, TypeError):
                            pass
                if is_metric:
                    metric_cols.append(k)
                else:
                    other_cols.append(k)

        logger.info(f"[normalize_result_columns] 分类结果: dimension_cols={dimension_cols}, metric_cols={metric_cols}, comparison_cols={comparison_cols}")
        # Step 4: 列 rename（用 pop 删除原列，避免重复）
        # 维度列 rename：GROUP_2 → 二级品类
        logger.info(f"[normalize_result_columns] col_to_dim_name={col_to_dim_name}")
        for row in result_data:
            if not isinstance(row, dict):
                continue
            for col_upper in list(row.keys()):
                if col_upper.upper() in col_to_dim_name:
                    chinese_name = col_to_dim_name[col_upper.upper()]
                    if col_upper != chinese_name:
                        row[chinese_name] = row.pop(col_upper)
                        logger.info(f"[normalize_result_columns] rename: {col_upper} -> {chinese_name}")

        # metric 列 rename：ORDERED_PRODUCTSALES → 总销售额（用 pop 删除原列，避免列重复）
        if metric_cols and metric_name:
            original_metric_col = metric_cols[0]
            if original_metric_col != metric_name:
                for row in result_data:
                    if isinstance(row, dict) and original_metric_col in row:
                        row[metric_name] = row.pop(original_metric_col)  # pop 删除原列，避免 Step 6 cleanup 重复添加

        logger.info(f"[normalize_result_columns] 完成后的列名: {list(result_data[0].keys()) if result_data else 'empty'}")

        # Step 5: 更新 dimension_cols 列表（用新名称）
        new_dim_cols = []
        for dc in dimension_cols:
            new_name = col_to_dim_name.get(dc.upper(), dc)
            new_dim_cols.append(new_name)
        dimension_cols = new_dim_cols

        if metric_cols and metric_name:
            metric_cols = [metric_name]

        # Step 6: 重排列顺序
        column_order = dimension_cols + metric_cols + comparison_cols + ratio_cols + other_cols

        for row in result_data:
            if not isinstance(row, dict):
                continue
            ordered_row = {}
            for col in column_order:
                if col in row:
                    ordered_row[col] = row[col]
            for k in list(row.keys()):
                if k not in column_order:
                    ordered_row[k] = row[k]
            row.clear()
            row.update(ordered_row)

        return result_data

    def reorder_result_columns(
        self,
        result_data: List[Dict],
        column_order: List[str]
    ) -> List[Dict]:
        """按指定顺序重排列"""
        if not result_data or not column_order:
            return result_data

        for row in result_data:
            if not isinstance(row, dict):
                continue
            ordered_row = {}
            for col in column_order:
                if col in row:
                    ordered_row[col] = row[col]
            for k in list(row.keys()):
                if k not in column_order:
                    ordered_row[k] = row[k]
            row.clear()
            row.update(ordered_row)

        return result_data
