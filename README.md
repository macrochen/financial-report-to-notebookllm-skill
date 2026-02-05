# Global Financial Report to NotebookLM

自动从全球主要市场（A股、港股、美股）下载上市公司财报，并上传至 Google NotebookLM，利用 AI 驱动的“财务分析师”角色进行深度分析。

> 💡 **提示**: 本工具会自动为 NotebookLM 配置专业的“财务分析师”角色，帮助你进行财报排雷、估值分析和商业模式拆解。针对中外市场采用不同的分析提示词。

## ✨ 核心功能

- 🌍 **全球支持**: 
  - **A股**: 自动下载巨潮资讯 (cninfo) 近 5 年年报 + 当年定期报告。
  - **港股**: 自动抓取 HKEX 最新公告并转换为易读的 Markdown。
  - **美股**: 自动从 SEC EDGAR 获取最新的 10-K 和 10-Q 报表。
- 🤖 **AI 分析师**: 根据市场自动植入专用 System Prompt，进行风险检测、估值分析和商业模式研判。
- 📦 **全自动流程**: 一键完成下载、市场识别、笔记本创建、角色配置和文件上传。
- 🧹 **自动清理**: 上传完成后自动清理临时文件，保持系统整洁。
- 🔐 **稳定登录**: 使用 `notebooklm-py` 确保鉴权稳定可靠。

## 🚀 使用方法

### 安装步骤

1. **安装 Skill**
   在你的 Agent 终端中运行以下命令（或直接让 Agent 处理）：

   ```bash
   npx skills add jarodise/financial-report-to-notebookllm-skill
   ```

2. **安装依赖** (首次运行)
   进入目录并运行安装脚本：

     ```bash
     cd financial-report-to-notebookllm-skill && ./install.sh
     ```

3. **认证登录**
   如果你之前没用过 NotebookLM，请先登录：

   ```bash
   .venv/bin/notebooklm login
   ```

### 运行工具

你可以直接在终端运行工具：

```bash
# A股：按代码或名称
python3 scripts/run.py 600519
python3 scripts/run.py "贵州茅台"

# 美股：按 Ticker
python3 scripts/run.py TSLA

# 港股：按 5 位代码
python3 scripts/run.py 00700
```

## 📂 项目结构

```
financial-report-to-notebookllm-skill/
├── package.json        # 项目元数据
├── SKILL.md            # LLM 指令和上下文说明
├── install.sh          # 依赖安装脚本
├── scripts/
│   ├── run.py          # 主流程控制脚本（市场识别 + 编排）
│   ├── download.py     # 巨潮资讯 (A股) 下载逻辑
│   ├── hk_downloader.py # HKEX (港股) 下载逻辑
│   ├── us_downloader.py # SEC (美股) 下载逻辑
│   └── upload.py       # NotebookLM 交互逻辑
└── assets/
    ├── financial_analyst_prompt.txt     # A股/港股分析师提示词
    └── us_financial_analyst_prompt.txt  # 美股分析师提示词
```

## ⚠️ 免责声明

本工具仅供教育和研究使用。请确保遵守各交易所信息披露平台和 Google NotebookLM 的服务条款。AI 提供的财务分析仅供参考，不构成任何投资建议。