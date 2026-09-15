"""Reproducible search benchmark; random boards are not assumed solvable."""
import json
import random
import time
from pathlib import Path
from app.zhuan.solver import solve, format_solution
from app.zhuan.bad_case import bad_case_1,bad_case_2

cases=[('original_bad_case_1',bad_case_1()),('original_bad_case_2',bad_case_2()),
       ('user_first_level',json.loads(Path('examples/first-level/board.json').read_text()))]
for seed in range(20):
    values=list(range(1,36))*4
    random.Random(seed).shuffle(values)
    cases.append((f'random_full_seed_{seed}',[values[i:i+10] for i in range(0,140,10)]))
reports=[]
for name,board in cases:
    r=solve(board,seconds=5,max_nodes=50000)
    if r.verified: format_solution(board,r)
    reports.append({'case':name,'status':r.status,'steps':len(r.actions),'expanded':r.expanded,
                    'seconds':round(r.elapsed,4),'phase':r.phase,'verified':r.verified})
    print(reports[-1],flush=True)
Path('benchmarks/results.json').write_text(json.dumps(reports,indent=2))
