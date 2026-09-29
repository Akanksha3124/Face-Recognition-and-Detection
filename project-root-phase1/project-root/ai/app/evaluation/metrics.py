"""
Shared evaluation metrics: accuracy, precision, recall, FMR, FNMR,
ROC-AUC, top-1/top-5 accuracy, inference time. Implemented alongside
Phase 11-12 evaluation work and reused by the Phase 17 test suite.
"""


def compute_metrics(predictions, ground_truth) -> dict:
    raise NotImplementedError("Implemented in Phase 11")
