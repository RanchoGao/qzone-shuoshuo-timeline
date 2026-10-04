---
name: qzone-export
description: 导出 QQ 空间（Qzone）说说与日志为本地 Markdown 存档，含图片、评论、转发、定位。全流程标准操作程序 SOP 见 references/SOP.md。Use when the user wants to back up or export their Qzone content — 导出 QQ 空间 / 备份说说 / 备份日志 / QQ 空间存档 / 把说说保存下来 / 导出 QQ 相册说说 / qzone export / export QQzone.
license: MIT
compatibility: Requires Python 3.8+ (stdlib only), Node 18+, and puppeteer-core, plus Chrome or Edge. User must log in to Qzone by scanning a QR code.
metadata:
  author: EurekaGao
  version: "1.0.1"
---

# qzone-export：导出 QQ 空间说说与日志

把 QQ 空间的**说说**和**日志**连同**图片、评论、转发、定位**，导出成一份本地 Markdown，图片存到 `images/` 用相对路径引用。

QQ 空间没有官方导出功能。可行路线是：**在真实浏览器里登录，然后在页面上下文调用同源 CGI 接口**——Cookie 由浏览器自动携带，不用手工拼 Cookie 头，也绕开了 httpOnly 和 GBK 编码的坑。

一次实测：**1573 条说说 + 16 篇日志 + 722 张图片**，输出 20840 行、1.04 MB 的 Markdown。

## 铁律（每一步都要遵守）

1. **只导出用户自己的空间。** 这套流程依赖用户本人的登录态。导出他人数据前必须有明确授权。
2. **不在命令行里收账号密码。** 未登录时，把窗口给用户让用户扫码，不要在脚本里回显凭据。
3. **凭据用完必须清。** 收尾时要删掉 `data/auth.json` 里的 `cookieStr` 和整个 `.chrome-profile/`（里面是完整的 QQ 登录态）。
4. **失败项要显式告知用户，不能静默丢弃。** 老图床失效的图片，在 Markdown 里保留原始 URL 并标注失效。
5. **不猜接口。** 端点路径变过，拿不准就跑 `scripts/sniff.js` 嗅一遍再动手。
6. **遵守调用频率。** 出现非 0 返回码就加大间隔，不要并发猛刷。

---

## 触发条件

用户意图命中以下任一即启用：

- 导出 / 备份 QQ 空间内容（说说、日志）
- 把说说保存下来、防止 QQ 空间关停丢失
- 想把多年说说做成可检索的本地文档
- qzone export / export QQzone posts

**动手前先问清两件事**（直接决定实现路径）：

| 问题 | 选项 |
|---|---|
| 图片怎么处理？ | 下载到本地（推荐，离线可看）／ 只留原始链接（快，但会失效）／ 两者都要 |
| 文件怎么组织？ | 日志说说分开两个文件 ／ 合并成一个大文件（推荐）／ 每篇日志单独一个文件 |

如果用户已经明确说了，不再追问。

---

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| 输出根目录 | 当前工作目录下的 `qzone-export/` | 产物都在这里 |
| `QZONE_OUT` | 未设置时取脚本上一级的父目录 | 覆盖上面那个根目录，用来导出到别的位置。**它是根目录本身**：`data/`、`images/`、`.md` 都生成在它下面，Node 与 Python 两侧语义一致 |
| `QZONE_HOST` | `127.0.0.1` | CDP 服务地址 |
| `QZONE_PORT` | `9222` | 远程调试端口。被占用时先释放，或换成 9333 |
| `NODE_PATH` | 无 | **必须**指向含 `puppeteer-core` 的 `node_modules`，否则 `require` 失败 |
| 每页条数（说说） | `20` | 接口上限，改大无效 |
| 请求间隔 | `700ms` | 触发风控时调到 `1500ms` 以上 |

Node 脚本必须带 `NODE_PATH`：

