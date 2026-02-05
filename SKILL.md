---
name: financial-report-to-notebookllm-skill
description: 自动从巨潮资讯 (A股)、HKEX (港股) 和 SEC EDGAR (美股) 下载上市公司报表并上传至 NotebookLM 进行深度分析。支持年报、季报，并自动配置专业财务分析提示词。
---

# Financial Report to NotebookLM

## 概述

该 Skill 旨在帮助投资者自动获取全球主要市场（A股、港股、美股）上市公司的财务报告，并无缝集成到 Google NotebookLM 中。它不仅完成下载和上传，还根据市场类型自动配置定制化的“财务分析师”提示词，利用 AI 进行深度基本面研究。

## 使用场景

- **A股研究**：用户输入“贵州茅台”或“600519”。
- **美股研究**：用户输入“AAPL”或“NVDA”。
- **港股研究**：用户输入“00700”或“09988”。
- **深度分析**：用户想要基于最新财报进行 AI 辅助的财务分析。

## 核心功能

1. **智能市场识别**：根据输入的代码或名称自动识别市场（6位数字为A股，5位数字为港股，纯字母为美股）。
2. **多源下载**：
   - **A股**：从巨潮资讯下载最近 5 年年报及当年定期报告。
   - **港股**：从 HKEX 下载最新公告并转换为 Markdown。
   - **美股**：从 SEC EDGAR 下载最新 10-K 和 10-Q 报表。
3. **NotebookLM 集成**：
   - 自动创建以公司名称命名的笔记本。
   - 自动上传所有报告（支持 PDF 和 Markdown）。
4. **角色配置**：
   - 自动应用位于 `assets/` 目录下的系统提示词（区分中外市场），如 `financial_analyst_prompt.txt`。

## 使用说明

### 1. 身份验证 (首次使用必读)

该 Skill 依赖 `notebooklm-py`。在首次运行前，**必须**在终端手动完成 Google 账号登录：

```bash
cd /Users/shi/workspace/my-skills/.gemini/skills/financial-report-to-notebookllm-skill
.venv/bin/notebooklm login
```
*注：这将打开浏览器窗口。请登录后在终端按回车确认。*

### 2. 运行主脚本

使用虚拟环境中的 Python 运行：

```bash
/Users/shi/workspace/my-skills/.gemini/skills/financial-report-to-notebookllm-skill/.venv/bin/python /Users/shi/workspace/my-skills/.gemini/skills/financial-report-to-notebookllm-skill/scripts/run.py <股票代码或名称>
```

示例：
- **A股**：`.../run.py 600519` 或 `.../run.py 贵州茅台`
- **美股**：`.../run.py TSLA` 或 `.../run.py NVDA`
- **港股**：`.../run.py 00700` (腾讯)

### 3. 反馈结果

向用户提供：
- ✅ 识别到的市场及公司名称。
- 📦 成功下载并处理的报表清单。
- 📚 NotebookLM 链接或 ID。
- 💡 提示已应用针对该市场的专业财务分析模型。

## 常见问题

- **识别错误**：如果美股代码被误认，请确保输入的是纯大写字母。
- **未登录 (Auth missing)**：手动运行 `.venv/bin/notebooklm login`。
- **HKEX/SEC 访问受限**：可能需要检查网络代理设置。
