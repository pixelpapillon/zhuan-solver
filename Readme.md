# 砖了个砖：完整路线求解与复验版

基于 [switchball/zhuan-solver](https://github.com/switchball/zhuan-solver)，基线提交 `cb7f6f9c73cc5b8ab117cb2cba06b64b992ab9c4`。

目标：**正确通关优先，速度第二，不优化最短步数**。输入完整截图或已核对棋盘，输出一次性完整中文路线。默认入口不控制鼠标、不依赖微信窗口或Windows。

## 快速运行

Python 3.10+。纯矩阵求解和核心测试只需标准库；截图初识需要额外依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# 已核对的用户第一关截图：直接复现求解
python solve.py --board examples/first-level/board.json --output result
# 独立重新复验保存的完整答案
python verify.py result/solution.json
# 全部核心回归测试
python -m unittest discover -s tests -v
```

`python main_entry.py` 与 `python solve.py` 是同一个新入口，均需要输入参数。

主要文件：

| 文件 | 作用 |
|---|---|
| `solve.py` | 文件入口；读取棋盘或截图，启动求解并只导出已验证路线 |
| `app/zhuan/board_state.py` | 棋盘状态、投影棋盘和完整动作枚举 |
| `app/zhuan/solver.py` | GBFS、短回溯、DFS fallback、状态缓存和路线格式化 |
| `app/zhuan/verifier.py` | 独立的逐格转移和完整路线复验 |
| `app/zhuan/screenshot.py` | 棋盘网格定位、模板初识和识别审计文件 |
| `verify.py` | 对保存的 `solution.json` 再次复验，不重新搜索 |
| `tests/` | 单元测试、转移实现对照和用户截图回归测试 |

### 新截图

```bash
python solve.py --image screenshot.jpg --output result
# 自动定位失败时，助手可按原图确定像素裁剪范围：
python solve.py --image screenshot.jpg --crop 30 490 880 1250 --output result
# 助手逐行核对、修正 result/board.json 后：
python solve.py --board result/board.json --output result --seconds 300 --max-nodes 1000000
python verify.py result/solution.json
```

`solve.py --board` 的参数是：`--seconds` 总时间预算（默认120秒）、`--max-nodes` 最大展开节点数（默认200000）、`--gbfs-nodes` GBFS阶段节点数（默认2000）、`--cache-size` 死状态缓存上限（默认100000）。提高预算会增加找到路线的机会，也会增加最坏情况下的运行时间和内存占用。

截图入口生成：`recognized.png`（网格/标签）、`recognition.json`（裁剪/每格图像距离/候选问题）、`board.auto.json`（原始候选矩阵）、`board.json`（待人工核对的副本）。截图命令退出码2表示需要核对，不产生答案。**用户在对话里只需给截图，识别核对由助手完成，不需要用户录入矩阵。** 此版本没有把视觉核对伪装为无人值守自动识别。

采用亮色砖块轮廓定位完整14×10格网，使用原仓库训练样本做模板初识；支持缩放和不同截图顶部高度。自动定位不能可靠覆盖缺边砖、遮挡、换皮等情况，可由助手视觉定位后指定裁剪。图像距离不是置信概率。

第一关实测初识错10格，且每种图案数量依然是偶数。助手已逐行核对纠正，记录在 `examples/first-level/review.json`；`board.auto.json` 保留原结果，`board.json` 为核对后输入。**不能凭成对计数或求解成功证明识别正确。**

## 原算法的问题

1. `check_single_move` 只返回首个匹配方向。上下/左右同时能配对时，会遗漏另一后继状态。问题在动作生成器；GBFS本身在有限状态空间、正确完整生成后继且不受资源限制时可穷尽。
2. heuristic只有已消除块数。每步消两块，同深度几乎全打平；搜索容易陷入某条选择的巨大失败子树。
3. 搜索没有时间、扩展数量、缓存限制，也没有保留内存的fallback；前沿、父节点和投影数据会持续增长。
4. 没有从最初棋盘逐步重放整条路线的最终出口检查；原移动执行函数对输入的防御不足。
5. BFS把邻居当作节点，但ZhuanNode返回 `(节点, 动作)`，接口不匹配。已修复BFS邻居解包与动作回溯，并给旧GBFS增加稳定序号打破同优先级平局；新入口使用组合求解器。
6. 原入口依赖Windows窗口；旧自动控制还可能在棋盘与缓存路线不一致时继续执行旧动作。本版将默认入口改为文件求解，同时删除了缓存不匹配时继续点击的逻辑。

## 搜索结构

### 状态、动作和转移

棋盘用不可变的 `14×10` 整数矩阵表示，`0` 是空格，正整数是图案类别。一个搜索节点只包含棋盘状态；到达该节点的动作单独保存在父节点表中，因此同一个棋盘状态不会因为不同历史路径而重复展开。

一个动作写成 `(start, end, match_direction)`：`start` 是被操作的砖块，`end` 是同一行或同一列上的落点，`match_direction` 是从落点寻找配对砖块的方向。移动会把起点处连续相连的一段砖块推入空格，然后从落点沿匹配方向跳过空格，遇到的第一个砖块必须与落点同图案；两块随后同时清除。`start == end` 表示不推移、直接寻找配对。

动作生成分为两步。`_available_moves_by_line` 先计算每个砖块沿行或列能到达的合法落点；`check_single_moves` 再对每个落点保留全部匹配方向。水平推移检查上下，垂直推移检查左右。旧实现使用单数 `check_single_move`，遇到两个方向都匹配时只保留第一个；新版保留两个分支，再按结果棋盘去重。这是搜索完备性的必要条件。

下面是求解器的核心流程（伪代码）：

```text
solve(initial):
    reject malformed board or odd tile counts
    frontier ← GBFS(start)
    while GBFS budget remains:
        state ← pop highest-priority state
        if state is empty: verify and return route
        for (next_state, action) in all_legal_successors(state):
            add unseen next_state with its parent/action

    for fixed random seeds:
        run a short DFS with a different child order
        cache only branches that were completely proven dead

    run full transposition-aware DFS while budget remains
    if a goal is found: replay from initial and return only if verified
```

1. **完整枚举**：保留每个移动的全部匹配方向；按实际后继棋盘去重。
2. **执行歧义保护**：默认排除同一个点击/拖动有多个匹配方向的动作。原项目没有验证游戏在这种情况下选择哪个对象。本版输出不依赖这个未知规则。
3. **GBFS快速阶段**：优先更多消除，其次优先较少暂时受阻的图案种类，再看可用动作数。启发式仅排序，绝不据此证明死局。
4. **多次短回溯**：64个固定随机种子，每次256个扩展预算，从初始局面改变分支顺序；避免反复困在同一个早期选择。完全失败的状态可共享，半途截断的分支绝不标记为无解。
5. **完整DFS兜底**：前面没找到，就从初始局面执行不截断分支的回溯，缓存已穷尽且失败的状态。缓存满后停止增加缓存，不删除合法分支。

### 为什么不直接使用 A* 或最短路搜索

目标只要求通关。由于每个合法动作固定清除两块砖，完整解的深度通常就是剩余砖块数除以二；寻找最短路线不会带来游戏收益，却会让队列和状态记忆显著增加。GBFS 先快速尝试高收益分支，回溯阶段再保证可以换路；启发式从不被当作“不可行”判据。

### 死状态缓存的正确性

搜索图每条边都会减少非空砖块数，所以不存在环。只有当一个状态的所有允许后继都已被完整搜索且没有到达空棋盘时，才把该状态加入 `dead` 缓存。因时间或节点预算中断的路径不会被标记为死状态，避免把“尚未搜索完”误当成“无解”。

默认总预算120秒、200000次扩展，GBFS阶段2000次扩展，状态缓存100000。`--seconds`、`--max-nodes`、`--gbfs-nodes`、`--cache-size`可调整。预算是整个组合搜索的，不是每个阶段单独重置。时间限制在扩展与后继生成边界检查，允许单次计算的少量超时。GBFS缓存阈值在扩展边界检查，可能多出一个节点的后继；不是硬字节级内存限制。

在当前模型中每个动作恰好消除两块，搜索图无环，深度最多70。完整DFS在没有资源限制时对**所允许的动作集合**可穷尽；默认无歧义模式限制了动作集合，所以找不到安全路线不等于原游戏无解。

研究API `solve(board, allow_ambiguous=True)` 可搜索原模型的所有方向，但 `format_solution` 和 `verify.py` 会拒绝把有歧义的路线作为可执行操作导出。当前命令行不开放该选项。

## 最终验证

- 搜索使用快速的整段复制推移。
- `verifier.py`用另一套逐格推移算法，从原始不可变棋盘重新执行动作，不信任父节点链和缓存棋盘。
- 检查边界、直线方向、非空起点、整段推移、后续障碍、最近可见同图案匹配、每步恰好减2，并与每步搜索状态比较。
- 最后必须剩余0块。
- 输出前再次重放，并检查所有点击/拖动的匹配方向唯一。
- 未通过的结果不生成 `solution.txt`；每次运行清理同输出目录的旧答案，避免将旧解当新解。

状态：

| 状态 | 含义 |
|---|---|
| `solved` | 已找到并重放验证完整解 |
| `budget_exhausted` | 达到时间/节点限制，不能断言无解 |
| `no_unambiguous_route` | 无歧义动作集合已穷尽，没有路线，不能断言原游戏无解 |
| `unsolvable` | 图案奇数不变量，或研究模式完整穷尽后证明该模型无解；截图应先排查识别错误 |

## 测试与实测

```bash
python -m unittest discover -s tests -v
PYTHONPATH=. python benchmarks/run.py
```

测试覆盖双方向漏解、推动连续砖块、碰撞/越界/空起点、回溯fallback、预算状态、篡改路径拒绝、配对歧义拒绝、错误中间棋盘拒绝、用户截图70步重放。

还包括：81个2×2种子布局放入14×10棋盘后，穷举起点/终点/方向，与优化生成器的完整后继集合对照；120个固定种子随机棋盘上，比较快速推移与逐格推移的每个合法动作结果。

本机回归13项全部通过。23个基准局面中22个找到无歧义完整解并验证，另1个返回 `no_unambiguous_route`；本次均未耗尽5秒单局预算。用户第一关140块以70步清空，搜索约0.6秒；这是核对后矩阵的搜索耗时，不含截图识别和视觉核对。实测详情见 `benchmarks/results.json`。随机满盘采用固定种子、35种图案各4块；这些输入没有预先保证可解，不能把测试结果直接当作真实游戏通关概率。

## 坐标与规则边界

坐标从上到下第1–14行、从左到右第1–10列，**空格也计数，不按剩余砖块重新编号**。每一步起点是执行到该步时的棋盘位置。移动连续砖块时，起点前方相连的一段会一起移动；配对坐标指完成移动后的位置。

沿用原项目：直线推动连续砖块，只能利用紧邻空隙；移动后与垂直方向最近的同图案配对；直接消除允许四个方向最近的同图案；每步消除两块，无重力、无新增砖块、无工具。若真实游戏规则不同（例如需要不消除的铺垫移动、隐藏层或自动连消），需要扩展状态模型。

**已做的是棋盘规则模型内的完整验证，尚未在真实客户端逐步操作验证。** 默认无歧义路线降低配对选择的不确定性，但不可能从一张图证明客户端所有规则或手势行为。截图识别不准、动画遮挡、新图案/皮肤、规则改变、局面无解、预算耗尽，都仍可能失败。

旧窗口控制入口保存在 `legacy_main_entry.py`，依赖见 `requirements-windows-legacy.txt`，不是本版推荐的使用方式。
