import itertools
import unittest
from app.zhuan.board_state import BoardState
from app.zhuan.solver import solve, format_solution
from app.zhuan.verifier import replay_step, verify_route


def board(rows):
    return [list(r)+[0]*(10-len(r)) for r in rows]+[[0]*10 for _ in range(14-len(rows))]


class SolverTests(unittest.TestCase):
    def test_all_match_directions(self):
        b = board([[0,1,0],[1,0,1],[0,1,0]])
        moves = BoardState(b).available_moves()
        self.assertIn(((1,0),(1,1),'up'), moves)
        self.assertIn(((1,0),(1,1),'down'), moves)

    def test_push_and_collision(self):
        b = board([[1,2,0,0,3],[0,0,1]])
        after,target = replay_step(b, ((0,0),(0,2),'down'))
        self.assertEqual(after[0][:5],(0,0,0,2,3))
        with self.assertRaises(ValueError):
            replay_step(b, ((0,0),(0,3),'down'))

    def test_invalid(self):
        for action in [((-1,0),(0,0),'up'),((0,0),(1,1),'up'),((0,1),(0,1),'right')]:
            with self.assertRaises(ValueError):
                replay_step(board([[1,0,1]]),action)
        with self.assertRaises(ValueError):
            verify_route(board([[1,1]]),[])

    def test_statuses_and_fallback(self):
        b = board([[1,1],[2,2]])
        for budget in (0,1,2000):
            result = solve(b,gbfs_nodes=budget)
            self.assertTrue(result.verified)
            self.assertEqual(len(result.actions),2)
            verify_route(b,result.actions)
            self.assertIn('直接消除',format_solution(b,result))
        self.assertEqual(solve(board([[1]])).status,'unsolvable')
        self.assertEqual(solve(b,max_nodes=1,gbfs_nodes=0).status,'budget_exhausted')
        self.assertEqual(solve(board([])).status,'solved')

    def test_exhaustive_small_boards(self):
        # Independent brute-force destination/direction enumeration vs optimized generator.
        for values in itertools.product(range(3), repeat=4):
            b=board([values[:2],values[2:]])
            expected=set()
            for r,c in itertools.product(range(2),repeat=2):
                if not b[r][c]: continue
                for er,ec in itertools.product(range(14),range(10)):
                    if r != er and c != ec: continue
                    for d in ('up','down','left','right'):
                        try: state,_=replay_step(b,((r,c),(er,ec),d))
                        except ValueError: continue
                        expected.add(state)
            actual={tuple(map(tuple,BoardState(b).apply_move_copy(*a))) for a in BoardState(b).available_moves()}
            self.assertEqual(expected,actual,values)

if __name__ == '__main__': unittest.main()
