# 数据契约与指标

## facts.csv

必需列：
entity_id, period_end, published_at, metric, value, currency, scale, scope, period_type, source_id, source_url

- 日期为ISO自然日；本版只做日级截至时间，不声称支持盘中历史回测。
- period_type为ytd，表示从该自然年1月1日至period_end的累计流量；12月31日为全年。
- scope为consolidated；母公司单体报表另设数据集。
- value允许留空；空值不填0。scale支持1、1000、10000、1000000、100000000。
- 示例metric：revenue、parent_net_profit、operating_cashflow、capex。
- currency为原报告币种；本版不自动换汇。
- source_id和source_url必须有值。原始返回、请求、工具版本保存在本地，source_url指向官方原文或供应商证据页。
- 本版自动计算针对自然年、非金融、合并报表累计流量。非自然年美股、银行和存量指标不强行导入本版计算器。
- 相同实体/期间/指标/币种/合并范围取as_of日已公布的最新版本；同日冲突报错。
- 不带时刻的公告日只支持日终研究；报告不能冒充当日收盘前已知信息。

### 可选的逐条证据列（向后兼容旧CSV）

| 列 | 默认值 | 用途 |
| --- | --- | --- |
| verification | unverified | 仅允许unverified或checked_against_disclosure；后者表示输入提供者声明已对照原文 |
| evidence_locator | 空 | 已核对时必须填写原文链接、页码、表名、行名等定位依据；source_url同时保留取数出处 |
| unit_basis | not_recorded | 记录该字段的币种和单位依据，按表核对，不能把整篇PDF视为同一单位 |
| publication_basis | source_reported_date | 记录披露日期、平台发布时间日期等具体口径，不能混用 |
| source_quality | unclassified | unclassified、disclosure、supplier_evidence、tool_description四选一 |

source_url必须是无内嵌用户名/密码的HTTP(S)链接。只有工具介绍页时使用tool_description，不把它当成财报原文。取数成功、数学复算通过与原文真实性核验是三个不同状态。程序不自动验证输入的核验声明；HTML与manifest会明确说明这点。

交易所披露日期与平台发布时间可能不同；同时保留原始字段及其定义、时区和请求证据，不对全部日期统一增减一天。需要使用实际可获得时间做事件研究时，应另行取得可靠带时区时间戳；本计算器仍只支持日级日期。

## 本版已实现

单季：本年累计减去前一季累计；一季度等于一季度累计。
TTM：上一年度全年 + 本年累计 - 上年同期累计；全年直接取全年。
净利率：归母TTM利润 / TTM营收，命名注明归母口径。
FCF：本项目以CFO减capex定义；capex字段需是正的购建长期资产现金支出，本版拒绝负支出和负营收。不适用于金融企业。
同比：仅正基数返回普通百分比；零/负基数单独标记扭亏、转亏、增亏或减亏。

### 输出范围与兼容性

v0.2.0的metrics.json对每个对象、币种、输入报告期输出26项：4个流量字段各自的ytd、quarter、ttm及三种同比，共24项；另有归母TTM净利率和TTM自由现金流。同比只比较上年同期间、同模式，不用TTM同比冒充单季同比。正利润转负利润也单列turn_to_loss，不显示普通增长百分比。

每项保留metric、value、unit、source_ids，并增加currency、status、missing_periods和fact_refs。fact_refs关联sources.csv的逐条记录，避免同一份报告内只有部分字段被核对时误标整份报告。value保持完整精度；HTML只做显示舍入。

旧的六项TTM指标名继续保留，但指标数量增加、sources.csv扩展为逐条事实记录；消费者应按metric与键名读取，不能依赖固定行数或列序号。manifest的schema_version为0.2.0，calculation_version记录当前程序版本（包括显示层修订），两者无需相等。

## 后续实现须遵循

PE用相应权益市值/归母TTM利润，负利润不定义PE；PB须匹配归母净资产。
股息率注明已支付/已宣告/预测；剔除重复股息和拆股干扰。
亏损公司、异常值处理、历史百分位窗口明确。
指数PE不简单平均个股PE；历史成分、权重与公告时点必须匹配。
同一数据商预计算指标保留supplier_metric，不以本项目自算值覆盖。
外币和不同准则的比较先统一可比口径；不能把汇率变化叫经营增长。

## 数据质量

重复、日期不合法、报告期晚于公告、未来公告、未知单位、币种混合、同日版本冲突分别检查。
缺失使对应指标不可用，不伪造一张完整表。源数据质量仍需人工/官方原文抽查，自动校验通过不证明输入内容本身真实。

quality.json区分missing_field（整个字段未提供）、missing_periods（缺少必要期间）、missing_value（该期间值为空）、missing_prior_year（缺少可比上年结果）、missing_dependencies（派生指标依赖缺失），并列出缺少的期间及分类汇总。零基数、扭亏、转亏等是特殊比较状态，不等同于取数失败。请求截至日期前没有任何可用输入时直接报错。

