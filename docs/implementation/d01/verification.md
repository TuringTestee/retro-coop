# D01 evidence verification

The inventory can be checked against the exact upstream source and fixture bytes without running a game. This verifies metadata and source enumeration, not emulator correctness, browser behavior or netplay.

Use Python 3 (standard library only), Git, and local source checkouts. Python is an optional research-verification tool here; this does not select or install the application build stack. Checkout directories under one parent must be named `d01-tetanes`, `d01-jsnes`, `d01-binjnes` and `d01-accuracycoin`. Obtain the repositories and full revisions listed in [inventory.json](inventory.json) with normal Git tooling. The verifier neither downloads nor redistributes fixtures and does not execute upstream code. Keep the AccuracyCoin license with the upstream checkout.

From the repository root, with the checkouts under `/tmp`:

```sh
python3 docs/implementation/d01/verify_inventory.py /tmp
timeout 60s sh scripts/preflight.sh
```

The source checker intentionally fails if a pin, inspected source hash, mapper registration or fixture byte changes. Refresh the recommendation and review before accepting a new pin. The small source parser is tied to these exact revisions, not a general Rust/C parser. The candidate binjnes mapper switch is checked only at its pinned source; re-inspect extraction boundaries on any upgrade.

Expected output at the D01 candidate:

```text
PASS: 4 exact source pins; 23 file hashes; 24 dispatch rows; 41/21/49 candidate mapper IDs; 40976-byte fixture header/hash; all qualification statuses untested.
Pre-flight passed (repository hygiene; no product tests yet).
```

The verifier checks full Git revisions, SHA-256 of recorded inspected files, selected mapper module paths and registration rows, candidate ID sets, all selected region/status fields, and the actual fixture header/size/SHA-256. It does not validate the truth of upstream hardware claims or permission beyond the recorded license evidence. The report supplies source-based interpretation and limitations; D02/D20 supply runtime proof. No product assets changed, so visual verification is inapplicable. No post-submit soak is assigned for D01; the runtime owners retain their later validation obligations.

Record actual command duration, exact PR head, independent review and CI run link in the PR's current evidence comment. Generic preflight stays below 60 seconds; the existing single presubmit job retains its 30-minute hard deadline and rejects retries that would extend the original deadline.
