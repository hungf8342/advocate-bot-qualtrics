# CONFIDENCE SCORING CALIBRATION INDEX

90–100% (High Certainty): User is definitive. (e.g., "Yes, it was delivered on Tuesday," "I am positive.")

70–89% (Moderate Certainty): User is mostly sure but lacks hard proof. (e.g., "I'm pretty sure," "I believe so.")

50–69% (Tentative/Fuzzy): User uses hedging words. (e.g., "I think," "Maybe," "I'm not entirely sure, but let's say yes.")

0–49% (No meaningful lean): Pure uncertainty with no direction — the host handles via skip; do not use answer_node.

CRITICAL: If the user uses the words "think", "maybe", or "not sure", you are strictly forbidden from scoring higher than 70%.

For date-collection nodes:
- Exact dates may use the normal ranges above.
- Approximate but usable dates (e.g. "around September 2024", "about a year before filing") should still use `answer_node` with `next_node_id="submit"`, but score them lower than exact dates.
- True lack of any usable timing estimate (e.g. "I have no idea when") should use `next_node_id="no_date"` instead of `submit`.
