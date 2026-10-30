# October 25 affirmative-defense scripts

`2026.10.25 Affirmative-Defense-Scripts.docx` governs the wording and conditional
flow for all 21 defenses, replacing the October 20 defense source. The October 11
preliminary source remains in effect, with a separate complaint breach-date
verification added to support the new scripts.

Implementation decisions confirmed by the user:

- “Finish this defense” advances without offering its checkbox.
- The user corrected an omission in the debt-buyer SOL arm: always ask about
  the main SOL defense before the first/third indented boxes. Yes and No remain
  explicit litigant choices; debt-buyer status never selects the main box.
- Indented checkboxes mentioned together in the source receive one combined
  choice. For SOL, one Yes/No answer applies to both the first and third boxes;
  the oral-contract second box remains a separate choice. Main and parent boxes
  retain their explicit questions. The same main checkbox is
  not asked twice when both claim groups are present.
- Unresolved factual issues and undecided choices block advancement. Returning
  to a question does not resolve it. Clinic referrals require explicit
  confirmation that staff have addressed the issue before continuing; that
  confirmation does not select a checkbox.
- `BREACH.DATE` is verified separately from `LAST.PAYMENT.DATE`. Corrections to
  breach date describe the complaint's contents and preserve the originally
  parsed value for provenance.

Per-defense confirmation displays the selected and declined boxes and waits for
readiness to advance. Identity theft and wrong party follow the referral paths
without inventing a checkbox offer. If all Common Counts facts are negative, no
checkbox is offered and the empty selection summary is confirmed. Approved
clarification text is kept separate from unknown factual answers.
