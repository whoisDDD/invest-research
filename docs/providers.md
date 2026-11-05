# 官方数据工具与接入验收

查询日期：2026-11-05。这里区分“官网存在”“发布者已认证”“当前账号能调用”“覆盖满足需求”，不将它们混成一个可用状态。

## 腾讯自选股 / 腾讯微证券

已在SkillHub腾讯认证企业页及腾讯自选股认证发布者页核对官方产品：

https://skillhub.cn/skills/tencent-adm/westock-data

官方页标识 @tencent-adm/westock-data，并说明需先安装 westock CLI，支持macOS/Linux、Windows以及跨平台安装入口。其公开能力包含A/港/美股、ETF、指数、行业、财报、公告和宏观等；不同市场与对象支持维度不同。K线有延迟，必须标注数据日期。

当前官方页面示例：

    westock search 宁德时代
    westock kline sh600519 --period day --limit 20
    westock finance sh600519,sz000651 --limit 1
    westock index constituent sh000300

以上是文档示例，仓库没有安装或执行供应商二进制。真实运行前读取安装包内当前版本说明并核对本人授权。

特别注意：目前所见官方Skill默认输出Markdown表格，并未在本次调查中核实稳定的机器JSON导出。先把它用于Agent交互查询与保存原文证据；如需无人值守批量入库，进一步核对供应商支持的机器接口或导出路径。不要虚构 --json 参数。平台中的旧 westock-mcp 连接器是否能在其他Agent复用、端点和授权是否公开，须在具体宿主核实。

## 同花顺 iFinD

官方服务入口：https://mcp.51ifind.com/

官方说明：https://stock.10jqka.com.cn/20260312/c675239015.shtml
同花顺官方页确认 iFinD MCP & Skill；公开发布说明涵盖A股、基金、宏观行业、公告资讯等模块。当前工具清单、账号额度、计费、导出和跨市场覆盖由本人账号与现行官方配置决定。不要把公开可接入理解成全量免费。

实施顺序：
1. 登录本人官方服务，取得客户端配置。
2. 在宿主接入；枚举 tools/list，保存去敏工具名和schema摘要。
3. 针对同一家公司请求代码、最新财报、历史财报、行情、分红、公告。
4. 确认是否返回完整数据、分页、单位、期间、来源、延迟和截断说明。
5. 小样本校对后才扩大采集。缺少机器可读导出时只标记交互可用。

不在公开仓库填写个人服务URL中的token、认证头、Cookie或API密钥。

## ChatGPT连接器

官方产品说明：https://learn.chatgpt.com/docs/plugins
自定义MCP说明：https://developers.openai.com/api/docs/guides/custom-mcp-server

当前会话目录按“腾讯微证券”“同花顺 iFinD”“FactSet”“LSEG”“Morningstar”检索未返回相应条目；这是本账号当次检索结果，不代表全平台不存在。S&P Global公司官方公告确认其ChatGPT应用及面向已有许可客户的MCP数据接入：

https://www.spglobal.com/en/press/press-release/sp-global-delivers-trusted-financial-data-and-insights-to-customers-through-app-for-chatgpt

Finances的目录说明是连接个人账户获取财务见解，不能据此把它认作A股财报数据源。Data是分析工具，也不等于已获得某家金融数据商授权。

同一数据商的ChatGPT连接器和本地MCP若调用同一底层数据，差别主要是工具设计、覆盖、授权、返回结构和保存能力，不是换个入口就天然更准确。ChatGPT自定义接入还需核对当前账号入口、宿主环境、认证方式及云端可达性，不能把本地stdio配置直接当成云端远程服务。

## 每个来源的最小验收表

- 身份：官方域名、认证发布者、版本、调查时间。
- 授权：当前账号是否真实调用成功；权限和额度不猜测。
- 覆盖：市场、代码、历史长度、频率、核心字段、指数成分。
- 口径：报告期、公告日、单位、币种、合并/母公司、TTM/累计/单季。
- 输出：结构化字段、分页、完整性、延迟、可保存与可复算。
- 样本：与官方原始财报核对营收、归母利润、经营现金流。
- 状态：文档已核实 / 授权待完成 / 查询成功 / 批量历史已验收。

