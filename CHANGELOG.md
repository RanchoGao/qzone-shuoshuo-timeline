# Changelog

本项目所有值得记录的改动都会写在这里。
格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [1.0.0] — 2026-10-04

首次公开发布。整套流程在一份真实账号上跑通：**1573 条说说、16 篇日志、722 张图片**，时间跨度 2009–2025，输出 20840 行 Markdown。

### 新增

- **五个阶段的完整导出链路**
  - A 身份凭据：独立 `--user-data-dir` 的调试浏览器 + CDP 取 `p_skey` + `g_tk` 算法
  - B 数据抓取：说说分页（含多图补齐）、日志列表与正文（含评论），支持中断续传
  - C 图片本地化：并发下载、协议回退、失效重试
  - D Markdown 生成：文本清洗、HTML 转 MD、排序聚合
  - E 收尾：关浏览器、清凭据

- **文本还原**
  - `@{uin:..,nick:..}` → `@昵称`
  - `[em]eNNN[/em]` → `[呲牙]` 这样的可读表情（e100–e182 经典表已映射，新版表情降级为 `[表情]`）
  - QQ 正文换行 → Markdown 硬换行
  - 行首结构性字符转义（ `#` / `>` / `-` / `1.` / `|` ）

- **保真与健壮性**
  - 说说取 `url2` 原图、日志取 `<img orgsrc>`，避免导出成缩略图
  - 图片类型按 magic bytes 判断，不信 URL 后缀
  - 日志正文用浏览器 `DOMParser` 解析，不用正则
  - 失效图片保留原始 URL 做占位，不静默丢弃
  - 自动解开已停摆的 `p.qpimg.cn` 图片代理重试

- **工程性**
  - `references/SOP.md`：标准操作程序，每阶段写明目标/输入/输出/通过标准/常见故障
  - `references/api-notes.md`：接口速查（端点、参数、字段、返回码）
  - `scripts/sniff.js`：接口路径变了不用猜，嗅一遍就知道
  - `examples/`：用虚构数据生成的真实输出，可直接看效果
  - `tests/test_core.py`：23 项纯 Python 自测，零依赖、不需要网络和浏览器
  - 全部输出目录可通过 `QZONE_OUT` 重定向

### 修复

- 有序列表转义了数字（`\1`）而非点号——`\1` 在 CommonMark 里不是合法转义，会原样显示
- 空加粗标记 `** **` 的清理规则误伤了合法加粗内容
- 转义规则误伤行内 `|`（管道符只在表格内有意义）

### 已知限制

- 2012 年前后引用的第三方图床（蚂蜂窝、腾讯微博图床、各类已关站博客）已永久下线，实测 732 张图中有 10 张无法恢复
- 日志图片的 `orgsrc` 带时效签名，抓取后需尽快下载，隔太久会返回 403
- Node 侧依赖 `puppeteer-core`，需自行 `npm install` 并正确设置 `NODE_PATH`；Python 侧零依赖
- 只支持导出本人登录后可见的内容

[1.0.0]: https://github.com/RanchoGao/qzone-shuoshuo-timeline/releases/tag/v1.0.0

## [1.0.1] — 2026-10-04

一次完整的回归测试（含真实账号端到端重跑）后收上来的修补 release。对外行为不变，修的全是**换了环境就会踩**的问题。

### 修复

- **`QZONE_OUT` 在 Node 和 Python 两侧语义不一致**（最严重的一个）
  - 表现：Node 把它当成 `data/` 目录，Python 当成根目录。设了变量后 Node 写进对的 json，Python 却读不到
  - 现在统一为**输出根目录**：`<QZONE_OUT>/data`、`<QZONE_OUT>/images`、`<QZONE_OUT>/<标题>.md`
  - 加了 `tests/test_lib.js` 把这个语义锁住，防回归
- **`download_images.py` 在空目录下第一步就崩**：只建了 `images/`，等到写 `images.json` 才 `FileNotFoundError`，长跑的结果全丢。改成两个目录预先都建好
- **缺 `auth.json` 时固定链接出现双斜杠**：`user.qzone.qq.com//mood/xxx`。现在 `uin` 会从 auth.json → 说说自身的 `uin` 字段依次回退，实在没有就省略 QQ 号段而不是留双斜杠
- **日志的图片计数与正文不符**：header 报 0 张，正文里却插了 5 张占位。口径改为按该条自己引用的 URL 去重统计，不再用全量 `images.json`
- **`lib.js` 顶层 `require('puppeteer-core')`**：没装依赖时连纯逻辑测试都跑不起来。改为惰性加载，并给出可直接照做的错误提示

