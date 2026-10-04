# qzone-export

> 把 QQ 空间的**说说**和**日志**，连同**图片、评论、转发、定位**，导出成本地 Markdown。
> QQ 空间没有官方导出入口，这是目前比较完整的一条民间路线。

**English:** Export your Qzone (QQ空间) posts — shuoshuo (说说) and blog posts (日志) — into a self-contained local Markdown archive, with pictures, comments, reposts and location data preserved. Ships as an Agent Skill plus a set of scripts, and follows a written standard operating procedure.

一次真实导出：**1573 条说说 + 16 篇日志 + 722 张图片**，输出 20840 行、1.04 MB 的 Markdown，时间跨度 2009–2025。

---

## 为什么需要它

QQ 空间是很多人的青春硬盘，但它：

- **没有导出功能**。官方不提供打包下载。
- **内容在缩水**。早年引用的第三方图床（蚂蜂窝、腾讯微博图床等）已经成片下线——实测 732 张图里有 10 张永久丢失，且每天都在增加。
- **格式是私有的**。说说用了 `[em]e113[/em]` 表情码、`@{uin:...,nick:...}` 这种内嵌标记，直接复制出来没法看。
- **可能说没就没**。一旦账号出问题或产品关停，十几年的记录就没了。

这个工具把它变成**一份纯文本的 Markdown + 一个 images 文件夹**，你可以放进 Obsidian、提交到私有 Git、或者压了扔进网盘——不依赖 QQ 是否还活着。

---

## 成品长什么样

`examples/example-output.md` 是**工具的真实输出**（用虚构数据生成，不包含任何真实信息）。每段长这样：

```markdown
## 2025-12-26 22:25 · 说说

年底回头看了看今年，做了个小总结。
有些地方确实挺意外的。

![](images/ss_demo_0001_0.png)

`来自 Android · 评论 1`

> **示例好友**（2025-12-26 22:41:02）：这个总结做得不错 @示例用户
> > **示例用户**（2025-12-26 22:55:11）：谢谢😄 [呲牙]

[原文链接](https://user.qzone.qq.com/100000001/mood/aa0000000000000000000001)
```

顶部还有一张统计表（说说/日志/图片数量、时间跨度）和一张年度分布表，正文按年份分组。

---

## 它是怎么工作的

QQ 空间给每个 CGI 请求加了一个叫 `g_tk` 的签名，它由浏览器 `p_skey` Cookie 算出，既没法从页面 DOM 里直接读到，也不可能跨境调用。所以路线是：

> **在真实浏览器里登录 → 用 Chrome DevTools Protocol 连上去 → 在页面上下文里调用同源 CGI 接口**

Cookie 由浏览器自动携带，不用手工拼 Cookie 头，也绕开了 httpOnly 和 GBK 编码的坑。

数据抓下来之后都是纯本地处理：图片并发下载、**按 Magic bytes 判类型**（不信 URL 后缀）、失效图重试，最后用 Python 标准库合成 Markdown。

**全程不碰 QQ 的阅读权限之外的东西，也不会向任何第三方发送数据。**

---

## 作为 Agent Skill 安装

