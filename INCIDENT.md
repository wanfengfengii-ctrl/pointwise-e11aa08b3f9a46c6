# 双剪辑放映的现场对照

## 校样与发号

用 `samples/incompatible.json` 比较两次单版放映与一次双版放映。只送甲版或只送乙版都可以发行。两版放在同一张节目单上时，确认拍是第 2 拍。甲要求两拍的 A 在第 2 拍结束前播完，乙要求一拍的 B 在同一截止拍前播完。共同开场只有 `[0,2)`。双版校样应拒绝，发行请求应返回 409 且无发行号。

## 实际播出与收场

用 `samples/branching.json` 取同一发行分别开一场甲和一场乙。第 0、1 拍连续播 A，第 2 拍报场内实际提示。甲场在 `[3,4)` 播 B。乙场第 3 拍等待，在 `[4,5)` 播 B。两场均应成功收场，实播账各有 A、B 两段。

原回归还用 `samples/crossing.json` 核对 A 已经在播时收到乙提示的情况，A 在 `[0,3)` 连续播完，B 仍在 `[4,5)` 播出。

## 重跑

从项目根目录运行以下命令。第一条对两起事故走实际 HTTP 路径。第二条执行全部原回归。第三条演示乙场从录入、开场、接班到收场及重开后的原号复读。

```sh
python3 -B -m unittest tests.test_release.ReleaseTests.test_incompatible_opening tests.test_show.ShowTests.test_actual_edition
python3 -B check_project.py
python3 -B -m tests.test_http --demo
```

日常请求和服务启动参数见 README.md。运行清单启动服务时使用本机回环地址和指定端口，`GET /health` 返回 200 表示服务可接收请求。上述核验和演示各自创建测试用库。

## 故障原因与修复实测

### 故障原因

1. `release/feasibility.py` 的双剪辑校样只评估 `revision.editions[0]`，并把 `shared_starts` 留空。因此甲版能排完整日程时，`incompatible.json` 也被误判为可发行；它没有检查第 2 拍提示前两版必须采用同一组启动/等待决定，也没有分别核对两版在提示后的完整续程。
2. `show/playback.py` 在已经收到乙提示后仍固定取 `revision.editions[0]`，于是乙场沿用甲版的 `B@3`。乙版 `[2,4)` 是原声窗，B 的 `[3,4)` 压住原声；实播核账据此将 B 判为不一致并拒绝收场。

### 修复要点

- 校样先求两版安静窗的公共交集和最严截止，枚举提示前的共同走法；跨提示拍的在播段按公共约束整段校验。对每个可行共同前缀，再分别求甲、乙从提示拍或在播段结束拍开始的完整续程。只有两版都能播完才写入 `DecisionBasis` 并允许发行。
- 放映决策在提示前只查 `shared_starts`，并按两版约束校验；收到提示后按实际 `edition_id` 选择该版续程。提示仍由 `accept_signals` 在同拍启动判断前受理，缺提示抛 `signal_required`，非法提示在事务内回滚。
- 新增 `test_common_wait_is_shared_before_confirmation`：锁住“第 0 拍共同等待、第 1 拍共同播 A，提示后甲 B 在 `[2,3)`、乙 B 在 `[4,5)`”的分支。

### 实际结果

修复前运行 `python3 -B check_project.py`：22 个测试中 7 个失败，覆盖双版误发行、甲乙实际走拍、跨提示段、第 0 拍提示、未知提示原子性、接班和 HTTP 日流程。

修复后：

- `python3 -B -m unittest tests.test_release.ReleaseTests.test_incompatible_opening tests.test_show.ShowTests.test_actual_edition` 通过。
- 甲场实测为 A `[0,2)`、B `[3,4)`；乙场为 A `[0,2)`、B `[4,5)`，两场均可按原场号收场和复读。
- `crossing.json` 维持 A `[0,3)` 跨提示连续播完、B `[4,5)`。
- 新增共同等待场景通过。
- `python3 -B check_project.py` 最终为 23 个测试全部通过（`result=PASS`）。
- `python3 -B -m tests.test_http --demo` 的乙场 HTTP 接班、收场、重开复读演示通过。
