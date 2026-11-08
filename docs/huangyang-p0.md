# 黄阳研究复现：P0测试说明

## 产品目标与当前验收状态

目标是复现视频中的市场/指数/行业研究：数据→样本与指标→图表→有证据的观察→人工判断。现有公司财报看板仍保留，但它不等同于这个目标。

**v0.4.1是可测试的研究基础版本，尚未通过“忠实复现原视频”的最终验收。** 已完成14页口径登记、研究输入契约、两种图表及证据交互、公开来源采集和真实样本验证。原视频的数据供应商、历史样本、营收算法和参考线公式仍有缺口；真实营收/市值八年趋势尚未取得，不能把合成演示当作完成证明。

原视频：[2026年三季度，上市公司财报，汇总数据分析](https://www.bilibili.com/zh-Hans/video/BV16Jx96JEpV/)，黄阳的学习分享。2026-11-06逐页核对；时间为观察点，不是精确切页时间。结构化记录在 `invest_research/ui/video-methods.json`，可直接从报告“视频与口径”页查看。

## 已知与未确认

| 项目 | 已直接观察到的内容 | 尚不能推定的内容 |
|---|---|---|
| 经营指标 | 柱图图例写“总营收” | 不是净利润；TTM/累计/年度算法未显示 |
| 定价指标 | 红色折线写“总市值” | 不能以指数点位或成交额替代；部分金额轴无单位 |
| 样本范围 | A股、沪深300、科创50、中证1000、半导体、银行、中证红利 | 作者历史样本/行业分类清单未取得 |
| 估值 | PE序列；部分图标“近八年数据” | PE算法、亏损股处理、数据频率未确认 |
| 参考线 | 沪深300为11.17/12.52/13.87 | 对称不证明公式是均值±标准差 |
| 作图软件 | 多页保留系统弹窗标题和关闭按钮 | 软件/数据商身份未确认 |

第1和14页为整体市场除银行PE；第2页整体营收/市值；第3/4页沪深300；第5/6页科创50；第7/8页中证1000；第9页半导体营收/市值；第10/11页银行；第12/13页中证红利。第9页没有独立PE图。原视频讲解和参考线属于研究对象，不作为已验证市场判断。

## 运行与体验

基础演示仅用Python标准库：

```sh
python -m invest_research research-demo --out runs/research-demo
```

浏览器打开 `runs/research-demo/report.html`。全部是虚构市场数据。入口分成图表研究、数据证据、视频与口径三个页面；手机底部固定导航。双轴原值与同日基期=100可切换，日期联动，数据点可点开证据。PE序列独立选择；视频线默认关闭，开启后明确注明口径待核实。

研究输出目录必须为空，重复测试请另用新目录，防止混入旧数据。

## 真实数据采集

腾讯官方Skill已优先调查并实测：`index constituent`返回成分，`kline`返回OHLC/成交量/成交额等。文档列有申万行业聚合财务及估值，但不能由此声称覆盖沪深300八年营收/总市值/PE。同花顺iFinD需要使用者自己的数据权限，本轮未配置，也未冒称联调成功。

因此增加一个**明确记录来源切换的公开数据采集器**，不伪装成腾讯或同花顺连接器：

| 数据 | 真实来源与映射 | 结果/限制 |
|---|---|---|
| 历史PE | 中证指数官方 `index-perf`，`peg`；AKShare将该字段映射为滚动市盈率 | 2026-11-08实测返回1,938条；不能因字段名叫peg就当成成长调整PEG |
| 样本清单 | 中证官方000300closeweight.xls，按文件真实日期识别 | 2026-10-30快照300只；仅这一日期，不能回填八年历史成员 |
| 逐股营收 | 东方财富RPT_LICO_FN_CPD，TOTAL_OPERATE_INCOME；分页完整性、代码/期间唯一性检查 | `2026Q3 + 2025全年 - 2025Q3`，逐股算TTM后加总；元→图表亿元 |
| 总市值 | 中证官方000300factsheet.pdf第1页“市值(亿元)→成分股总市值” | 只在PDF日期与成分权重日期完全一致时导入；不取“指数市值” |
| 真实样本状态 | 2026-11-08本环境实测 | 299/300家公司TTM依赖齐全；688981本期营收缺失，因此合计留空 |

基础历史PE采集不需要附加依赖。`--as-of`必须填实际采集当天，不能将今天下载的修订数据声称为历史当时可见：

```sh
python -m invest_research collect-csi300 --as-of 2026-11-08 --out data/research-csi300.csv
```

若要包含财报和总市值快照，使用可选依赖（不影响基础演示）：

```sh
python -m pip install -e ".[research-data]"
python -m invest_research collect-csi300 --as-of 2026-11-08 --with-finance --out data/research-csi300.csv
python -m invest_research research --input data/research-csi300.csv --as-of 2026-11-08 --audit data/collection-audit.json --out runs/csi300-research
```

以后测试时把上述日期换成实际采集日。当前财报样板固定为2026Q3，不自动假设未来季度已适配。首次财报采集约三十多次公开分页请求；每次超时30秒，最多3路并发。先保存PE成功结果，财报失败会明确退出，不能把PE成功等同完整采集成功。重跑复用同日已校验缓存，不偷偷切换来源。跨日独立缓存以保留历史快照。

`data/raw/`保存原始字节、请求URL、抓取时间与SHA256；`collection-audit.json`保存300只样本、逐股依赖、公告/更新日期和缺失清单。原始响应不进入公开仓库。

## 输入契约与计算

研究CSV与公司财报facts.csv是两种不同粒度，不能直接混用。列定义：

| 列 | 要求 |
|---|---|
| series_id / label | 唯一研究序列及名称；换口径须另建序列 |
| date / available_at | 观测日期及这条数据最早可用日；任一个晚于研究截至日则排除 |
| metric | revenue / market_cap / pe |
| value / unit | 原始完整值；金额CNY元，PE为multiple；缺失填空 |
| basis | 收入ttm；市值total；PE为provider_ttm（来源预计算，不冒称本项目自算） |
| universe_id | 历史当时成分与固定成分明确区分；同指标同序列禁止静默换样本 |
| source_url / evidence_locator | 无凭据HTTP(S)链接与字段/表格定位 |
| missing_reason | 空值必填；不补零、不插值 |

财报固定样本快照和中证历史PE分成不同序列，不能拿一个的均值/分位解释另一个。配对比较只使用同日、同universe_id的有效营收和总市值，至少2对且基期大于零。基期=100只是视觉换算；两条曲线相交不产生交易信号。

历史PE位置采用 `count(PE≤latest)/N×100`（并列计入），注明完整输入区间。图中的算术均值随可见区间变化，完整区间的事实摘要不随筛选变化，两者在页面明确说明。缺失PE和非正PE不参与统计。不同来源的估值曲线不拼接，未实现亏损股自行处理或整体法PE计算。

`analysis.md`输出数据事实、缺口、待验证解释、人工判断四块。目前没有自动调用LLM；ChatGPT或本地Agent可读取研究包，在来源支持范围内补充解释，并保留人的判断。不能把固定模板称作已经接入AI模型。

## 验证与回传

```sh
python -m unittest discover -s tests -v
python -m invest_research demo --out runs/demo
python -m invest_research research-demo --out runs/p0-demo
npm ci --ignore-scripts
npm run test:ui
npm run test:research
python runs/p0-demo/recompute.py
```

两个Node命令是DOM/交互逻辑检查，不等于浏览器渲染。`tests/test_research_browser.cjs`另有可选真实Chromium冒烟：需自行准备Playwright和浏览器，可用CHROMIUM_PATH指定已安装Chromium；云端尝试仍受socket权限限制；用户回传的v0.4.0本地Chromium测试已实际运行，发现参考线与重合点拦截鼠标的缺陷。v0.4.1已改为按日期统一命中并显示全部来源，真实浏览器命中及手机显示需要本地复测。

研究包包含HTML、CSV、JSON、观察文字、方法、确定性计算源码、复算脚本和哈希清单。解压后运行 `python recompute.py`，核对CSV重算结果与保存JSON一致；该检查证明计算一致，不证明供应商数据已与每家公司原文核对。明确传 `--audit`时也包含逐股采集依赖。

## P0完成条件

1. 本地可以从取数到报告完整运行，得到可复查的结果与失败原因。
2. 沪深300历史营收/总市值样本、日期、单位、财务算法被确认，取得足够长度的真实序列。
3. 原视频PE和参考线口径能说明并复算，或明确取得作者原始数据用于比对。
4. 两张真实研究图及其观察可追溯并经本地验收。

**第2、3、4项仍未完成。** 本次不通过删掉这几项、回填当前成分、从图上猜数或合成曲线来宣告P0结束。

## 原始来源与接口依据

- [中证历史指数接口](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000300&startDate=20181109&endDate=20261106)
- [中证沪深300概况](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300factsheet.pdf)
- [中证样本权重](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/closeweight/000300closeweight.xls)
- [AKShare中证接口实现](https://github.com/akfamily/akshare/blob/main/akshare/index/index_stock_zh_csindex.py)
- [AKShare成分接口实现](https://github.com/akfamily/akshare/blob/main/akshare/index/index_cons.py)
- [AKShare东方财富业绩报表接口实现](https://github.com/akfamily/akshare/blob/main/akshare/stock/finance/stock_yjbb_em.py)
- [腾讯官方SkillHub说明](https://skillhub.cn/skills/tencent-adm/westock-data)
- [同花顺iFinD官方入口](https://mcp.51ifind.com/)

## 本地结果与0.4.1界面修复

回传报告记录41项Python测试在两种Python版本通过、13项DOM测试通过、26项独立数据核验通过；真实浏览器27项断言中1项失败，定位为基期点的两层遮挡。这些结果支持基础数据链路，不能证明原视频完整复现。

0.4.1中，同日指标共用一个互不重叠的日期点击区域，参考线不接收鼠标；弹窗保留当天全部指标的原始值和独立来源。单点显示快照、无值轴不绘制；有数据趋势的图优先，研究摘要默认折叠；手机取消570px最小图宽，按实际容器绘图。桌面导航取消粘顶，避免滚动命中被导航覆盖；手机保留底部导航。

新旧版本使用同一回传CSV生成的research.json完全一致。本轮未改供应商接口、财务计算或缺口判定。针对性测试见[prompts/test-p0-clickfix.md](../prompts/test-p0-clickfix.md)，复测可重用原采集日的数据，无需重新联网取数。
