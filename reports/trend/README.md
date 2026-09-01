# 趋势页

`fx-trend.html` 是发布成 artifact 的那一份源文件,**自包含**:数据内联在两个
`<script type="application/json">` 块里(`series` 与 `facts`),外部引用只有一条
Google Fonts。因此它是"一个文件
就能搬走"的东西 —— 换账号、换机器都不必带数据文件、不必配服务、不必改路径。

## 刷新数据

    python3 scripts/trend_page.py            # 全窗口
    python3 scripts/trend_page.py --date 2026-09-01

它只替换那两段内联 JSON —— `series` 出自 `scripts/trend.py`(定盘、区间、
实际利率、复盘序列),`facts` 出自 `scripts/highlights.py`(从已过校验的报告里
**抽取**的要点:速览表、判断环、「本期相对上期的变化」四类标签、复盘结论、
周主线与翻转指标)。页面结构与样式一个字符都不动,页面自己不重述任何一句话。序列化口与
`scripts/trend.py --mode series` 一致(`sort_keys=True`),所以同一份数据重嵌
一次逐字节不变 —— git diff 上只会出现真正变了的部分。

## 换一个账号发布

artifact 的归属在**发布那一刻**就定了,没有转移这回事;分享链接给的是读取权,
不是所有权。要让另一个账号拥有它,只有一条路:**拿同一份 HTML 在那个账号的
会话里重新发布一次**,会得到一个属于它的新 URL。

1. 那个账号 clone 本仓库(或者只把 `reports/trend/fx-trend.html` 这一个文件
   传过去);
2. 在那边的 Claude Code 会话里说:把 `reports/trend/fx-trend.html` 发布成
   artifact;
3. 之后在**那个**会话里改同一个文件路径重新发布,URL 不变。

不要指望从已发布的链接把源码读回来:读一份别人分享给你的 artifact 拿到的是
摘要,不是原始 HTML。源文件以这一份为准。
