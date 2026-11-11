## 0.3.0 — 2026-11-11

第二批：把"能算"补齐成"能对账、能体检、能自助验证"。

### 新增

- scripts/reconcile.py：两份报价同口径对账（归一系数、逐类差额、Top3 差异桶、真实差价判断）
- scripts/split_layers.py：按关键词把清单拆成投产必建/运营配套，两层各自取费
- scripts/deliverable_qc.py：目录域是否更新、末尾空段、表格跨页、PPTX 形状越界
- eferences/05-单价基准与修正系数.md：基准单价（传统/农业/软件）、地区系数、年度指数、询价校准规则
- 	ests/test_scripts.py：14 条回归测试，零第三方依赖
- README_EN.md、.github/ISSUE_TEMPLATE/（单价偏差、新行业骨架两类模板）

### 修复

- deliverable_qc.py 目录域判定：原按样式名 TOC 前缀识别，中文版 Word 为"目录 1"，导致误报"未更新"；改为识别 PAGEREF 域数量（每条目录项一个），样式名作兜底

### 验证

| 用例 | 结果 |
|---|---|
| 14 条回归测试 | 全部 OK（1.0 s） |
| deliverable_qc.py 跑真实三件套 | 目录已更新 56 行、26 个表格同页 0 跨页、466 个形状 0 越界 |
| split_layers.py --selftest | 正确把报告厅/入口 LED 归入运营配套 |
| econcile.py --selftest | 输出 Top3 差异桶与"倍数≥1.6 → 范围差异"判断 |
## 0.2.1 — 2026-11-11

### 修复

- 	emplates/docx_kit.py：表格上方的引导句/小标题未设 keep-with-next，会出现"标题留在页底、表格跑到下一页"的孤行；改为建表前自动把紧邻段落设为与下段同页
- 效果：某 31 页方案里 26 个表格全部同页完整（此前有 2 个跨页 + 1 个孤标题）
# 更新记录

## 0.2.0 — 2026-11-11

把"能算平"升级为"能交付且能挣钱"：新增四个脚本、内部备忘录模板、排版内核，并修掉两处会真实出错的地方。

### 新增

- `scripts/margin_model.py`：毛利与净利测算，含乐观/中性/悲观三情景敏感度；成本率可调
- `scripts/capacity.py`：视频存储、带宽、UPS、光缆芯数四组公式，每条结论附"边界"一行
- `scripts/consistency_check.py`：三件套（docx/xlsx/pptx）关键金额一致性 + 占位符残留检查
- `templates/internal-margin-memo.md`：内部《成本与报价备忘录》模板（毛利表、三情景、报价底线、预判问答、留档）
- `templates/docx_kit.py`：排版内核，含"整表不跨页 / 表头重复 / 行不拆行"
- `examples/`：可跑的脱敏样例（`items.csv`、`params.csv`、`margin.csv`）
- `references/03` 新增第九节「两种读者：客户版与内部版」，含客户版禁用词清单

### 修复

- `costing_check.py` 的分层校验原用"综合系数近似"，误差可达 1%–3%；改为**逐层走完整取费链**（安装基数按设备材料占比、调试基数按设备材料软件占比折算），两层相加与总额比对
- 新增 `--boq` 直读清单 CSV（支持 `类型,金额` 与 `类别,项目,单位,数量,单价,类型` 两种列），不再手工填四类金额

### 验证

| 用例 | 结果 |
|---|---|
| `costing_check.py --selftest` | 含税 1,982.84，8 项校验全绿，基线全部吻合 |
| `costing_check.py --boq examples/items.csv` | 正确汇总为 278.19 万元直接费 |
| `margin_model.py --selftest` | 毛利 22.9% / 净利 12.1%；悲观 14.3% / 3.9% |
| `capacity.py --selftest` | 存储 520TB、带宽 1,680Mbps、UPS 20.1kVA、光缆 24 芯 |
| `consistency_check.py` 跑真实三件套 | 抓到编制单位 `××智能科技有限公司` 占位符 3 处（真实阻断项） |

## 0.1.0 — 2026-11-11

首个版本。方法来自一个真实项目全流程（传统智能化 7 类 20 子系统 + 农业智能化 5 类 8 子系统，含税 1,982 万元）。

### 新增

- `SKILL.md`：五条铁律、四种模式、六阶段与门禁 G0–G4、六条停止规则、输出契约
- `references/01`：口径冲突处理、密度假设表、四组容量公式、子系统骨架、六种算量错误
- `references/02`：GB/T 50500-2024 取费链、基准算例、五项交叉校验、控制额、可选包扣减、分层建设
- `references/03`：三件套结构、Office 自动化、Windows 八个坑、交付前自检
- `references/04`：同口径归一、砍项映射、成本率表、毛利模型
- `scripts/costing_check.py`、`templates/params.csv`、`templates/options.csv`
- `tools/gitsafe/`：提交前密钥拦截 + 全历史扫描 + CI 巡检

### 已知限制

- 仅覆盖方案阶段估算（±15%），不能替代注册造价师成果
- 单价为地区经验值，跨地区需整体调整
- 未包含 BIM 算量与 IFC 解析

