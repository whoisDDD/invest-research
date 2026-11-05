# 修复分支本地验收

在独立工作区检出origin/fix/report-readability，记录commit和环境。先读AGENTS.md，本轮不改源码。本分支已升级为v0.3.0交互看板，旧静态报告入口为static_report.html。

运行单元测试、doctor、demo，并用上次600519的标准CSV重新生成报告。重点核对：累计/单季/TTM和三种同比均已输出；特殊基数单列；CFO/资本开支缺失原因准确；HTML用亿元/百分比、逐项来源可跳转、未核对数据不会变成已核实；日期横轴按真实间隔、缺失季度断线；研究包能在脱离仓库的目录独立复算。原始日期不应被自动增减一天。

为同一报告的少量字段补充verification和evidence_locator等可选列，确认只对应字段显示输入核验记录；保留一份无新列的旧CSV验证兼容性。对已安装westock Skill用doctor --skill-dir显式检查，确认工具发现与授权状态分开。

本轮重点：直接双击report.html，离线切换两家合成公司、报告期、4/8/全部期数和财务口径；检查六张卡片、四组图表、图例开关、悬停数值、点击证据面板、明细搜索排序和CSV导出。测试深浅主题，以及1440/1280/390px下的布局。缺失断线、负现金流、不同币种分组和完整原始精度均应保留。用上次真实CSV重跑并与旧结果比较，metrics.json、quality.json、sources.csv不应变化；demo现在改用新的丰富合成样例，数量变化正常。static_report.html应仍可打开，研究包应包含两个HTML且可脱库复算。

如具备Node，可选运行npm ci --ignore-scripts及npm run test:ui；这是开发检查，不是运行HTML的前提。截图验收请确认图表不溢出、轴标签可读、来源面板可关闭且焦点返回、导出文件能打开。

生成TEST_REPORT.md：commit、命令与输出、通过/失败/未测、复现步骤；附前后截图及日志，打包local-test-results.zip回传，排除凭据与私人数据。不要把回传包提交到公开仓库。
