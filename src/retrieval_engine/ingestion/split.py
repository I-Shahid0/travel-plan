from datetime import date, datetime

from retrieval_engine.db.models import EvalSplit


def assign_eval_split(occurred_at: datetime, cutoff: date) -> EvalSplit:
    event_date = occurred_at.date()
    return EvalSplit.TRAIN if event_date < cutoff else EvalSplit.TEST
