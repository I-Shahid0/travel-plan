# Eval split — frozen configuration

## Policy

Interactions are split on a **temporal boundary** to prevent leakage: the model and retrieval index may only learn from past behavior; evaluation uses future interactions.

| Field | Value |
|-------|-------|
| **Cutoff date** | `2020-01-01` |
| **Train** | `occurred_at < 2020-01-01` |
| **Test** | `occurred_at >= 2020-01-01` |

## Included interaction types

| Type | Source file | Notes |
|------|-------------|-------|
| `review` | `data/archive/yelp_academic_dataset_review.json` | Includes star rating |
| `tip` | `data/archive/yelp_academic_dataset_tip.json` | Implicit positive signal |

## Excluded

- **Checkins** (`data/archive/yelp_academic_dataset_checkin.json`) — no `user_id` in the Yelp schema; cannot attribute to a user for personalization eval.
- **Users** (`data/archive/yelp_academic_dataset_user.json`) — not loaded in Phase 0; reserved for Phase 4.5 personalization features.

## Reproducing

```bash
uv run ingest --cutoff 2020-01-01
```

Counts are persisted in `eval_split_metadata` and exposed at `GET /eval/split`.

## Rationale for 2020-01-01

A mid-corpus cutoff balances train volume (pre-2020 reviews are abundant) with a meaningful held-out test window (2020–2022 activity in the Yelp academic snapshot). Adjust via `EVAL_SPLIT_CUTOFF` if you re-run ingestion; document any change here.
