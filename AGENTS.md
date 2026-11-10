# AGENTS.md — 给任何 AI 的仓库导览 / Guide for any AI agent

这是什么：文韬中文（Wentao Chinese）的教学 skill 合集。目前有一个 skill：根据老师给的生字表，自动生成带笔顺动画的中文课件（互动 HTML + PPTX）。

What this is: a collection of teaching skills for Wentao Chinese. It currently contains one skill that turns a teacher's character list into Chinese lesson courseware with stroke-order animation (interactive HTML + PPTX).

## Skill 在哪 / Where the skill lives

- `skills/hanzi-stroke-courseware/` — 做法说明是该目录的 `SKILL.md`，先读它。
- 输入是一份 `words.json` 生字表（格式见 `skills/hanzi-stroke-courseware/examples/words-sample.json`）。
- 四步管线都在 `skills/hanzi-stroke-courseware/scripts/` 里：取笔顺数据 → 拼 HTML → 生成 GIF → 拼 PPTX。
- 运行环境要求（Python 版本、依赖、联网）在 `SKILL.md` 的 “Runtime requirements” 一节里，任何 AI 通用，没有厂商专属假设。

## 不装本地环境的用法 / Hosted options (no local setup)

托管服务地址 / Hosted service: https://wentao-courseware-api.onrender.com

- **网页版 / Web app**：打开上面的地址，用 Google 登录，贴生字表即可生成和下载课件。适合普通老师。
- **REST API**：`POST /generate` 提交生字表（请求头 `X-API-Key`），再用 `GET /jobs/{job_id}` 查状态、`GET /jobs/{job_id}/files/lesson.html` 或 `lesson.pptx` 下载。
- **MCP**：MCP 地址是 `https://wentao-courseware-api.onrender.com/mcp`，与 REST 用同一把 key。支持 MCP 的 AI 客户端连上后可以直接调用生成工具。

## 许可 / Licenses

- 笔顺动画库 Hanzi Writer：MIT。
- 笔顺字形数据 Make Me a Hanzi：Arphic Public License（全文在 `skills/hanzi-stroke-courseware/references/ARPHICPL.TXT`），分发课件或数据时保留署名。
