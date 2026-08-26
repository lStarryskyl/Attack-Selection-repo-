from oracle_gap.classification import _weighted_auc


def test_weighted_auc_handles_perfect_order_and_ties():
    assert _weighted_auc([(2.0, 1), (3.0, 1)], [(0.0, 1), (1.0, 1)]) == 1.0
    assert _weighted_auc([(1.0, 2)], [(1.0, 3)]) == 0.5


def test_weighted_auc_respects_cluster_weights():
    # One positive beats one negative and ties the two-weight negative cluster.
    assert _weighted_auc([(2.0, 1)], [(1.0, 1), (2.0, 2)]) == 2 / 3
