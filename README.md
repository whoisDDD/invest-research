# Invest Research

面向 ChatGPT、WorkBuddy、OpenCode Desktop 与 DeepSeek Harness 的开放投资研究框架。

**数据优先复用官方 MCP / Skill / CLI；程序固定计算；AI解释与核查；人作判断。**

## 当前状态

v0.3.0：默认报告升级为离线交互财报看板，包含公司/币种分组、期间与口径切换、指标卡、收入利润趋势、同比、现金流和净利率图。图例可切换，图表和卡片可查看证据，明细可筛选/排序/导出；支持深浅主题和窄屏。财务计算与证据契约延续0.2.0。厂商授权、真实取数覆盖和客户端联调仍需在使用者环境验收。

## 开始

从 Google Drive 下载项目包时，先解压并在 `invest-research` 目录打开终端或本地Agent。详见 [Drive交付与启动](docs/drive-quickstart.md)。后续发布到GitHub时沿用同一项目。

需要 Python 3.10 或以上。基础演示只用标准库，无需安装模型或数据商SDK。

    git clone https://github.com/whoisDDD/invest-research.git
    cd invest-research
    python -m unittest discover -s tests -v
    python -m invest_research doctor
    python -m invest_research demo --out runs/demo

用浏览器打开 runs/demo/report.html 即可体验交互看板，无需服务器或联网；将 runs/demo/review_pack.zip 上传给 ChatGPT。演示包含两家虚构公司、各19个季度，全部为明确标注的合成数据，不代表任何真实证券。examples/demo.csv仍保留为最小测试样例。

看板以图表和指标卡为主，完整表格放在“指标明细”。公司、报告期、最近4期/8期/全部及TTM/单季/累计联动；显示金额用亿元等可读单位，比率用百分比，完整精度保存在metrics.json。每期26项指标的计算不变，缺失不补零。点击指标卡、图表数据点或表格数值可查看完整数值、依赖与原文链接。

趋势线按真实日期排列，缺失季度断线；柱图和折线纵轴包含零，负现金流可显示在零线下方。同一图中不混合不同币种；自由现金流和归母净利率卡片始终明确标注TTM。“本期观察”仅复述指标变化，不自动生成因果分析或投资结论。

旧版完整表格保留在 runs/demo/static_report.html，看板有直接入口；禁用JavaScript时也提供此入口。两个HTML及原始数据、脚本、口径、来源都在研究包内，计算可脱离仓库复算。

有来源明确的标准化数据后运行：

    python -m invest_research analyze --input path/to/facts.csv --as-of 2026-11-05 --out runs/my-review

核验记录可通过CSV可选列逐条提供，见docs/metrics.md；未提供时显示未核对，不根据“成功取数”自动变成已核实。

doctor只做本机工具发现，不测试授权。额外技能路径可用 `python -m invest_research doctor --skill-dir /path/to/westock-data` 指定；缺少CLI或Python MCP SDK不代表宿主没有可用MCP。

## 给本地Agent的第一句话

“先阅读 AGENTS.md 和 docs/framework.md，按 prompts/bootstrap.md 检查当前环境、官方数据源和实际权限；复用已有程序，完成一次真实样本取数、字段映射、原文核对和报告，不把演示样例当实测数据。”

个人直接 clone 即可。需要独立修改、保留个人规则或贡献上游时再 fork。单独保存自己的数据与账号配置。

## 内容地图

- AGENTS.md：所有Agent共用的工作规则。
- docs/framework.md：市场—行业—公司—财务—估值—风险—跟踪的完整框架。
- docs/metrics.md：指标、日期与比较口径。
- docs/providers.md：官方数据源调查及接入验收。
- docs/clients.md：ChatGPT、本地Agent与官方工具的协作方法。
- docs/roadmap.md：已实现、待联调与后续阶段。
- prompts/：初始化、研究、交叉复核的通用指令。
- config/：不含密钥的连接与观察池示例。
- invest_research/：确定性计算、质量检查、HTML与研究包。
- invest_research/ui/：离线看板模板、样式和交互脚本；生成时内嵌到单个HTML，不依赖CDN。
- examples/：合成数据与研究记录模板。
- tests/：财务口径和端到端验证。

## 开发者验证

Python基础测试无需Node或额外依赖。修改交互脚本时，可选安装开发测试依赖后运行：

    npm ci --ignore-scripts
    npm run test:ui

Node只用于开发测试；最终HTML及日常财务计算不需要Node。DOM行为测试不等于浏览器截图验收。产品范围和后续图形化扩展见docs/dashboard.md。

## 数据接入原则

1. 首选已核验发布者的官方工具。例如腾讯官方 westock-data 目前公开说明依赖 westock CLI；同花顺提供 iFinD MCP & Skill。
2. MCP连接、Skill说明、CLI命令和数据授权分别验证。Skill不一定通过MCP，也可能直接调用API或CLI。
3. 保存来源返回、日期、单位与请求说明，再映射到统一数据契约。只返回Markdown的工具先作为交互取证通道；不要猜测未在官方说明中的JSON参数或批量导出能力。
4. 数据平台的预计算指标与本项目自算指标分别保留，不覆盖、拼接或混称官方口径。
5. 开源代码和模板可以共享；账号密钥、个人研究记录与供应商原始数据留在本地。开源仓库不等于获得供应商数据再分发权。

## 许可证

代码与原创文档采用 MIT License。厂商工具和数据遵循各自授权；本仓库不打包第三方Skill正文或私有数据。

