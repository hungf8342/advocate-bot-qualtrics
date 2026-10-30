# October 30 affirmative-defense scripts

`2026.10.30-affirmative-defenses.docx` was copied unchanged from Windows Downloads.
It governs Statute of Limitations and Ambiguity in the guided click-through
prototype. This update does not migrate the separate chatbot or defenses 3–21.

The prototype uses the revised SOL general explanation and debt-buyer wording,
the expanded Ambiguity explanation, and separate confirmation text for selected
and empty selections. The SOL dependency table agrees with the existing offer
rules: the main and grouped first/third choices are offered to debt buyers and
qualifying/explicitly uncertain original-creditor paths; the second also requires
an oral agreement. Ambiguity's main choice is always offered and is independent
of SOL. No checkbox is selected automatically.

After either Yes or No, continue to the next applicable question unless explicitly
directed elsewhere. Confirmation ends that defense's questions. A finish path
offers no further checkboxes; the prototype shows its result before moving on.
Unresolved checkbox decisions block advancement. The grouped SOL first/third
choice and previously approved dependency-based edit behavior are retained.

October 30 display copy is in `guided_defense_content.yaml`; existing canonical
routes and deterministic screening helpers supply the unchanged routing rules.
The clarification chat receives the same revised copy as the page.

`2026.10.30-preliminary-fields.docx` governs the prototype's separate preliminary
section. All 18 fields are collected once and reviewed before SOL begins. Known
fields are reused by defense routing; unresolved fields return to preliminary
intake for clarification. The original-creditor name is derived from the plaintiff
name when plaintiff type is original creditor. Existing dependency-aware edits
retain unrelated fields and still-valid defense choices.
