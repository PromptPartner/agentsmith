<div align="center">
  <img src="site/assets/promptpartner-mark-amber.svg" width="72" height="72" alt="PromptPartner mark">
  <p>
    <a href="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml"><img alt="Verification" src="https://github.com/PromptPartner/agentsmith/actions/workflows/verify.yml/badge.svg?branch=master"></a>
    <a href="https://github.com/PromptPartner/agentsmith/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/PromptPartner/agentsmith"></a>
    <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-14213D.svg"></a>
  </p>
  <p>
    <a href="README.md">English</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <strong>简体中文</strong>
  </p>
</div>

# AgentSmith

**先验证，再完成。** 为 AI 智能体提供项目规则、完成标准，以及证明工作成果的方法。

AgentSmith 会在项目中安装一套共享的工作约定和一个工作配置文件。智能体会获得明确的边界，运行相关检查，实际走通操作流程，记录证据，并留下可供后续会话验证的交接记录。对外部系统的写入操作始终由您掌控。

![AgentSmith flow: project rules and profile, bounded agent work, automated checks and real-path exercise, evidence, then handoff and resume.](site/assets/agentsmith-flow.svg)

## 设置 AgentSmith

请选择以下两种方式之一。它们使用相同的引导式设置，并生成相同的项目文件。

### 1. 手动设置

1. 从[最新版本](https://github.com/PromptPartner/agentsmith/releases/latest)下载适用于 macOS、Windows 或 Linux 的已签名安装程序。
2. 打开终端并运行 `agentsmith`。
3. 回答向导中的问题。AgentSmith 会在写入任何内容之前显示完整计划。

向导既可以配置现有项目，也可以为新项目创建空文件夹并初始化 Git。独立应用已经包含运行环境，无需安装 Python。

### 2. 让您的智能体安装

将以下内容粘贴到 Claude Code、Codex 或其他编程智能体中：

```text
Install AgentSmith for this project. Follow the official agent guide at
https://github.com/PromptPartner/agentsmith/blob/master/AGENT-INSTALL.md
Inspect the project first, explain your profile recommendation in plain language,
show me the exact installation plan, and ask once before applying it.
```

智能体会检查仓库，但不会运行项目代码；它会根据检查结果推荐配置文件、预览由 AgentSmith 管理的文件、安装 AgentSmith，并运行诊断检查。

> 从源代码构建 AgentSmith 适用于贡献者和高级自动化场景。请参阅[安装参考](INSTALL.md)。

## 新项目还是现有项目？

| 起点 | AgentSmith 会做什么 | AgentSmith 不会做什么 |
|---|---|---|
| 现有项目 | 检查文件、推荐配置文件、保留不属于 AgentSmith 的内容，并添加托管规则和验证结构。 | 检查时不会运行项目，也不会替换现有项目配置。 |
| 新项目 | 创建或验证一个空文件夹，初始化 Git，然后添加 AgentSmith。 | 不会选择或生成应用框架。设置完成后，您的智能体可以继续构建应用。 |

默认使用项目级设置，因为规则会随仓库一起保存，协作者也可以审查这些规则。面向当前用户所有项目的全局核心规则位于 **高级选项** 中。分层设置会将该全局核心规则与简短的项目专用配置文件组合起来。请参阅[项目级、用户全局和分层设置](INSTALL.md#where-the-rules-live)。

## 工作配置文件

配置文件会告诉智能体，当前工作达到什么标准才算“完成”。向导会推荐一个配置文件，并显示支持该建议的文件证据。您可以接受建议，也可以查看完整列表。

| 配置文件 | 适用工作 | 主要证明 |
|---|---|---|
| `software-dev` | 功能开发、问题修复、重构、应用、库和产品界面 | 构建、检查、测试、安全审查、实际运行 |
| `devops-setup` | 安装程序、CI、容器、配置和部署 | 试运行、幂等性、回滚、实际部署流程 |
| `marketing-outreach` | 营销活动、电子邮件、新闻简报、落地页文案和 CRM 工作 | 受众与事实审查、链接、渲染、发送审批 |
| `document-creation` | 报告、提案、规格说明、手册和 Wiki | 来源准确性、结构、链接、成品文件审查 |
| `data-crunching` | 数据清理、分析、SQL、指标和 ETL | 可复现性、汇总结果、边界情况、输出检查 |
| `general-admin` | 分类处理、日程安排、组织整理、总结和日常运营 | 完整性、输出忠实度、目标位置和审批检查 |
| `deep-research` | 尽职调查、市场研究和带引用的调研 | 来源质量、论点覆盖、引用、综合结论审查 |
| `creative-design` | 图表、演示文稿、品牌素材、图像和视频 | 需求简报、视觉与导出审查、无障碍、品牌一致性 |
| `security-audit` | 威胁建模、安全审查、渗透测试和 IAM 审计 | 复现、严重性证据、修复、复测 |

`autonomous-loops` 是用于定时任务或无人值守工作的高级修饰配置。请将它与主要工作配置文件组合使用，不要单独使用。请参阅[配置文件指南](docs/07-how-to-pick-a-profile.md)，了解容易混淆的情况、配置切换和叠加方式。

## 安装的内容

- `AGENTS.md` 是项目的标准工作约定。Claude Code 还会获得自动生成的 `CLAUDE.md`。
- `.harness/verify.conf` 定义该项目要执行的实际检查。
- `.agentsmith/state.json` 只记录 AgentSmith 管理的设置，因此更新或移除 AgentSmith 时会保留其他内容。
- 可选的技能、MCP 服务器和钩子位于默认折叠的高级步骤中。

默认采用谨慎的权限模式。AgentSmith 绝不会把已连接的外部服务视为写入授权。

## 查看证据

[第一个已验证循环](docs/demos/first-verified-loop/README.md)记录了修复前失败的测试、修复后通过的验证、一次真实命令运行、结果凭证，以及可恢复工作的交接记录。[支持注册表](config/agents.json)区分了指令支持和经过测试的原生行为。

## 文档与社区

- [安装参考](INSTALL.md)
- [文档索引](docs/README.md)
- [验证如何成为证据](docs/03-verify-means-evidence.md)
- [智能体兼容性](docs/22-compatibility-contract.md)
- [参与贡献](CONTRIBUTING.md)和[获取支持](SUPPORT.md)
- [安全政策](SECURITY.md)和[行为准则](CODE_OF_CONDUCT.md)

采用 MIT 许可证。由 [PromptPartner](https://promptpartner.ai/) 构建。
