# 文韬中文 Skills 合集 · Wentao Chinese Skills

文韬中文（Wentao Chinese）教学工作的 agent skill 合集。每个 skill 放在 `skills/` 下一个独立目录里，含 `SKILL.md`（做法说明）、`skill.yaml`（元数据）和它需要的脚本、模板与示例。

A collection of agent skills for teaching work at Wentao Chinese. Each skill lives in its own folder under `skills/` with a `SKILL.md`, a `skill.yaml`, and the scripts, assets and examples it needs.

## Skills

| 目录 | 做什么 |
| --- | --- |
| [hanzi-stroke-courseware](skills/hanzi-stroke-courseware/) | 给一张生字表，生成带笔顺动画的课件：一份可互动的单文件 HTML（笔顺动画、描红测验、配对游戏）和一份 16 页 PPTX（每字一页 GIF 动画、描红格、连线游戏、教师备注）。 |

后续 skill 会陆续加入这个仓库（备课、练习页、成绩与通知等方向），每个都按同样的目录规范放进来。

## 用法

1. 把某个 skill 目录拷到你的 AI 宿主的 skills 目录（见下一节的通用说明）。
2. 按该 skill 的 `SKILL.md` 准备输入（例如一份 `words.json` 生字表），照流程运行 `scripts/` 里的脚本即可。

## Use with any AI / 任何 AI 都能用

这些 skill 用的是开放的 Agent Skills 格式（`SKILL.md` + 脚本），不绑任何一家 AI。三种用法：

These skills use the open Agent Skills format (`SKILL.md` + scripts) and are not tied to any single AI vendor. Three ways to use them:

1. **支持 Agent Skills 的宿主 / Agent Skills hosts**（Claude Code、Codex、Cursor、Gemini CLI 等）：把 `skills/` 下的 skill 目录拷进该宿主的 skills 目录即可，宿主会自动读 `SKILL.md`。
   Copy the skill folder under `skills/` into your host's skills directory; the host picks up `SKILL.md` automatically.
2. **不支持 skill 的 AI / Any other AI**：把 `SKILL.md` 全文当说明书发给它读，让它照着运行 `scripts/` 里的四步脚本。运行环境要求（Python、依赖、联网）写在 `SKILL.md` 里。
   Paste the full text of `SKILL.md` as instructions and let the AI run the four scripts; runtime requirements are in `SKILL.md`.
3. **不想装环境 / Hosted version**：用托管服务 https://wentao-courseware-api.onrender.com — 网页版用 Google 登录；REST API 与 MCP（`https://wentao-courseware-api.onrender.com/mcp`）用同一把 key。
   Use the hosted service instead: web app with Google sign-in, plus a REST API and MCP endpoint sharing one API key.

## 数据与许可

- 笔顺动画库 Hanzi Writer 为 MIT 许可。
- 笔顺字形数据来自 Make Me a Hanzi，适用 Arphic Public License，课件成品中保留署名行。
- 拼音与释义由使用者自备，本管线不使用 Make Me a Hanzi 的字典部分（该部分为 LGPL 3.0+）。
- Arphic Public License 全文见 skills/hanzi-stroke-courseware/references/ARPHICPL.TXT，修改后的笔顺数据按该许可保持免费可得。
