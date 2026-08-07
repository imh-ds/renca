# Multi-pair FWER under v4 — familywise control holds

5,000 replications from GitHub Actions run
[31201703021](https://github.com/imh-ds/renca/actions/runs/31201703021), 2026-08-07, bound
to `v4-cubic-blend-n300-d005-phase0`. Identical protocol and configuration to
[`../multipair-fwer-2blocks-n375-materiality-q04/`](../multipair-fwer-2blocks-n375-materiality-q04/README.md),
so the only change is the library and its profile.

Everything previously measured about v4 was a per-test rate. This closes that gap.

| metric | v3 | v4 |
|---|---|---|
| familywise error rate | 0.00000 | **0.00000** |
| 95% upper bound | 0.00060 | **0.00060** |
| separator recovery | 1.00000 | **1.00000** |
| true-nonedge certification | 0.10142 | **0.09158** |
| abstention rate | 0.01094 | 0.00996 |
| mean Holm family size (of 15) | 14.707 | 14.727 |

Zero familywise errors in 5,000 replications, with 100% separator recovery confirming the
boundary pairs were genuinely tested at `theta = delta`. Control is indistinguishable from
v3.

Pruning falls 9.7% in relative terms, from 10.14% to 9.16%, and the share of replications
certifying no true nonedge rises to 49.9%. That is the 10.1% coarser resolution floor
appearing at network scale, close to what the floor arithmetic predicted.

## Reading

v4 is now validated on both axes: familywise control at the boundary, and the cubic
false-prune breach removed. The cost is about a tenth of pruning power. Given that v3
false-pruned true cubic edges at up to 9.7% against `alpha = 0.05` while v4 holds at or
below 0.2%, and that cubic associations are within the normal range of behavioural
research, the trade favours v4.

The scope boundary is unchanged and still applies: relationships past cubic remain biased
under both libraries, and false pruning there can exceed `alpha`.

## Operational note

Shard 8 failed on its first attempt after 99 minutes with no step conclusion recorded,
which indicates a lost runner rather than an error; successful shards ran 66 to 97 minutes,
so it was the slowest draw. Re-running that shard alone reproduced its results exactly,
since replications are seeded by index rather than execution order.

Shards near 100 minutes are long enough that one flake costs the whole run, because
`summarize` needs every shard. Halving `replications_per_shard` and doubling the matrix
would leave total compute and wall clock unchanged under the 20-job cap while making each
job about 50 minutes.
