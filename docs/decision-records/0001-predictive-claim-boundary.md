# ADR 0001: Predictive practical separation is not causal identification

## Status

Accepted for the initial Python reference engine.

## Decision

`renca` may certify that two variables are practically predictively separated
relative to a predeclared separator family and practical thresholds. This is a
predictive result, not a causal nonedge or a direct-effect claim.

Causal-skeleton interpretation, direction claims, and graph-solver
constraints remain unavailable until a future assumption package explicitly
declares and validates the required causal, measurement, selection, and
separator-completeness conditions.

## Consequences

All initial public artifacts and reports must label practical-separation
results as predictive. Future causal-promotion modules must record their
assumptions and provenance rather than silently upgrading this result.
