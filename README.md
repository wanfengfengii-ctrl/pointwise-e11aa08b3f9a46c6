# 河桥小剧场无障碍口述放映服务

节目编辑交付剪辑及口述单，校样员签发可兑现的排程，放映员在现场按实际剪辑走拍，收场员按实际出播区间核账。服务使用 Python 3.11 标准库、SQLite 和本机 JSON HTTP，无需音频设备。所有拍位从 0 开始。

## 一天的操作

1. 编辑提交两份剪辑的原声窗及口述稿的段长和截止拍，领取节目修订号。
2. 校样员按号查看是否可安排完整连续口述，通过后发行。勘误另建修订，原发行仍可按原素材办理。
3. 放映员将发行装入指定放映间，用同一发行号开场，领取场号与待处理拍 0。
4. 按拍推进。样例两场均先播 A，并在第 2 拍收到区分剪辑的提示。甲场的 B 在第 3 拍播，乙场的 B 在第 4 拍播。
5. 接班人提交原场号，领取当前装台、已见提示和实播进度，并继续推进原场。
6. 收场员查看实际口述区间。尚有必播段待播或在播时，场次保持在办。
7. 实播齐全后收场，领取固定编号。重开服务后可凭原场号或收场号查回同一结果。

## 运行

```sh
python3 -B -m booth.http_api --database theatre.sqlite3 --port 8000
python3 -B check_project.py
python3 -B -m tests.test_http --demo
```

第一条命令仅绑定 `127.0.0.1`。初始化只创建缺少的表，重启后继续使用指定数据库。样例不会自动写入数据库。第二条是平台提供的完整回归入口。第三条在测试临时目录新建数据库，对真实 HTTP 服务跑完一场、关停并用原库重新启动，最后输出实测场景。直接使用 Python 标准库发现用 `python3 -B -m unittest discover -s tests -t . -v`。

`samples/branching.json` 是可发行双剪辑样例。`samples/incompatible.json` 的两版分别可排，但发不出双版发行。`samples/crossing.json` 的 A 跨过提示拍连续播出。可直接把样例对象作为 `/program_input` 的请求体。

## JSON 接口

所有操作使用 `POST`，请求体为 JSON 对象，响应为 JSON。编号为正整数；剪辑号、段号、放映间、操作者和提示码为非空字符串。

| 路径 | 请求字段 | 成功响应 |
| --- | --- | --- |
| `/program_input` | `editions`、`segments`、`signals`，可选 `title` | 201，`revision_id` |
| `/preview` | `revision_id` | 200，`revision_id`、`eligible`、`reason` |
| `/issue` | `revision_id` | 201，`issued`、`revision_id`、`issue_id` |
| `/mount` | `booth`、`issue_id`、`operator` | 201，`assignment`、空 `show` 和 `intervals` |
| `/start` | `booth`、`issue_id` | 201，场次快照 |
| `/advance` | `show_id`、`tick`，可选 `signal` | 200，`tick`、`action`、`ended_segment`、`show` |
| `/handover` | `booth`、`show_id`、`operator` | 200，`assignment`、`show`、`intervals` |
| `/close` | `show_id` | 200，`closed` 和 `summary` |
| `/read` | `show_id` 或 `closeout_id`，二选一 | 200，`show`、`intervals`、`closeout` |

`editions` 中的对象含 `edition_id`、`length`、`sound_windows`。片长为正整数，窗口形如 `[start,end]`，语义为 `[start,end)`，满足 `0 <= start < end <= length`。相接或重叠的原声窗合并；显式空列表表示全片无原声。`segments` 中的对象含 `segment_id`、正整数 `length`、`deadlines`。截止映射必须恰好覆盖全部剪辑，截止拍可在 0 至对应片长之间。重复剪辑号或段号会拒绝整份输入。

`signals` 中的对象含 `code`、`tick`、`edition_id`。双剪辑各有一个确认码，两个码使用同一确认拍，且在各版片长内。单剪辑可用空列表，也可定义一个本版提示。推进时缺省或传 `null` 表示没有新提示。双剪辑到确认拍须报实际码，缺提示时回报 `signal_required` 并留在原拍。未知码、提前或迟到的码、重复提示和错误拍均拒绝整次推进。确认码在本拍播放决策前受理。

每次推进记录一个 `[tick,tick+1)`。`action.kind` 为 `wait`、`start` 或 `continue`；一拍段可以在同次请求启动和播完。当前 `show` 包含 `show_id`、`issue_id`、`mount_id`、`booth`、`next_tick`、`edition_id`、`signal`、`remaining`、`active`、`completed`、`closed`。在播段有 `start_tick` 和 `remaining_ticks`，实播账中的 `end_tick` 只有实际播完后才有值。实播按 `start_tick`、`segment_id` 排序。

输入不合法返回 400，未知号返回 404。冲突返回 409，响应的 `error` 给出可机读原因。不可发行时 `/issue` 返回 `issued: false` 和原因，且无发行号。提前收场返回 `closed: false` 及待完成信息。成功收场后重复提交原场号可复领同一摘要，已经收场的场次拒绝继续推进。错发行号开场、放映间占用时换装、对非绑定场交班均不会改动现有绑定。

## 计算与保存

`program/` 校验素材与每版时间轴。`release/` 核对同一观察下的共同开场及各版完整续程，固定发行所需的修订和行动依据。开始前已排定的口述可能跨过确认拍，校样要求它在全部当时可能的剪辑中都能连续播完。`show/` 只按现场已见提示选择后续动作。`record/` 单独保存实际起止拍并核对收场。`booth/` 管理装台和接班，通过事务把开场绑定、推进实播和收场解绑各自作为一次提交。
