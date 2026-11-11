# -*- coding: utf-8 -*-
"""回归测试：8 个用例，零第三方依赖（docx/pptx 相关用例会自动跳过）

    python -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)


def run(script, *args):
    cmd = [sys.executable, os.path.join(SCRIPTS, script)] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class T1_CostingChain(unittest.TestCase):
    def test_selftest_passes(self):
        code, out = run("costing_check.py", "--selftest")
        self.assertEqual(code, 0, out)
        self.assertIn("基线比对：全部吻合", out)

    def test_control_below_total_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "p.csv")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("key,value\neq,750.61\nmat,290.15\nsw,203.84\nsv,167.77\ncontrol_main,1500\n")
            code, out = run("costing_check.py", "--params", f)
            self.assertEqual(code, 1, out)
            self.assertIn("控制额", out)

    def test_missing_file_is_input_error(self):
        code, out = run("costing_check.py", "--params", os.path.join(ROOT, "no_such.csv"))
        self.assertEqual(code, 2, out)


class T2_Boq(unittest.TestCase):
    def test_boq_aggregates(self):
        fixtures = os.path.join(ROOT, "examples", "items.csv")
        code, out = run("costing_check.py", "--boq", fixtures)
        self.assertEqual(code, 0, out)
        self.assertIn("直接费", out)
        # 示例清单四类合计 278.19 万元
        self.assertRegex(out, r"直接费\s+278\.\d\d")


class T3_Capacity(unittest.TestCase):
    def test_storage_and_ups(self):
        code, out = run("capacity.py", "--selftest")
        self.assertEqual(code, 0, out)
        self.assertIn("520", out)          # 建议配置 520TB
        self.assertIn("kVA", out)
        self.assertIn("边界", out)


class T4_Margin(unittest.TestCase):
    def test_margin_scenarios(self):
        code, out = run("margin_model.py", "--selftest")
        self.assertEqual(code, 0, out)
        self.assertIn("净利", out)
        self.assertIn("悲观", out)

    def test_margin_requires_amounts(self):
        code, out = run("margin_model.py")
        self.assertEqual(code, 2, out)


class T5_SplitLayers(unittest.TestCase):
    def test_split_selftest(self):
        code, out = run("split_layers.py", "--selftest")
        self.assertEqual(code, 0, out)
        self.assertIn("投产必建", out)
        self.assertIn("运营配套", out)
        self.assertIn("报告厅音视频", out)


class T6_Reconcile(unittest.TestCase):
    def test_reconcile_selftest(self):
        code, out = run("reconcile.py", "--selftest")
        self.assertEqual(code, 0, out)
        self.assertIn("逐类对账", out)
        self.assertIn("真实差价", out)

    def test_reconcile_needs_both(self):
        code, out = run("reconcile.py", "--mine", "x.csv")
        self.assertEqual(code, 2, out)


class T7_ConsistencyPlaceholder(unittest.TestCase):
    def test_placeholder_detected(self):
        import consistency_check as cc
        texts = ["编制单位：××智能科技有限公司", "合计 1,982.85 万元", "[待确认: 面积口径]"]
        res = cc.scan("dummy.docx", texts, ["1982.85"])
        self.assertEqual(res["missing"], [])
        kinds = {p["type"] for p in res["placeholders"]}
        self.assertIn("×× 占位", kinds)
        self.assertIn("待确认标记", kinds)

    def test_missing_amount_detected(self):
        import consistency_check as cc
        res = cc.scan("dummy", ["合计 1,900 万元"], ["1982.85"])
        self.assertEqual(res["missing"], ["1982.85"])


class T8_QcBounds(unittest.TestCase):
    def test_qc_requires_target(self):
        code, out = run("deliverable_qc.py")
        self.assertEqual(code, 2, out)

    def test_qc_docx_when_available(self):
        try:
            import docx  # noqa: F401
        except ImportError:
            self.skipTest("python-docx 未安装")
        from docx import Document
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "t.docx")
            doc = Document()
            doc.add_paragraph("标题")
            doc.add_paragraph("正文")
            doc.save(f)
            code, out = run("deliverable_qc.py", "--docx", f)
            self.assertIn("交付物体检", out)
            self.assertIn("结论", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)