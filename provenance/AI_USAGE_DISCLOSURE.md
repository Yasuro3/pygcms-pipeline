# AI-use record

## Manuscript, code-review and figure preparation

OpenAI ChatGPT (GPT-5.6 Pro; accessed 14 July 2026) and Anthropic Claude (Opus 4.8; accessed 15 July 2026) assisted with English-language editing, document organization, code review, test scaffolding and drafting the deterministic figure-generation scripts in this archive. All scripts were executed and inspected by the authors. The authors verified calculations, references and visual outputs and remain responsible for the work. The models did not generate experimental measurements, NIST search results, mass spectra or ground-truth compound identities.

For v1.3.0, Anthropic Claude (Opus 4.8) additionally assisted with drafting the offline mock bridge (`scripts/mock_nist_bridge.py`), the adversarial fixture, and the candidate-preservation tests. The authors executed every test, inspected the assertions and the resulting failures and passes, and confirmed that the fixture is capable of failing a lossy implementation. The synthetic candidate values in the mock are fabricated constants chosen to probe software behaviour; they are labelled as such in the code, in every response, and in `docs/MOCK_BRIDGE.md`, and they are not analytical results.

## Optional AI function in the application

The optional external-model review is advisory. Every call must create a record conforming to `ai_runtime_record_template.yaml`. The original NIST candidates remain unchanged. The final human decision and override reason are recorded. API credentials must never be deposited.