```bash
NODE_PATH="/path/to/node_modules" node scripts/fetch_shuoshuo.js
```

---

## 执行逻辑

五个阶段**串行**：B 依赖 A 的 `g_tk`，C 依赖 B 的 URL 清单，D 依赖 B 和 C 的产物。

**阶段 0（可选但推荐）：跑自测。** 两侧都不需要网络、浏览器或 `puppeteer-core`，几秒出结果：

```bash
node tests/test_lib.js      # 15 项：g_tk 算法、JSONP 解包、环境变量语义
python tests/test_core.py   # 28 项：Markdown 转义、HTML 转换、图片计数
```

不通过就先修脚本，别带着病跑真实数据。
完整的「目标 / 输入 / 输出 / 通过标准 / 常见故障」见 [SOP.md](references/SOP.md)，接口参数细节见 [api-notes.md](references/api-notes.md)。

### A　身份与凭据 → `data/auth.json`

| 步骤 | 命令 | 做什么 |
|---|---|---|
| A1 | 手动启动 Chrome | 带 `--remote-debugging-port=9222` 和**独立的 `--user-data-dir`**，打开 QQ 空间 |
| A2 | `node scripts/status.js` | 用 CDP 的 `Network.getAllCookies` 取 `p_skey`，算 `g_tk`，落盘 `auth.json` |
| A3 | 同上（读数） | 确认 `loggedIn: true`；未登录则让用户扫码后重跑 A2 |

`g_tk`（bkn）算法：`hash = 5381; 每位 hash += (hash << 5) + charCodeAt(i); 末尾 hash & 0x7fffffff`。
**通过标准**：`uin` 为纯数字、`g_tk` 为 8–10 位正整数、当前页面在 `user.qzone.qq.com` 下。

> 必须用**独立的** `--user-data-dir`，不要污染用户日常的浏览器配置。

### B　原始数据抓取 → `shuoshuo.json`、`blog.json`

| 步骤 | 命令 | 做什么 |
|---|---|---|
| B1 | `node scripts/fetch_shuoshuo.js` | 说说分页拉取（每页 20），失败重试 4 次退避；每页落盘，中断可续传；图片不足时补详情接口 |
| B2 | `node scripts/fetch_blog.js` | 日志列表 → 逐篇正文（用 `DOMParser` 解析，不是正则）→ 评论 |
| B3 | 读数校验 | 条数对不对、`code` 是否全 0、`contentHtml` 是否非空 |

**通过标准**：说说条数 == 接口 `total`；日志条数 == `get_abs` 的 `totalNum`。
**注意**：日志列表的 `statYear` 必须是有效年份（空值会返回 -4003）。

### C　图片本地化 → `images/`、`images.json`

| 步骤 | 命令 | 做什么 |
|---|---|---|
| C1 | （由 C2 内部完成） | 构建清单：说说取 `pic[i].url2`（原图），日志取 `<img orgsrc>` |
| C2 | `python scripts/download_images.py` | 8 线程下载，https/http 双协议回退，扩展名按 magic bytes 判断，已存在自动跳过 |
| C3 | `python scripts/retry_failed.py` | 解开已停摆的 `p.qpimg.cn` 图片代理重试 |
| C4 | 校验 | Markdown 引用的每个文件名，在 `images/` 里必须真实存在 |

**通过标准**：文件数 == `ok: true` 的数量，缺失为 0，无 0 字节文件。
**已知不可恢复**：2012 年前后的第三方图床（蚂蜂窝、腾讯微博图床等）已下线，实测 732 张中 10 张失效。

> ⚠️ 日志的 `orgsrc` 带时效签名，**抓完尽快下载**，隔太久会 403。

### D　Markdown 生成 → `QQ空间存档.md`

```
python scripts/gen_markdown.py
```

