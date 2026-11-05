# 从 Google Drive 启动投资研究工作流

交付日期：2026-11-05；版本：v0.1.0。Drive快照包含完整项目源码和Git历史备份；后续源码更新以 https://github.com/whoisDDD/invest-research 为准。

## 取得项目

1. 下载 `invest-research-v0.1.0-20261105.zip`，解压到本地独立目录。
2. 打开 `invest-research/README.md`。所有命令均在包含该README的项目目录执行。
3. 用 WorkBuddy、OpenCode Desktop 或 DSH 打开该目录，让它先读 `AGENTS.md`。
4. 目录中的 `repo.bundle` 是额外的Git历史备份，普通使用无需操作。若需要可提交的Git工作区，在压缩包外运行 `git clone /实际路径/invest-research/repo.bundle invest-research-work`。克隆出来的工作区与直接解压项目二选一作为日常目录。

## 首次运行

需要Python 3.10及以上，演示无需额外依赖。Linux通常用 `python3`，Windows通常用 `python` 或 `py`。

```bash
python -m unittest discover -s tests -v
python -m invest_research doctor
python -m invest_research demo --out runs/demo
```

用浏览器打开 `runs/demo/report.html`；把 `runs/demo/review_pack.zip` 交给ChatGPT复核。演示全部使用合成数据，并未接入任何真实证券账户或数据商。

Drive文件夹中的 `demo-report.html` 是预先生成的同一演示报告，下载后用浏览器打开即可预览。

## 可复制给本地Agent的启动任务

```text
这是投资研究工作流项目。先读取AGENTS.md、README.md、docs/framework.md、docs/providers.md以及prompts/bootstrap.md。运行doctor、单元测试和离线demo，保留原有项目结构。检查我已经授权的官方金融工具，优先腾讯westock-data Skill/CLI或同花顺iFinD MCP，实际枚举工具、核对账号权限和返回字段。先对一家公司做真实数据验收：记录来源、报告期、公告日、币种和单位，核对营收、归母利润和经营现金流，再映射成标准CSV，调用现成程序生成报告和review_pack。遇到授权步骤只停该步骤，其余准备继续。不要把合成演示当成真实取数，也不要凭空编写接口或认证参数。最后说明已执行结果和未联调项目。
```

## ChatGPT与本地Agent如何配合

- 本地Agent负责实际数据工具、原始证据留存、统一字段、运行计算和生成研究包。
- ChatGPT读取研究包，核查数据口径、原始披露与解释，给出初步分析和需要人工判断的事项；能运行代码的会话可以复算。
- 人负责估值假设、投资逻辑、仓位与最终决定，按 `examples/decision_journal.md` 留下判断记录。

## 本版边界

- 已实现：完整研究框架、数据契约、自然年累计财务流量计算、质量检查、基础HTML报告、研究包导出和11项测试。
- 待联调：真实数据商账号、三款本地客户端、机器导出字段映射。
- 待扩展：批量历史数据库、交互图表、行情估值、银行专用计算、美股非自然财年。

Drive用于交付源码快照。下载解压后的本地目录才是执行工作区；Drive里保留压缩包不会自动运行、定时更新或与本地双向同步。后续可直接把同一Git历史迁移到GitHub。