本仓库遵循开放的 [Agent Skills](https://agentskills.io/specification) 规范（`SKILL.md` + `scripts/` + `references/`）。Claude Code、Codex、Gemini CLI、Cursor、GitHub Copilot、OpenCode 等支持 SKILL.md 的工具都能用。

把仓库克隆到对应的 skills 目录，**文件夹名必须是 `qzone-export`**（规范要求与 `name` 字段一致）：

| 工具 | 用户级目录（所有项目可用） | 项目级目录 |
|---|---|---|
| 通用约定（Codex、Cursor、Gemini CLI、Copilot 等都会读） | `~/.agents/skills/` | `.agents/skills/` |
| Claude Code（**不读**通用目录，要单独装） | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| GitHub Copilot（VS Code） | `~/.copilot/skills/` | `.github/skills/` |

```bash
# 例：装到通用目录
git clone https://github.com/RanchoGao/qzone-shuoshuo-timeline.git ~/.agents/skills/qzone-export
# 例：装到 Claude Code
git clone https://github.com/RanchoGao/qzone-shuoshuo-timeline.git ~/.claude/skills/qzone-export
```

> 各工具读取的目录还在变化。装好后如果识别不到，查一下该工具的最新文档。

装好后直接对 agent 说：

- 「帮我把 QQ 空间的说说导出来」
- 「备份一下 QQ 空间的日志」
- 「导出 QQ 空间，图片存到 D:/备份」

Agent 会先问你两个问题（图片怎么处理、文件怎么组织），然后按 SOP 跑完整流程。

---

## 作为命令行工具使用

### 环境要求

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | 3.8+ | 图片下载、Markdown 生成（**只用标准库，零 pip 依赖**） |
| Node.js | 18+ | 浏览器控制与数据抓取 |
| `puppeteer-core` | 最新版 | 连接 Chrome 调试端口 |
| Chrome / Edge | 任意新版 | 登录 QQ 空间 |

```bash
cd /tmp/qe && npm install puppeteer-core
# 记下这个绝对路径，后面要用，例如：
# /tmp/qe/node_modules
```

### 完整步骤

```bash
# 0. 先跑一遍自测，确认脚本本身没问题（都不需要网络和浏览器）
#    Node 侧不需要 puppeteer-core，纯逻辑自测；没装 Node 可跳过
node tests/test_lib.js
python tests/test_core.py

# 1. 启动带调试端口的浏览器（会弹出窗口，在里面扫码登录 QQ 空间）
#    Windows
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir="$PWD/.chrome-profile" \
  --no-first-run "https://user.qzone.qq.com" &
#    macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir="$PWD/.chrome-profile" \
  --no-first-run "https://user.qzone.qq.com" &

# 2. 确认登录态（输出 loggedIn: true 才可继续）
NODE_PATH=/tmp/qe/node_modules node scripts/status.js

# 3. 抓数据（说说 + 日志，支持中断续传）
NODE_PATH=/tmp/qe/node_modules node scripts/fetch_shuoshuo.js
NODE_PATH=/tmp/qe/node_modules node scripts/fetch_blog.js

# 4. 下载图片
python scripts/download_images.py
python scripts/retry_failed.py

# 5. 生成 Markdown
python scripts/gen_markdown.py

# 6. 收尾
NODE_PATH=/tmp/qe/node_modules node scripts/close.js
rm -rf .chrome-profile          # 务必删掉，里面是你的登录态
```

产物都在仓库根目录：

```
QQ空间存档.md         ← 最终成果
images/              ← 所有图片
data/*.json          ← 原始数据（字段比 Markdown 全）
```

### 换输出目录

不想导出到仓库目录里？用 `QZONE_OUT`：

```bash
export QZONE_OUT="D:/备份/qzone"
# 然后照常跑上面 2~6 步，所有 Python 和 Node 脚本都会认这个变量
```

想换个 Markdown 文件名？用 `QZONE_TITLE`：

```bash
QZONE_TITLE="我的QQ空间" python scripts/gen_markdown.py   # 输出 我的QQ空间.md
```

### 全部可调参数

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `QZONE_OUT` | 仓库根目录 | 输出根目录，`QQ空间存档.md`、`data/`、`images/` 都生成在它下面。Node 与 Python 两侧语义一致，**不是** `data/` 本身 |
| `QZONE_TITLE` | `QQ空间存档` | Markdown 文件名（不含 `.md`） |
| `QZONE_HOST` | `127.0.0.1` | CDP 服务地址 |
| `QZONE_PORT` | `9222` | 远程调试端口，被占用时改掉 |
| `QZONE_DELAY` | `700` | 请求间隔（毫秒）。**触发风控时调到 1500+** |
| `QZONE_WORKERS` | `8` | 图片下载并发数 |
| `QZONE_STAT_YEAR` | 当前年份 | 日志接口的 `statYear` 必须是有效年份 |
| `QZONE_UA` | 内置 Chrome UA | 下载图片时的 User-Agent |

---

## 退出前必做（很重要）

1. `node scripts/close.js` —— 否则 Chromium 进程常驻后台
2. 删掉 `data/auth.json` 里的 `cookieStr`（如有）——**那是你的有效登录凭据**
3. 删掉 `.chrome-profile/` —— **里面是完整的 QQ 登录态**
4. 别把 `QQ空间存档.md`、`data/`、`images/` 误传到公开仓库 —— 里面有你的 QQ 号、好友昵称、定位

> Windows 上 `.chrome-profile/` 常有上千个文件，可能触发删除保护提示。按提示逐个确认，或者用 `mv` 移到别处。

---

## 常见问题

| 现象 | 处理 |
|---|---|
| 9222 端口连不上 | 确认浏览器进程还在；如果本机开了代理，访问 localhost 要加 `--noproxy '*'` |
| `Cannot find module 'puppeteer-core'` | `NODE_PATH` 没设对，它要指向**包含该包的 `node_modules` 目录本身** |
| 接口返回乱码 | 日志接口显式传了 `inCharset=utf-8&outCharset=utf-8`，一般不会；若仍有，检查是否改过脚本 |
| 抓着抓着大量报错 | 风控。设 `QZONE_DELAY=2000` 后重跑，脚本有续传不会重复抓 |
| 图片全是缩略图 | 说说应取 `pic[i].url2`，日志应取 `<img orgsrc>`；两个位置都容易取错 |
| 日志列表报 `-4003` | `statYear` 非法，设 `QZONE_STAT_YEAR=2026` |
| 有图下载失败 | 跑完 `retry_failed.py` 还失败的，多半是图床已永久下线，Markdown 里保留了原 URL 做占位 |
| 接口路径报错/返回异常 | 路径历年变过。跑 `node scripts/sniff.js blog` 嗅一遍当前真实地址 |

---

## 目录结构

```
qzone-export/
├── SKILL.md                     # Agent Skill 定义（触发条件、执行逻辑、参数）
├── README.md                    # 本文件
├── LICENSE                      # MIT
├── CHANGELOG.md
├── scripts/
│   ├── lib.js                   # CDP 连接、g_tk 计算、页面内 fetch、JSONP 解包
│   ├── status.js                # ① 登录态检查
│   ├── sniff.js                 # ② 接口嗅探（路径变了用它）
│   ├── fetch_shuoshuo.js        # ③ 说说抓取
│   ├── fetch_blog.js            # ④ 日志抓取
│   ├── download_images.py       # ⑤ 图片下载
│   ├── retry_failed.py          # ⑥ 失效图重试
│   ├── gen_markdown.py          # ⑦ Markdown 生成
│   ├── close.js                 # ⑧ 关闭浏览器
│   └── make_example.py          # 生成 examples/（虚构数据）
├── references/
│   ├── SOP.md                   # 标准操作程序：每阶段的目标/输入/输出/通过标准/故障处理
│   └── api-notes.md             # 接口速查：端点、参数、字段、返回码
├── examples/
│   ├── example-output.md        # 工具的真实输出（虚构数据）
│   ├── data/                    # 对应的输入 fixtures
│   └── images/
└── tests/
    ├── test_core.py             # 纯 Python 逻辑自测，28 项，零依赖
    └── test_lib.js              # 纯 Node 逻辑自测，15 项，零依赖（不需要 puppeteer-core）
```

---

## 合规与边界

1. **只导出自己的空间。** 整套流程依赖本人的登录态。导出他人数据前必须获得明确授权。
2. **遵守调用频率。** 接口有风控，出现非 0 返回码就加大间隔，不要并发猛刷。
3. **仅限个人备份。** 不得用于批量抓取、转售或公开发布他人内容。
4. **不在命令行传递账号密码。** 未登录时让用户在弹出的浏览器窗口里扫码，脚本不接触凭据。
5. 本项目是个人存档用途的民间工具，与腾讯无关，也不使用任何非公开 API 以外的通道。

---

## 致谢

接口路径的建立方式值得一提：**不是查文档查出来的，而是监听页面自身请求嗅出来的**。QQ 空间的接口历年改过多次（比如日志列表从 `blog_get_abstract` 换到 `get_abs`），与其猜，不如打开页面看它自己调了什么——这也是 `scripts/sniff.js` 存在的原因。

## License

MIT © EurekaGao
