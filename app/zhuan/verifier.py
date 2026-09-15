"""Strict replay engine. Does not trust move enumeration or cached search states."""
from collections import Counter

DIRECTIONS = {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}


def validate_board(board):
    if not board or not board[0] or any(len(row) != len(board[0]) for row in board):
        raise ValueError('棋盘必须是非空矩形')
    if any(type(v) is not int or v < 0 for row in board for v in row):
        raise ValueError('棋盘只能包含非负整数；0 表示空格')
    return tuple(tuple(row) for row in board)


def replay_step(board, action):
    board = validate_board(board)
    rows, cols = len(board), len(board[0])
    start, end, direction = action
    def inside(p):
        return len(p) == 2 and all(type(v) is int for v in p) and 0 <= p[0] < rows and 0 <= p[1] < cols
    if not inside(start) or not inside(end) or direction not in DIRECTIONS:
        raise ValueError('动作坐标或方向无效')
    r, c = start
    er, ec = end
    if not board[r][c] or (r != er and c != ec):
        raise ValueError('起点为空或斜向移动')
    dr, dc = (er > r) - (er < r), (ec > c) - (ec < c)
    distance = abs(er-r) + abs(ec-c)
    sr, sc = DIRECTIONS[direction]
    if distance and dr*sr + dc*sc:
        raise ValueError('移动后只能沿垂直于移动的方向匹配（原项目规则）')
    cells = [list(row) for row in board]
    if distance:
        # Advance one cell at a time; push the entire contiguous run.
        for step in range(distance):
            head = (r + step*dr, c + step*dc)
            run = []
            rr, cc = head
            while 0 <= rr < rows and 0 <= cc < cols and cells[rr][cc]:
                run.append((rr, cc))
                rr, cc = rr+dr, cc+dc
            if not (0 <= rr < rows and 0 <= cc < cols):
                raise ValueError('推移越界')
            # The original rules allow only the initial run to slide through empty space.
            if step and len(run) != run_length:
                raise ValueError('移动路径被其他砖块挡住')
            run_length = len(run)
            for rr, cc in reversed(run):
                cells[rr+dr][cc+dc] = cells[rr][cc]
                cells[rr][cc] = 0
    rr, cc = er+sr, ec+sc
    while 0 <= rr < rows and 0 <= cc < cols and not cells[rr][cc]:
        rr, cc = rr+sr, cc+sc
    if not (0 <= rr < rows and 0 <= cc < cols) or cells[rr][cc] != cells[er][ec]:
        raise ValueError('指定方向最近的砖块不匹配')
    target = (rr, cc)
    cells[rr][cc] = cells[er][ec] = 0
    result = tuple(tuple(row) for row in cells)
    if sum(v != 0 for row in board for v in row) - sum(v != 0 for row in result for v in row) != 2:
        raise ValueError('一步必须恰好消除两块')
    return result, target


def verify_route(initial, actions, expected_states=None):
    board = validate_board(initial)
    targets = []
    for index, action in enumerate(actions):
        board, target = replay_step(board, action)
        targets.append(target)
        if expected_states is not None and board != expected_states[index]:
            raise ValueError(f'第 {index+1} 步与搜索状态不一致')
    if any(v for row in board for v in row):
        raise ValueError('路线结束后棋盘未清空')
    return targets
