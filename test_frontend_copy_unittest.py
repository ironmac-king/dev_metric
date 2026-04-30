import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


class FrontendCopyTests(unittest.TestCase):
    def test_layout_labels_are_readable(self):
        text = (PROJECT_ROOT / "web/src/views/Layout.vue").read_text(encoding="utf-8")

        expected_labels = [
            "工作台",
            "指标库",
            "智能问数",
            "决策分析",
            "反馈看板",
            "问数分析",
            "意图配置",
            "配置中心",
            "用户管理",
            "导航菜单",
            "头像设置",
            "点击选择或上传头像",
            "预设头像",
            "自定义上传",
            "支持 JPG、PNG，建议尺寸 128x128",
            "账号设置",
            "退出登录",
            "已退出登录",
        ]
        for label in expected_labels:
            self.assertIn(label, text)

        broken_snippets = ["?/span>", "?/div>", "title=\"韪?", "宸ヤ綔鍙?", "鎸囨爣搴?"]
        for snippet in broken_snippets:
            self.assertNotIn(snippet, text)

    def test_config_center_labels_are_readable(self):
        text = (PROJECT_ROOT / "web/src/views/ConfigCenter.vue").read_text(encoding="utf-8")

        expected_labels = [
            "配置中心",
            "管理智能问数后台配置",
            "数据源配置",
            "触发规则",
            "开关管理",
            "模板配置",
            "维度标签",
            "维度配置",
            "意图配置",
            "LLM配置",
            "告警配置",
        ]
        for label in expected_labels:
            self.assertIn(label, text)

        self.assertNotIn("鏁版嵁婧愰厤缃?", text)
        self.assertNotIn("閰嶇疆涓績", text)

    def test_llm_ask_message_actions_are_readable(self):
        text = (PROJECT_ROOT / "web/src/views/LLMAskV2A.vue").read_text(encoding="utf-8")

        expected_labels = [
            "复制",
            "数据解读",
            "解读",
            "好评",
            "差评",
            "生成报告",
            "决策分析",
        ]
        for label in expected_labels:
            self.assertIn(label, text)

        self.assertFalse((PROJECT_ROOT / "web/src/components/ask/ActionBar.vue").exists())

    def test_llm_ask_view_has_no_known_undefined_runtime_references(self):
        text = (PROJECT_ROOT / "web/src/views/LLMAskV2A.vue").read_text(encoding="utf-8")

        self.assertNotIn("currentSql.value = finalSql", text)
        self.assertNotIn("thinkingStepsMap", text)


if __name__ == "__main__":
    unittest.main()
