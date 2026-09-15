"""Bounded GBFS followed by exhaustive, transposition-aware DFS.

Every edge removes two tiles: finite DAG, depth <= 70, no shortest-path objective.
Only fully explored failures enter the DFS dead-state cache.
"""
import heapq
import itertools
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from app.zhuan.board_state import BoardState
from app.zhuan.verifier import validate_board, verify_route


@dataclass
class Result:
    status: str
    actions: list = field(default_factory=list)
    expanded: int = 0
    elapsed: float = 0
    phase: str = ''
    verified: bool = False
    reason: str = ''


class BudgetExceeded(Exception):
    pass


def solve(initial, seconds=120, max_nodes=200000, gbfs_nodes=2000, cache_size=100000, allow_ambiguous=False):
    initial = validate_board(initial)
    start = BoardState(initial)
    if seconds <= 0 or max_nodes < 1 or gbfs_nodes < 0 or cache_size < 0:
        raise ValueError('搜索预算无效')
    began = time.monotonic()
    result = Result('budget_exhausted')
    counts = Counter(v for row in initial for v in row if v)
    if any(n % 2 for n in counts.values()):
        return Result('unsolvable', reason='存在奇数个图案；请先排查截图识别错误')

    def check():
        if time.monotonic()-began >= seconds or result.expanded >= max_nodes:
            raise BudgetExceeded

    def children(board):
        seen = set()
        moves = board.available_moves()
        groups = {}
        for action in moves:
            groups.setdefault(action[:2], set()).add(action[2])
        for action in moves:
            if not allow_ambiguous and len(groups[action[:2]]) > 1:
                continue
            check()
            child = BoardState(board._apply_generated_move_copy(*action))
            if child not in seen:
                seen.add(child)
                yield child, action

    def rank(board):
        # Prefer states in which more remaining pattern types have a legal removal.
        # Ordering only: blocked types are NOT pruned (pushing may unlock them).
        moves = board.available_moves()
        groups = {}
        for a in moves:
            groups.setdefault(a[:2], set()).add(a[2])
        usable = [a for a in moves if allow_ambiguous or len(groups[a[:2]]) == 1]
        remaining = {v for row in board.tiles for v in row if v}
        active = {board.tiles[a[0][0]][a[0][1]] for a in usable}
        return (len(remaining-active), -len(usable))

    def success(actions, states):
        verify_route(initial, actions, states)
        result.status, result.actions, result.verified = 'solved', actions, True

    def reconstruct(board, parents):
        actions, states = [], []
        while parents[board] is not None:
            prev, action = parents[board]
            actions.append(action)
            states.append(board.tiles)
            board = prev
        return actions[::-1], states[::-1]

    try:
        result.phase = 'gbfs'
        serial = itertools.count()
        queue = [((0, 0, 0), next(serial), start)]
        parents = {start: None}
        while queue and result.expanded < gbfs_nodes and len(parents) < max(1, cache_size):
            _, _, board = heapq.heappop(queue)
            if board.elimated_tiles() == 140:
                success(*reconstruct(board, parents))
                break
            check()
            result.expanded += 1
            for child, action in children(board):
                if child not in parents:
                    parents[child] = (board, action)
                    heapq.heappush(queue, ((-child.elimated_tiles(), *rank(child)), next(serial), child))
            # Bound frontier storage; fallback restarts from the original board.
        else:
            if not queue:
                result.status = 'unsolvable'
        if result.status == 'budget_exhausted':
            del queue, parents
            dead = set()
            actions, states = [], []
            class RestartBudget(Exception):
                pass
            local_limit = None
            rng = None
            def visit(board):
                if board.elimated_tiles() == 140:
                    success(list(actions), list(states))
                    return True
                check()
                if local_limit is not None and result.expanded >= local_limit:
                    raise RestartBudget
                if board in dead:
                    return False
                result.expanded += 1
                candidates = list(children(board))
                if rng is not None:
                    rng.shuffle(candidates)
                else:
                    candidates.sort(key=lambda pair: rank(pair[0]))
                for child, action in candidates:
                    actions.append(action)
                    states.append(child.tiles)
                    if visit(child):
                        return True
                    actions.pop()
                    states.pop()
                # Interrupted branches never reach here: only proven dead states cached.
                if len(dead) < cache_size:
                    dead.add(board)
                return False
            result.phase = 'restarts'
            for seed in range(64):
                rng = random.Random(seed)
                local_limit = result.expanded + 256
                actions.clear()
                states.clear()
                try:
                    if visit(start):
                        break
                    result.status = 'unsolvable'
                    break
                except RestartBudget:
                    pass
            if result.status == 'budget_exhausted':
                result.phase = 'dfs'
                rng = None
                local_limit = None
                actions.clear()
                states.clear()
                if not visit(start):
                    result.status = 'unsolvable'
    except BudgetExceeded:
        result.reason = '达到时间或节点预算；不代表无解'
    if result.status == 'unsolvable' and not allow_ambiguous:
        result.status = 'no_unambiguous_route'
        result.reason = '已穷尽无歧义动作；不能据此断言原棋盘无解'
    result.elapsed = time.monotonic()-began
    return result


def format_solution(initial, result):
    if result.status != 'solved' or not result.verified:
        raise ValueError('只允许输出已验证的完整路线')
    targets = verify_route(initial, result.actions)
    # Output policy: no reliance on an unconfirmed in-game tie-breaking direction.
    board = BoardState(initial)
    for action in result.actions:
        matches = {a[2] for a in board.available_moves() if a[:2] == action[:2]}
        if len(matches) != 1:
            raise ValueError('路线包含配对方向歧义，禁止输出为可执行答案')
        board = BoardState(board.apply_move_copy(*action))
    names = {'up': '上', 'down': '下', 'left': '左', 'right': '右'}
    lines = ['坐标：固定棋盘网格，从上到下数行、从左到右数列，均从1开始；空格也计数。']
    for i, ((start, end, match), target) in enumerate(zip(result.actions, targets), 1):
        r,c = start
        er,ec = end
        if start == end:
            text = '直接消除'
        else:
            direction = 'down' if er>r else 'up' if er<r else 'right' if ec>c else 'left'
            text = f'向{names[direction]}移动{abs(er-r)+abs(ec-c)}格'
        lines.append(f'{i}. 第{r+1}行第{c+1}个 → {text}（与第{target[0]+1}行第{target[1]+1}个配对）')
    return '\n'.join(lines)
