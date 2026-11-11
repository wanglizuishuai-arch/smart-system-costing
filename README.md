# smart-system-costing

智能化 / 弱电 / 农业设施类项目的**方案与投资估算**技能：从客户资料到可交付三件套（DOCX + XLSX + PPTX），且三份金额必须咬合。

## 为什么单独做一个

现有公开技能里，两件事做得很好、但都不覆盖第三件：

| 已有 | 强在哪 | 缺什么 |
|---|---|---|
| `ai-bid-document` 类（投标文档） | 条目化台账、零发明、承诺三档、21 条校验 | 明确声明不做报价测算与成本推算；工程清单需另配模板 |
| `presales-skills` 类（售前方案/PPT） | 方案撰写管道、多源转 PPTX、配图 | 不涉及工程量、取费与核价 |
| `DDC_Skills` 类（建筑 221 技能） | BIM 分析、cost estimation、文档控制 | IFC/西式口径，不含 GB/T 50500 清单计价 |
| 通用"投标写作"类 | 中文标书骨架、导出 Word | 只到"写"，不碰"量与价" |

本技能补的是这一层：**量从哪来、钱怎么算、边界在哪、别人报价差一倍怎么解释**。

## 目录

```
SKILL.md                    主指令：五铁律、四模式、六阶段门禁、停止规则、输出契约
references/
  01-系统清单与容量推导.md     口径冲突、密度假设、存储/带宽/UPS/光缆公式、28 子系统骨架
  02-清单计价与取费.md         GB/T 50500-2024 取费链、五项校验、控制额、可选包、分层建设
  03-交付物与工程实现.md       docx/xlsx/pptx 结构、Office 自动化、Windows 八个坑、交付自检
  04-报价对账与毛利模型.md     同口径归一、砍项映射、成本率表、毛利与净利、三种不赚钱情形
scripts/
  costing_check.py          取费链复算 + 交叉校验（纯标准库，退出码 0/1/2）
templates/
  params.csv                参数模板（含自测基线）
  options.csv               选配开关模板
```

## 快速开始

```bash
# 1. 先跑通基线，确认环境正常
python scripts/costing_check.py --selftest

# 2. 从清单直接汇总（推荐）
python scripts/costing_check.py --boq examples/items.csv --json out.json

# 3. 三件套交付前检查：金额一致 + 占位符清零
python scripts/consistency_check.py --docx 方案.docx --xlsx 概算.xlsx --pptx 汇报.pptx \
    --expect 1982.85,1412.37,1109.57

# 4. 算量
python scripts/capacity.py --video "64,4,90;128,4,30" --bandwidth 350 --ups "3,1.5,4,6" --fiber 6

# 5. 毛利（内部用）
python scripts/margin_model.py --params examples/margin.csv
```

期望：`--selftest` 输出「含税造价 1982.84」且校验全绿、`exit 0`。

## 自测基线

```
设备 750.61 / 材料 290.15 / 软件 203.84 / 服务 167.77
→ 直接费 1412.37 → 安装 145.71 / 调试 62.23 / 管理 48.61
→ 分部分项 1668.92 → 措施 66.76 / 暂列 83.45 → 税前 1819.12
→ 税 163.72 → 含税 1982.84
```

三项回归测试（已在本机验证）：

| 用例 | 命令 | 期望 |
|---|---|---|
| 正常 | `--params templates/params.csv --options templates/options.csv` | exit 0，校验全绿 |
| 输入错误 | `--params 不存在的文件.csv` | exit 2，stderr 报"参数文件不存在" |
| 阻断 | 控制额 1500 < 含税 1982.84 | exit 1，「控制额 ≥ 含税造价」判 `[!!]` |

## 来源

方法来自一个真实项目（国际智慧蓝莓产业园，传统 7 类 20 子系统 + 农业 5 类 8 子系统，含税 1,982 万元）：从规划文本与平面图出发，经口径冲突处理、密度假设、容量推导、清单计价、交叉校验、可选项剥离、同口径对账，到三件套交付与视觉核验，全过程踩过的坑都写进了 `references/03`。

## 边界

- 产出的是**方案阶段估算**（±15%），不能替代注册造价师的招标控制价或结算成果；
- 不处理投标应答表、偏离表、废标风险核查（另有专门技能）；
- 不生成 PPT 视觉与动效，只定义页序与每页要回答的问题；
- 模板与示例中的项目名、数量、金额为脱敏示例，不得直接用于其他项目。

MIT 许可，可直接改、可商用。
## 密钥防泄露（本仓库自带）

仓库里带了一套提交前拦截 + 全历史扫描，随包分发，任何 fork 都能直接用：

| 文件 | 作用 |
|---|---|
| `tools/gitsafe/install.ps1` | 一键给任意 git 仓库装拦截钩子 |
| `tools/gitsafe/pre-commit.py` | 提交时扫暂存区，命中即中止（exit 1） |
| `tools/gitsafe/keyguard_scan.py` | 扫全历史（含已删除文件、commit message） |
| `.github/workflows/keyguard.yml` | push / PR 时自动跑全历史扫描 |

```bash
# 装钩子（Windows PowerShell）
powershell -NoProfile -ExecutionPolicy Bypass -File tools/gitsafe/install.ps1 -Repo .

# 扫全历史
python tools/gitsafe/keyguard_scan.py .
```

行为已实测：

| 场景 | 结果 |
|---|---|
| 硬编码 OpenAI key | 拦（exit 1） |
| 提交 `.env` | 拦 |
| 干净 HTML / CSV | 过 |
| `process.env.OPENAI_API_KEY`、`os.environ[...]` | 过 |
| 文档里的 `your-key-here` 占位符 | 过 |

**误报率低比规则多更重要**——误报多了就会习惯性 `--no-verify`，钩子等于没装。

> 本仓库只放方法、模板与脚本。真实项目的图纸、报价、客户资料一律不进仓库（见 `.gitignore`）。

