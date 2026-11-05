# 修复分支本地验收

在独立工作区检出origin/fix/report-metrics-provenance，记录commit和环境。先读AGENTS.md，本轮不改源码。

运行单元测试、doctor、demo，并用上次600519的标准CSV重新生成报告。重点核对：累计/单季/TTM和三种同比均已输出；特殊基数单列；CFO/资本开支缺失原因准确；HTML用亿元/百分比、逐项来源可跳转、未核对数据不会变成已核实；日期横轴按真实间隔、缺失季度断线；研究包能在脱离仓库的目录独立复算。原始日期不应被自动增减一天。

为同一报告的少量字段补充verification和evidence_locator等可选列，确认只对应字段显示输入核验记录；保留一份无新列的旧CSV验证兼容性。对已安装westock Skill用doctor --skill-dir显式检查，确认工具发现与授权状态分开。

生成TEST_REPORT.md：commit、命令与输出、通过/失败/未测、复现步骤；附前后截图及日志，打包local-test-results.zip回传，排除凭据与私人数据。不要把回传包提交到公开仓库。