### 新增

- `tests/test_lib.js`：15 项零依赖 Node 自测（`g_tk` 确定性/范围、JSONP 解包边界、环境变量语义）。不需要 `puppeteer-core`
- `tests/test_core.py` 从 23 项扩到 28 项，覆盖上面双斜杠和图片提取两个回归
- README / SKILL.md 补了阶段 0 自测步骤，以及 `QZONE_OUT` 语义的两条故障排查

### 验证

真实账号完整重跑一遍并与两个月前的产物逐项比对：

| 项 | 本次 | 基准 | |
|---|---|---|---|
| 条目总数 | 1590 | 1590 | ✅ |
| 图片引用 | 722 | 722 | ✅ |
| 失效占位 | 10 | 10 | ✅ |
| 固定链接 | 1589 | 1589 | ✅ |
| 评论行数 | 913 | 913 | ✅ |

说说 1573 条的 tid 集合完全一致，正文/图片数/时间戳零差异；差异只有三项：标题空格、导出时间戳、一位好友改了昵称。

[1.0.1]: https://github.com/RanchoGao/qzone-shuoshuo-timeline/releases/tag/v1.0.1

## [1.1.0] — 2026-10-04

新增**时间轴页面**：把说说做成一张离线网页，用来按时间整体回看自己的过往。仓库同时改名为 `qzone-shuoshuo-timeline`（skill 名仍是 `qzone-export`，克隆到 skills 目录时文件夹名不变）。

### 新增

- `scripts/gen_timeline.py` 和 `scripts/timeline_template.html`：生成单文件 `QQ空间时间轴.html`，只含说说
  - **年月热力图**：哪些年、哪些月发得最多一眼可见，点格子跳到那个月
  - **时间轴**：按年、月分组，最新在前 / 最早在前可切换，右侧年份导航
  - **搜索与筛选**：全文搜索（含评论、地点，命中高亮）、按年份、只看有图、只看有评论
  - **回顾**：「跳到最早一条」「随机回顾一条」「那年今日」
  - **看图**：大图查看，键盘 ← / → / Esc 与触摸滑动；失效图片显示占位，不显示坏链
  - 深色模式、手机适配；不联网、不依赖任何外部库
- 环境变量 `QZONE_TIMELINE_TITLE`（页面标题，默认也是文件名）、`QZONE_TIMELINE_FILE`（文件名与标题不同时用）
- `tests/test_timeline.py`：44 项零依赖自测，覆盖数据整形、内嵌安全（正文里的 `</script>` 不会提前结束数据块）、端到端生成；有 Node 时顺带做页面脚本的语法检查
- `examples/example-timeline.html` 和 `examples/screenshots/`（README 里的截图）

### 变更

- `examples/` 的虚构数据从 3 条扩到 38 条说说，覆盖多图、定位、转发、视频、音乐、链接和嵌套评论；占位图换成彩色渐变，示例才有看头。示例时间用本地时间字符串构造，换时区也读出同样的日期
- `make_example.py` 现在同时生成 Markdown 和时间轴页面，并在生成前清掉旧的示例图，保证结果可复现
- `.gitignore` 增加根目录的 `QQ空间时间轴.html`（真实导出的页面含 QQ 号和好友昵称）
- README、SKILL.md、SOP.md 补上时间轴的用法、参数、通过标准和排障

### 验证

- 三套自测全过：`test_lib.js` 15 项、`test_core.py` 28 项、`test_timeline.py` 44 项
- 在 headless Chrome 里对示例页逐项操作：搜索、三种筛选、排序切换、评论展开、热力图跳转、灯箱、主题切换，加手机宽度下无横向溢出，全程无 JS 报错
- 用 1573 条、跨 17 年、三千多张图引用的合成数据压测：页面加载约 0.16 秒，筛选 / 切换排序约 0.2 秒。混入 `<img onerror>` 和 `<script>` 的正文被当成纯文本显示，不会执行

