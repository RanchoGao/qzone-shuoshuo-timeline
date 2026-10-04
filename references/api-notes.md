# QQ 空间 CGI 接口速查

> 给 agent 和排障用。**端点路径历年变过，本文里的地址可能失效。**
> 拿不准就别猜，跑 `scripts/sniff.js` 嗅一遍页面的真实请求（十几秒的事），比试错快得多。

---

## 通用规则

| 项 | 值 |
|---|---|
| 域名 | `https://user.qzone.qq.com` |
| 代理前缀 | `/proxy/domain/{真实域名}/{path}`，例如 `/proxy/domain/taotao.qq.com/cgi-bin/...` |
| 必带参数 | `g_tk`（见下） |
| 返回格式 | JSONP：`_Callback({...});` 或者直接是 JSON。**要剥壳** |
| 编码 | 说说接口 UTF-8；博客接口默认 GBK，可显式传 `inCharset=utf-8&outCharset=utf-8` |
| 调用方式 | 在页面上下文里 `fetch(url, {credentials:'include'})`，Cookie 自动带上 |

### g_tk（bkn）

`p_skey`（取不到则用 `skey`）的 djb2 变体：

```js
function gtk(skey) {
  let hash = 5381;
  for (let i = 0; i < skey.length; i++) {
    hash += (hash << 5) + skey.charCodeAt(i);
    hash &= 0xffffffff;   // 这一步只是把中间值压回 32 位，数学上等价，防止溢出
  }
  return hash & 0x7fffffff;  // 结果是 8~10 位正整数
}
```

取 Cookie 要用 CDP 的 `Network.getAllCookies`——`page.cookies()` 读不到 httpOnly 的 `p_skey`。

---

## 说说

### 列表

```
GET /proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6
  uin            QQ 号
  ftype          0
  sort           0（按时间倒序）
  pos            偏移量，从 0 开始
  num            每页条数，上限 20
  replynum       评论拉取条数，给 100
  g_tk
  callback       _preloadCallback
  code_version   1
  format         jsonp
  need_private_comment  1
```

响应要点：

| 字段 | 说明 |
|---|---|
| `total` | 说说总数，用它判断是否抓完 |
| `msglist[]` | 本页数据 |
| `msglist[].tid` | 唯一 ID，去重和拼原文链接都要用 |
| `msglist[].content` | 正文，含 `[em]xxx[/em]` 和 `@{uin:..,nick:..}` |
| `msglist[].created_time` | Unix 秒 |
| `msglist[].pic[]` | 图片列表，见下 |
| `msglist[].pictotal` | **该条图片总数**。列表通常只回前几张，判断要不要拉详情就看 `pictotal > pic.length` |
| `msglist[].commentlist[]` | 评论；`list_3[]` 是楼中楼回复 |
| `msglist[].lbs` | 定位 `{name, idname, pos_x, pos_y}` |
| `msglist[].rt_*` | 转发信息：`rt_uinname`（原作者）、`rt_con.content`（原正文） |
| `msglist[].source_name` | 发布来源，如 "Android" |
| `msglist[].video[]` | 视频，`url3` 是 mp4 |
| `msglist[].audio[]` | 背景音乐信息 |

### 图片字段（踩坑最多的地方）

```
pic[i].url1      较小  —— 路径以 /m 结尾
pic[i].url2      原图  —— 路径以 /b 结尾   ★ 用这个
pic[i].url3      缩放  —— /b 再加 &w=&h=
pic[i].smallurl  缩略图 —— /a
pic[i].pic_id    "uin,相册ID,图片ID" 形式
```

**必须取 `url2`**，否则导出的全是缩略图。

### 详情（图片超过列表返回数时才用）

```
GET /proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msgdetail_v6
  uin  tid  t1_source=1  ftype=0  sort=0  pos=0  num=20  g_tk  callback=...
```

---

## 日志

### 列表

```
GET /proxy/domain/b.qzone.qq.com/cgi-bin/blognew/get_abs
  hostUin       QQ 号
  uin           QQ 号
  blogType      0
  cateName      （空）
  cateHex       （空）
  statYear      必须是有效年份，如 2026；留空会返回 -4003「错误的统计年份」
                注意：它只影响侧栏的年月统计，并不过滤列表本身
  reqInfo       7
  pos           偏移量
  num           每页条数，上限 15
  sortType      0
  source        0
  rand          随机数
  ref           qzone
  g_tk
  verbose       1
```

响应：`data.totalNum` 是总数，`data.list[]` 为列表，每项含 `blogId`、`title`、`pubTime`（`"2015-03-15 12:12"`）、`cate`（分类）、`commentNum`。

> 历史上有过一个 `blog_get_abstract`，现在会报"日志ID不能为空"。**接口路径变了就嗅一遍。**

### 正文

```
GET /proxy/domain/b.qzone.qq.com/cgi-bin/blognew/blog_output_data
  uin  blogid
  styledm       qzonestyle.gtimg.cn
  imgdm         user.qzone.qq.com/proxy/domain/qzs.qq.com
  bdm           b.qzone.qq.com
  mode          2
  numperpage    15
  timestamp     Unix 秒
  blogseed      随机数
  inCharset     utf-8     ← 不传默认 GBK
  outCharset    utf-8
  ref           qzone
  g_tk
```

返回整页 HTML：

| 提取目标 | 位置 |
|---|---|
| 正文 HTML | `#blogDetailDiv`（回退：`.blog_details`、`#blogContainer`） |
| 结构化元数据 | 内联脚本里的 `g_oBlogData = {...}` |
| 标题 / 作者 / 分类 | `g_oBlogData.data` |

**图片是懒加载的**：`<img src="loading.gif" orgsrc="真图URL">`。真图 URL 带 `dis_t` / `dis_k` 时效签名，**抓完要尽快下载，隔太久会 403**。

解析要用浏览器里的 `DOMParser`，不要正则——`<td>` 这类嵌套标签数不对会全盘错位。

### 评论

```
GET /proxy/domain/b.qzone.qq.com/cgi-bin/blognew/get_comment_list
  uin  num=100  topicId={uin}_{blogid}  start=0  r=随机数
  iNotice=0  inCharset=utf-8  outCharset=utf-8  format=jsonp  ref=qzone  g_tk
```

---

## 图片

| 情况 | 处理 |
|---|---|
| 说说图 | 取 `url2` |
| 日志图 | 取 `orgsrc` |
| `p.qpimg.cn/cgi-bin/cgi_imgproxy?url=<真实地址>` | **该代理已停摆**（502）。解出内层 `url` 参数直连重试 |
| `*.mafengwo.net`、`t3.qpic.cn/mblogpic/*` 等老图床 | 大多已永久下线，救不回来 |
| 扩展名 | 一律按 **magic bytes** 判断（`\xff\xd8\xff`=jpg、`\x89PNG`=png、`GIF8`=gif、`RIFF....WEBP`=webp），**不信 URL 后缀** |

---

## 返回码

| code | 含义 | 处理 |
|---|---|---|
| `0` | 成功 | — |
| `-3000` 附近 | 凭据 / g_tk 有问题 | 重算 g_tk，确认没过期 |
| `-4003` | 参数错误（如 `statYear` 非法） | 检查必填参数是否为有效值 |
| `msg` 含「权限」 | 该内容对你不可见 | 属正常跳过项 |
