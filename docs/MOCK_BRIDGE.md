# Mock NIST bridge: scope, use, and limits

## Why this exists

PyGCMS Pipeline delegates library searching to a separately licensed local NIST
MS Search installation. That dependency is deliberate: NIST software, libraries,
and spectra are not redistributable, and the public release contains none of
them.

The consequence is that a reader or reviewer without a NIST licence cannot
exercise the candidate-preserving stage, which is the software's central claim.
`scripts/mock_nist_bridge.py` removes that obstacle. It is a **test double**: it
re-implements the bridge's interface contract and returns synthetic candidates
from a fictitious library, so the whole workflow can be run offline.

## What the mock does and does not establish

| Claim | Established by the mock? |
|---|---|
| Every returned candidate survives selection and export with its original rank | **Yes** |
| Original match factor, reverse match factor, probability, CAS, and library are preserved unmodified | **Yes** |
| Selecting one candidate never deletes the alternatives | **Yes** |
| A zero-hit component is retained as unidentified rather than deleted | **Yes** |
| The application parses the bridge response format correctly | **Yes** |
| NIST match factors are accurate | **No. Out of scope.** |
| Any compound is correctly identified | **No. Out of scope.** |
| Mock output resembles real NIST output numerically | **No. Not claimed.** |

The mock verifies **software behaviour**, not chemistry. Candidate preservation
is a data-handling property: the question "does the exported record still
contain rank 2, with its original score, after rank 1 was selected?" has a
determinate answer that does not depend on whether rank 1 is chemically right.
That is exactly the property a test double can settle, and exactly the property
the manuscript claims.

Every hit returned by the mock carries `lib = "MOCKLIB-SYNTHETIC-1.0"` and every
response carries a `banner` field reading
`SYNTHETIC MOCK OUTPUT - NOT NIST MS SEARCH - NOT AN IDENTIFICATION`.
Exports produced against the mock are therefore self-labelling and cannot be
mistaken for analytical results.

## Why the fixture is adversarial

A mock that returns whatever the software expects would demonstrate nothing. The
fixture in `--mode adversarial` is built so that a naive or lossy implementation
**fails**:

| Query | Probe | A naive implementation fails by |
|---|---|---|
| 1 | Near-tie, MF 912 vs 909 | Collapsing near-ties, or keeping only the top hit |
| 2 | Rank 1 and rank 2 in different NOM classes | Letting class assignment overwrite the alternative |
| 3 | All candidates weak (MF ~420) | Forcing an assignment instead of leaving it unassigned |
| 4 | Zero hits returned | Dropping the component from the table entirely |
| 5 | Missing CAS and formula | Corrupting the record or discarding the hit |
| 6 | Same name at ranks 1 and 2 | Deduplicating by name and losing a rank |
| 7 | 20 candidates, top-N = 15 | Truncating from the wrong end, or reordering |

`tests/test_candidate_preservation.py` drives the released `software/index.html`
against this fixture and asserts invariants I1-I6. It fails loudly if any
candidate, rank, or score is altered.

## What this does not replace

The mock does not substitute for validation against real NIST MS Search. Users
with a licence should run the real bridge; the archived run manifest records the
NIST build, library release, and search options for exactly that reason. The
mock's role is to make the *software's* contribution independently checkable by
someone who has no licence at all.

## Usage

```bash
# 1. Start the mock in a separate terminal
python scripts/mock_nist_bridge.py                     # demo mode
python scripts/mock_nist_bridge.py --mode adversarial  # edge-case fixture

# 2. Open software/index.html in a Chromium-based desktop browser.
#    Leave the bridge URL at http://127.0.0.1:18789 and press "Check bridge".
#    Load data/example/synthetic_gc_ms.mzML, run the analysis,
#    then press "Run NIST search".

# 3. Or run the automated invariant checks:
python tests/test_mock_bridge_contract.py     # no browser required
python tests/test_candidate_preservation.py   # requires playwright + chromium
python scripts/run_checks.py                  # everything
```

`test_candidate_preservation.py` skips with a clear message if Playwright or
Chromium is unavailable, so `run_checks.py` remains runnable on a bare Python
installation.
