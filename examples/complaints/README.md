# Fictional complaint inputs

These fact-only JSON objects provide fictional defaults for clickthrough intake.
All names, case numbers, and facts are fictional. Neither file contains defense
judgments. They are examples, not a document-extraction feature.

```bash
.venv/bin/python scripts/run_clickthrough.py --complaint-fields examples/complaints/original-creditor.json
.venv/bin/python scripts/run_clickthrough.py --complaint-fields examples/complaints/debt-buyer.json
```

The original-creditor example has complete dates and attachments. The debt-buyer
example has an original-creditor name, both claim types, missing payment/opening
dates, and no attached statement or ownership documents. Defaults prefill relevant
intake controls; they become facts only after the user submits those screens.
Use `--blank` to start without example defaults, or `--debug` for section jumping
with collection disabled.

| Fields | JSON value |
| --- | --- |
| `CASE.NUMBER`, `PLAINTIFF`, `ORIGINAL.CREDITOR`, `LAW.FIRM` | Nonempty text |
| `PLAINTIFF.TYPE` | `"original"` or `"buyer"` |
| `SUIT.TYPE` | `"breach"`, `"common"`, or `"both"` |
| `AMOUNT` | Positive currency string, such as `"$4,250.00"` |
| `LAST.PAYMENT.DATE`, `BREACH.DATE`, `OPEN.DATE`, `COMPLAINT.DATE` | ISO date strings (`YYYY-MM-DD`) |
| `OWNERSHIP`, `STATEMENT`, `OWNERSHIP.PROOF`, `VERIFIED` | JSON `true` or `false` |

A `null` field represents missing complaint information; an omitted key represents
information not determined. A `false` value is a known negative. Unknown keys and
invalid values are rejected. `RECOGNIZE`, `CONSOLIDATION`, and `ORAL` must be
answered by the user and cannot be supplied in the example JSON.

Programmatic use from the project root:

```python
import json
from pathlib import Path
from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import (
    GuidedAnswer, ClickthroughReview,
)

values = json.loads(Path("examples/complaints/debt-buyer.json").read_text())
review = ClickthroughReview(values)
review.replay([GuidedAnswer(node_id="guided_welcome", value="continue")])
page = review.page()  # First preliminary field; defaults have not been submitted.
```

`COMPLAINT.DATE` binds to internal `FILING-DATE` and `session.filing_date`.
`PLAINTIFF` binds to `PLAINTIFF-NAME`, while `PLAINTIFF.TYPE` binds to `PLAINTIFF`.
`BREACH.DATE` binds to `BREACH-DATE` and is separate from payment date. These
internal bindings remain stable for shared rules and answer replay.

Use Back or Change in the interface to review submitted values. Changes reconcile
the subsequent path and retain applicable answers. For current intake and editing
behavior, see the [clickthrough guide](../../docs/clickthrough-guide.md).
