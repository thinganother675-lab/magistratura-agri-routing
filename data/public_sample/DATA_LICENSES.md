# Public smoke data and measurement facts

The original formal smoke scenarios in `benchmark.jsonl` and the original
measurements-only numerical projections in `home150_measurements.jsonl`,
`home150_expected_aggregates.json` and `home150_provenance.json` are dedicated
to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
by Antoniy Sarychev and Denis Shesternin, 2026.

The projection omits source/input/context/gold and provider response text. Its
correctness flags preserve the historical scorer v1 judgment; they are not a
human gold review or an independently rescored experiment. It reproduces 750
retained numerical policy decisions (five policies on 150 cases) and 13 selected
aggregate metrics per policy. Known-cost sums are lower bounds where charges
are unknown, not provider invoices.

This dedication does not cover original AgXQA, Extension, FAO, ERA5/NASA data,
provider responses, model weights or manuscripts. The public smoke cases use
invented formal inputs and do not represent agronomic field recommendations.
