import json
import random
import unittest
from pathlib import Path
from app.zhuan.board_state import BoardState
from app.zhuan.solver import solve, format_solution, Result
from app.zhuan.verifier import replay_step, verify_route
from app.zhuan.bad_case import bad_case_1, bad_case_2


class IntegrationTests(unittest.TestCase):
    def test_two_transition_engines(self):
        rng=random.Random(431)
        for _ in range(120):
            values=[rng.randrange(5) for _ in range(140)]
            b=BoardState([values[i:i+10] for i in range(0,140,10)])
            for action in b.available_moves():
                expected,_=replay_step(b.tiles,action)
                self.assertEqual(expected,tuple(map(tuple,b._apply_generated_move_copy(*action))))

    def test_tampered_route_rejected(self):
        b=[[0]*10 for _ in range(14)]; b[0][:2]=[1,1]
        r=solve(b)
        r.actions[0]=((0,0),(0,0),'up')
        with self.assertRaises(ValueError): format_solution(b,r)
        with self.assertRaises(ValueError): format_solution(b,Result('budget_exhausted'))

    def test_inconsistent_search_state_rejected(self):
        b=[[0]*10 for _ in range(14)]; b[0][:2]=[1,1]
        with self.assertRaises(ValueError):
            verify_route(b,[((0,0),(0,0),'right')],[tuple(map(tuple,b))])

    def test_ambiguous_route_not_exported(self):
        b=[[0]*10 for _ in range(14)]; b[0][:4]=[1,1,1,1]
        actions=[((0,1),(0,1),'left'),((0,2),(0,2),'right')]
        verify_route(b,actions)
        with self.assertRaises(ValueError):
            format_solution(b,Result('solved',actions,verified=True))

    def test_original_fixtures(self):
        for f in (bad_case_1,bad_case_2):
            r=solve(f(),seconds=30,allow_ambiguous=True)
            self.assertEqual(r.status,'solved')
            verify_route(f(),r.actions)


class SavedScreenshotTests(unittest.TestCase):
    def test_user_screenshot_saved_solution(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/'examples/first-level/solution.json').read_text())
        initial=json.loads((root/'examples/first-level/board.json').read_text())
        self.assertEqual(initial,data['initial'])
        actions=[(tuple(a),tuple(b),d) for a,b,d in data['actions']]
        self.assertEqual(len(actions),70)
        verify_route(initial,actions)
        format_solution(initial,Result('solved',actions,verified=True))

    def test_restarts_solve_user_screenshot(self):
        root=Path(__file__).resolve().parents[1]
        initial=json.loads((root/'examples/first-level/board.json').read_text())
        result=solve(initial,seconds=20)
        self.assertEqual(result.status,'solved')
        self.assertEqual(result.phase,'restarts')
        self.assertEqual(len(result.actions),70)

class CompatibilityTests(unittest.TestCase):
    def test_generic_search_interfaces(self):
        from state.search import BFS, GBFS
        from app.zhuan.zhuan_node import ZhuanNode
        for algorithm in (BFS, GBFS):
            board=[[0]*10 for _ in range(14)]
            board[0][:4]=[1,1,2,2]
            path=algorithm(ZhuanNode(BoardState(board))).search()
            self.assertTrue(path[-1].is_goal())
            verify_route(board,[node.from_action for node in path[1:]])

if __name__ == '__main__': unittest.main()
