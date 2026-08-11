## 1. HTTP 取数封装(P2,后续 P3/P4 的硬前置)

- [ ] 1.1 `scripts/collect/util.py` 的 `fetch_text` 按 gzip 魔数(`raw[:2] == b"\x1f\x8b"`)解压后再解码;解压失败抛异常,不得回退为有损解码。`fetch_json` 复用之
- [ ] 1.2 `fetch_text` / `fetch_json` 增加可选 `headers` 参数,与默认 `User-Agent: macro-fx-collector/0.1` 合并(调用方可覆盖,未传时行为不变)
- [ ] 1.3 回归测试:gzip 响应正常解压、`Accept-Encoding: identity` 被无视时仍解压、压缩体损坏时抛异常而非返回乱码、未压缩响应行为不变、自定义 header 随请求发出

## 2. BIS 取数与解析

- [ ] 2.1 `config/endpoints.json` 增 `bis_cbpol_url`、`bis_cpi_url`;`config/indicators.json` 为五经济体的 CPI 与政策利率补 BIS 维度键(`REF_AREA`),保留现有 `series_id` 供 DBnomics 回落
- [ ] 2.2 `scripts/collect/macro.py` 新增 BIS CSV 解析:`csv.DictReader` 按列名取 `REF_AREA` / `TIME_PERIOD` / `OBS_VALUE`;三个必需列任一缺失即抛错由上层转 gap,禁止按列位置索引
- [ ] 2.3 `REF_AREA` 映射(BIS `XM` ↔ 仓库 `EA`)写成模块级常量,不做字符串启发式
- [ ] 2.4 `WS_CBPOL` 日频序列取最近一个非 `NaN` 观测;`"NaN"` 按字符串显式判定,不得先转 float 再判,避免 NaN 穿过数值比较

## 3. 前值与优先级

- [ ] 3.1 政策利率的 `prev` 取上一个**与当前值不同**的利率水平及其最后生效日;回溯窗口内无变动时 `prev` 为 `null`,不得等于当前值
- [ ] 3.2 来源优先级接成 BLS > BIS > DBnomics:美国 CPI 保持 BLS 且 BIS 不得覆盖;BIS 取得的指标不再打 DBnomics
- [ ] 3.3 逐指标回落:BIS 整体失败 / 缺必需列 / 缺某经济体时,受影响指标各自回落 DBnomics 并记 gap,未受影响的保持 BIS;经常账户 5 条始终走 DBnomics 不受影响
- [ ] 3.4 端点未配置时静默跳过 BIS 分支(与 `feeds.py` 的"未配置 = 有意停用"同一约定),使删掉两个 URL 即可整体回滚

## 4. 测试

- [ ] 4.1 `tests/test_macro.py` 覆盖 BIS 正常路径:五经济体 CPI 与政策利率取自 BIS、`source` 为 `bis`、美国 CPI 仍为 `bls`
- [ ] 4.2 覆盖三条降级路径:BIS 整体不可达、缺必需列、缺某经济体——各自的回落粒度与 gap 记录
- [ ] 4.3 覆盖 `NaN` 处理与 `prev` 口径:末端 NaN、全 NaN、有变动、无变动(`prev` 为 null 而非等值)
- [ ] 4.4 覆盖换源标记:切换当日 10 个指标带 `source_changed_from`、`is_new_release` 为 false;回落方向同样标记
- [ ] 4.5 畸形输入不崩:CSV 空响应、列名大小写变化、`OBS_VALUE` 非数值、`REF_AREA` 含未知经济体、CSV 体积异常

## 5. 收尾

- [ ] 5.1 `skills/fx-daily-report/SKILL.md` 的「数据发布」行在 `prev` 后加 `prev_period`,写成「前值 <prev>(截至 <prev_period>)」;`prev` 为 null 时写「前值 不可得(回溯窗口内未观测到变动)」——日频序列的前值不带日期即歧义
- [ ] 5.2 跑一次真实采集,核对五经济体的 `value` / `period` / `lag_months` / `source` 与 BIS 端点直查结果逐条一致
- [ ] 5.3 `README.md` 数据源一节补 BIS 两个 dataflow 与三级优先级;注明经常账户仍走 DBnomics、BSP 因 robots.txt 不接入
