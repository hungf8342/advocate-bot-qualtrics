# Imaginary complaint inputs

These two JSON objects simulate facts returned by an external complaint scraper.
All names, case numbers, and facts are fictional. Neither file contains defense
judgments. This is a temporary format for exercising the prototype.

```bash
.venv/bin/python scripts/interactive_chat_demo.py --complaint-fields examples/complaints/original-creditor.json
.venv/bin/python scripts/interactive_chat_demo.py --complaint-fields examples/complaints/debt-buyer.json
```

The original-creditor example has complete dates and attachments. The debt-buyer
example has an original-creditor name, both claim types, missing payment/opening
dates, and no attached statement or ownership documents. To try corrections,
answer "No" to an agreement question and provide your preferred value.

| Fields | JSON value |
| --- | --- |
| `CASE.NUMBER`, `PLAINTIFF`, `ORIGINAL.CREDITOR`, `LAW.FIRM` | Nonempty text |
| `PLAINTIFF.TYPE` | `"original"` or `"buyer"` |
| `SUIT.TYPE` | `"breach"`, `"common"`, or `"both"` |
| `AMOUNT` | Positive currency string, such as `"$4,250.00"` |
| `LAST.PAYMENT.DATE`, `OPEN.DATE`, `COMPLAINT.DATE` | ISO date strings (`YYYY-MM-DD`) |
| `OWNERSHIP`, `STATEMENT`, `OWNERSHIP.PROOF`, `VERIFIED` | JSON `true` or `false` |

Any field may be `null`, meaning the scraper found that it was absent from the
complaint. An omitted key means extraction did not determine the answer. A `false`
answer is a known negative, distinct from either missing or unknown information.
`ORIGINAL.CREDITOR` is verified when the plaintiff is a debt buyer or its type is
unknown; the original-creditor path skips that question.

`RECOGNIZE`, `CONSOLIDATION`, and `ORAL` are answered by the litigant and are rejected
in scraper input. Unknown keys and invalid values are rejected. The application
does not accept documents through this entry point.

Programmatic use:

```python
import json
from pathlib import Path
from advocate_bot_qualtrics.core.engine import InteractiveChatEngine

values = json.loads(Path("examples/complaints/debt-buyer.json").read_text())
engine = InteractiveChatEngine.from_user_input(complaint_fields=values)
engine.initial_messages()
```

All parsed fields immediately appear in the sidebar as awaiting verification.
They become effective answers only after agreement or correction. "I don't know"
leaves a field unknown for screening. A correction preserves the original parsed
value; date-presence checks still distinguish what was present in the complaint
from the litigant's preferred date. Reset restores the original input for fresh
verification.

`COMPLAINT.DATE` maps to the established internal `FILING-DATE` field and
`session.filing_date`. `PLAINTIFF` maps to internal `PLAINTIFF-NAME`, while
`PLAINTIFF.TYPE` maps to internal `PLAINTIFF`. These aliases keep downstream
screening compatible with the existing session fields. The selected clinic SOL
workflow preserves the defense for every debt buyer without asking for another
payment date. For original creditors, the litigant confirms the complaint's timing
estimate or answers a separate one-year question; this leaves the scraped date intact.
