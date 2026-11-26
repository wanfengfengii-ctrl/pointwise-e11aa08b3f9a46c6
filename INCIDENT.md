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
