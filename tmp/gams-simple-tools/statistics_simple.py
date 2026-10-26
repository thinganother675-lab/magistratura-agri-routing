from pathlib import Path
import sys, csv
root = Path('C:/sarychev/Codex/magistratura')
sys.path.insert(0, str(root/'coursework/mmm-ppr/variant-11/runtime/python_packages'))
import numpy as np
from scipy.stats import rankdata, spearmanr
folder = Path(sys.argv[1])
with (folder/'input_data.csv').open() as f:
    data = list(csv.DictReader(f))
with (folder/'efficiencies.csv').open() as f:
    scores = list(csv.DictReader(f))
assert len(data) == len(scores) == 25
assert [r['firm'] for r in data] == [r['firm'] for r in scores]
assert all(r['modelstat'] == '1' and r['solvestat'] == '1' for r in scores)
efficiency = np.array([float(r['efficiency']) for r in scores])
efficiency[np.abs(efficiency-1) < 1e-9] = 1
lawyers = np.array([float(r['x1']) for r in data])
economists = np.array([float(r['x2']) for r in data])
size = lawyers + economists
share = lawyers / size
rank = rankdata(efficiency)
rank = (rank-rank.mean()) / np.linalg.norm(rank-rank.mean())
results = []
for name, values in [('size', size), ('share', share)]:
    rho, asymptotic = spearmanr(efficiency, values)
    other = rankdata(values)
    other = (other-other.mean()) / np.linalg.norm(other-other.mean())
    random = np.random.default_rng(20261024)
    extreme = 0
    for start in range(0, 199999, 10000):
        count = min(10000, 199999-start)
        permutations = np.array([random.permutation(rank) for _ in range(count)])
        extreme += np.count_nonzero(np.abs(permutations@other) >= abs(rho)-1e-12)
    results.append([name, 25, rho, (extreme+1)/200000, asymptotic])
with (folder/'spearman.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['predictor', 'n', 'rho', 'p_permutation', 'p_asymptotic'])
    writer.writerows(results)
with (folder/'ranks.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['firm', 'efficiency', 'size', 'share', 'rank_efficiency', 'rank_size', 'rank_share'])
    for i in range(25):
        writer.writerow([data[i]['firm'], efficiency[i], size[i], share[i],
            rankdata(efficiency)[i], rankdata(size)[i], rankdata(share)[i]])
for row in results:
    print(row)
