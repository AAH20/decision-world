# Benchmarks and unit economics

## What a better decision engine must prove

| Claim | Baseline | Primary evidence |
| --- | --- | --- |
| Better demand forecast | Static rate and simple elasticity | Time-held-out MAE, log loss, calibration across sites |
| Better intervention ranking | Cheapest feasible action and analyst plan | Prospectively measured regret and incremental contribution |
| Swarm adds value | Deterministic reference planner | Same-data ablation with and without agent policies |
| GraphRAG adds value | Licensed-source lexical/vector retrieval | Grounded assumption precision versus index/query cost |
| Optimization adds value | Bounded enumeration | Same objective and constraints, with time-to-solution |
| Safe operations | Advisory-only dry run | Zero unauthorized executions in the test set, authenticated approvals |

The first published fixture is **synthetic**. Its selected support intervention has no demonstrated real-world benefit. Before claiming business lift, freeze the world specification, use consented historical data with an information cutoff, compare against simple baselines, then run a randomized pilot with predeclared metrics and stopping rules.

## Reference cost accounting

The fixture evaluates 10 feasible plans × 80 runs × 7 days = **5,600 world-steps**. It assigns illustrative rates of `$0.02` per 1,000 world-steps plus `$0.005` storage per 11 enumerated plans. Thus compute is `$0.112`, storage `$0.055`, direct reference cost `$0.167`, and with a 30% allowance `$0.2171` per full planning run. These numbers are **input assumptions**, not cloud invoices. The meter excludes provider tokens, indexing, data engineering, review, deployment, and customer support.

Production COGS should be measured as:

```text
planning_cogs = ingest + graph_index_amortization + simulation_compute
              + model_input + model_output + optimizer_compute
              + storage + observability + human_review
```

```text
tenant_gross_margin = recurring_revenue + usage_revenue
                    - planning_cogs - serving_cogs - allocated_support
```

Budget every experiment by world-steps, provider calls, token limits, wall time, and storage. Publish p50 and p95 COGS per accepted recommendation, plus the measured incremental contribution created by controlled pilots. A large synthetic swarm that costs more but does not improve decisions should be removed from the critical path.
