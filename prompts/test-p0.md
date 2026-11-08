请在 invest-research 的 feat/huangyang-p0 分支测试，不修改代码或合并PR。先读 AGENTS.md 和 docs/huangyang-p0.md，记录分支和commit。

1. 运行Python测试、旧demo和research-demo，用新的空输出目录。安装既有Node开发依赖后运行 test:ui、test:research；解压research review_pack，在仓库外执行recompute.py。
2. 浏览器实际检查两张研究图、基期=100、日期筛选、证据弹窗、导出CSV、三页导航；手机宽度390px检查操作与溢出。记录截图，区分DOM通过与实际渲染通过。
3. 以今天为as-of运行collect-csi300；条件允许加--with-finance，然后research附带--audit生成真实报告。检查300只覆盖、缺失是否保留为空、PE来源/日期与两套样本口径；网络失败记为未通过，不能用合成数据代替实测。
4. 生成 TEST_REPORT.md，写通过/失败/未测、复现命令、日志、数据缺口和体验问题。将报告、截图、真实研究review_pack与collection-audit.json打包为local-test-results-p0.zip回传，排除凭据、node_modules和供应商原始批量响应。不要将可测试版本写成已经忠实复现原视频。