文本清洗：`@{uin:..,nick:X}` → `@X`；`[em]e113[/em]` → `[呲牙]`（新版表情降级为 `[表情]`）；正文 `\n` → Markdown 硬换行；行首结构字符转义。
> 有序列表要转义**点号**（`1\. x`），不能转义数字——`\1` 在 CommonMark 里不是合法转义。

日志 HTML 用 `html.parser` 转成 Markdown；最后日志与说说合并、**按时间戳倒序**、按年分组。

**通过标准**：引用图片数 == `images/` 文件数且缺失为 0；随机抽 3 条渲染正常（换行在、图片在、评论在）；不存在 `\数字` 形式的残留。

### E　收尾

1. `node scripts/close.js`——**必须执行**，否则 Chromium 常驻后台
2. 删掉 `data/auth.json` 里的 `cookieStr`
3. 删掉 `.chrome-profile/`
   > 该目录通常有上千个文件，可能触发批量删除保护。**不要绕过安全策略**：改用 `mv` 移到项目外，或明确告诉用户手动删
4. 交付说明要讲清：导出了什么（条数 / 时间跨度 / 图片数）、哪些没办到、**移动时 `.md` 和 `images/` 必须一起移动**

---

## 使用示例

```bash
# 0. 自测（可选但推荐）
node tests/test_lib.js && python tests/test_core.py

# 1. 启动浏览器（给用户扫码）
"/path/to/chrome" --remote-debugging-port=9222 \
  --user-data-dir="$PWD/.chrome-profile" \
  --no-first-run "https://user.qzone.qq.com" &

# 2. 确认登录态
NODE_PATH=/path/to/node_modules node scripts/status.js

# 3. 抓数据
NODE_PATH=/path/to/node_modules node scripts/fetch_shuoshuo.js
NODE_PATH=/path/to/node_modules node scripts/fetch_blog.js

# 4. 图片
python scripts/download_images.py
python scripts/retry_failed.py

# 5. 生成 Markdown
python scripts/gen_markdown.py

# 6. 收尾
NODE_PATH=/path/to/node_modules node scripts/close.js
```

用户对 agent 说的话，以及该有的反应：

| 用户说 | agent 应该做 |
|---|---|
| 「帮我把 QQ 空间的说说导出来」 | 先问图片和文件组织方式，再跑完整流程 |
| 「我 QQ 空间的日志怎么备份」 | 同上，日志通常只有几篇到几十篇，很快 |
| 「导出到 D:/备份」 | 指定输出根目录为 `D:/备份` |
| 「图片太多跑不动了」 | 问是否改成只留链接；或先抓一批看看量级 |
| 「有好多图下载失败」 | 跑完 `retry_failed.py` 后，如实告知哪些图床已永久下线 |

---

## 遇到这些情况

| 现象 | 处理 |
|---|---|
| 9222 端口连不上 | 确认浏览器进程在；curl 加 `--noproxy '*'`（localhost 常被代理拦截） |
| `Cannot find module 'puppeteer-core'` | `NODE_PATH` 没设对，它必须指向含该包的 `node_modules` 目录本身 |
| 接口返回乱码 | 博客接口显式传 `inCharset=utf-8&outCharset=utf-8` |
| 频繁报非 0 返回码 | 风控。把间隔调到 1500ms 以上；脚本有续传，重跑不会重复抓 |
| 图片全是缩略图 | 说说取了 `url1`/`url3` 而不是 `url2`；日志取了 `src` 而不是 `orgsrc` |
| 日志列表报 -4003 | `statYear` 填有效年份 |
| 猜不出接口路径 | 跑 `node scripts/sniff.js blog` 嗅一遍再说 |
| Node 抓到了数据，Python 说找不到文件 | `QZONE_OUT` 指的是**输出根目录**（`data/` 和 `images/` 的父目录），不是 `data/` 本身。Node 和 Python 两侧语义一致，别混用 |
| 正文没图但 header 说有图 | 日志走 `<img orgsrc>` 提取；统计口径按该条自己引用的 URL 去重计数，不是全量 `images.json` |
