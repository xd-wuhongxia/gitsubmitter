# Repository Memory

## Usage Documentation
- README 中新增的“使用说明”部分包含三个子章节：仓库分析流程、GitHub PR/MR 管理模块和常见使用场景，帮助用户理解启动步骤、token 配置和典型用法。

## 功能要点
- 应用支持本地路径、远程 Git URL 以及 `owner/repo` 简写输入，远程仓库会被临时克隆后进行统计分析。
- “MR 管理”依赖 GitHub Personal Access Token（需要 `public_repo` 或 `repo` 权限），获取到的 PR 数据会存储在 `mr_data.db` 中，方便后续查询和操作历史追踪。
- 前端通过全局 CSS 强制使用 `Noto Sans SC / PingFang SC / Microsoft YaHei` 等中文友好字体堆栈，避免不同平台出现中文字符渲染为方块。

