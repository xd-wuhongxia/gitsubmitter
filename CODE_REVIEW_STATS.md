# Code Review 统计功能

## 📋 功能概述

Code Review 统计功能通过分析Git commit message中的特定关键词（如机器人名称），统计代码审查活动，帮助团队了解代码审查的覆盖率和活跃度。

## 🎯 主要特性

### 1. 可配置的关键词监控
- 支持自定义关键词列表
- 默认包含常见的机器人名称：
  - `pr-agent` - PR Agent 机器人
  - `codiumai-pr-agent` - CodiumAI PR Agent
  - `github-actions[bot]` - GitHub Actions 机器人
  
### 2. 多维度统计分析
- **Review覆盖率**：计算包含关键词的提交占总提交的百分比
- **关键词出现次数**：统计每个关键词在commit message中的出现频率
- **作者统计**：按作者统计Review次数
- **时间趋势**：展示Review活动随时间的变化趋势
- **最近记录**：显示最近20条Review记录

### 3. 可视化展示
- 📊 关键指标卡片展示
- 📈 柱状图显示关键词分布
- 📉 折线图展示Review趋势
- 📋 数据表格详细列表

## 🚀 使用方法

### 配置关键词

1. 进入主页面，点击 **"🔍 Code Review统计"** 标签页
2. 展开 **"⚙️ Code Review 配置"** 部分
3. 在文本框中输入关键词，每行一个
4. 点击 **"💾 保存配置"** 保存设置

示例配置：
```
pr-agent
codiumai-pr-agent
github-actions[bot]
codecov
sonarcloud[bot]
my-review-bot
```

### 查看统计

配置完成后，系统会自动分析commit历史：

1. **统计概览**：查看总提交数、已Review提交数、Review覆盖率和Review总数
2. **关键词出现次数**：查看每个关键词的使用频率和占比
3. **作者Review统计**：了解各作者的Review活动
4. **最近Review记录**：查看最近的Review活动详情
5. **Review趋势分析**：观察Review活动的时间趋势

## 📁 配置文件

配置会自动保存到 `code_review_config.json` 文件中：

```json
{
  "keywords": [
    "pr-agent",
    "codiumai-pr-agent",
    "github-actions[bot]"
  ],
  "enabled": true
}
```

## 💡 工作原理

系统通过以下步骤进行统计：

1. 获取指定时间范围内的所有commit记录
2. 检查每个commit message是否包含配置的关键词
3. 统计包含关键词的commit数量和分布
4. 按作者、时间等维度进行聚合分析
5. 生成可视化图表和统计报告

## 🔧 高级功能

### 启用/禁用功能
可以通过配置页面的复选框快速启用或禁用Code Review统计功能。

### 重置为默认配置
点击 **"🔄 重置为默认"** 按钮可以快速恢复到默认的关键词配置。

## 📊 统计指标说明

- **总提交数**：当前时间范围内的所有提交数量
- **已Review提交**：commit message中包含任一关键词的提交数量
- **Review覆盖率**：已Review提交 / 总提交数 × 100%
- **Review总数**：所有关键词在commit message中出现的总次数

## ⚠️ 注意事项

1. 关键词匹配不区分大小写
2. 关键词会在整个commit message中进行搜索
3. 一个commit可以被多个关键词匹配
4. 确保关键词准确反映实际的Review工具或流程
5. 定期检查和更新关键词列表以保持准确性

## 🎨 示例场景

### 场景1：监控PR Agent使用情况
```
关键词配置：
- pr-agent
- codiumai-pr-agent

查看统计了解：
- PR Agent在项目中的使用频率
- 哪些作者的提交包含PR Agent Review
- PR Agent使用趋势是否在增长
```

### 场景2：多机器人环境
```
关键词配置：
- pr-agent
- github-actions[bot]
- codecov
- sonarcloud[bot]

分析每个机器人的：
- 使用频率和占比
- 活跃时间段
- 覆盖的代码范围
```

## 🔗 相关功能

- **MR管理**：管理Pull Request和pr-agent结果
- **提交分析**：查看详细的commit历史
- **作者分析**：了解团队成员的贡献情况
- **时间分析**：观察项目活动趋势

## 📝 更新日志

### v1.0.0 (2025-10-27)
- ✨ 首次发布Code Review统计功能
- 🎨 支持可配置关键词监控
- 📊 多维度统计分析
- 📈 可视化趋势展示
- 💾 配置持久化保存

