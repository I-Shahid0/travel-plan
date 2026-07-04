from datetime import date, datetime

from retrieval_engine.db.models import EvalSplit
from retrieval_engine.ingestion.split import assign_eval_split


def test_assign_eval_split_train():
    before = datetime(2019, 12, 31, 23, 59, 59)
    assert assign_eval_split(before, date(2020, 1, 1)) == EvalSplit.TRAIN


def test_assign_eval_split_test():
    assert assign_eval_split(datetime(2020, 1, 1, 0, 0, 0), date(2020, 1, 1)) == EvalSplit.TEST
