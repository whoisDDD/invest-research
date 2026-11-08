请测试 invest-research PR #3 的最新提交（feat/huangyang-p0，v0.4.1），记录commit；只测试，不改代码或合并。

重点复测上轮F1和两个显示问题：
1. research-demo切换“同日基期=100”，用真实鼠标点击基期重合点，必须同时看到营收600亿元、市值1000亿元的原始值和两个来源入口；Tab/Enter同样可用。禁止force点击、dispatchEvent或修改样式绕过命中。
2. 重用上轮已采集CSV和collection-audit.json，以原采集日2026-11-08生成新报告，无需重新联网取数。缺营收/单个市值点应显示快照卡，无虚构左轴，默认先看PE。
3. 320/360/390/414px下检查首屏能看到可用图表、图表无需内部横向滑动、单位/刻度可读，三页和证据仍可操作。分别记录桌面/手机视口截图。
4. 运行41项Python测试、旧9项UI与新7项research DOM测试、两份研究包独立复算。实际Chromium运行tests/test_research_browser.cjs；可用RESEARCH_HTML指定新demo，RESEARCH_REAL_HTML指定上一步新真实报告，CHROMIUM_PATH指定本机Chrome。

输出TEST_REPORT.md和local-test-results-p0-clickfix.zip，明确区分DOM通过和真实浏览器通过，附失败日志及截图。不打包凭据、node_modules或供应商原始批量响应，不把本轮界面修复写成P0完整复现。
