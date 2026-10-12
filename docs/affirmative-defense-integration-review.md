# October affirmative-defense integration review

Historical review: the documents were subsequently revised, and the first nine
defenses have now been implemented. This review's findings and implementation
status describe the earlier versions. See [the current flow](decision-tree.md)
for the implemented behavior. The user confirmed unconditional SOL preservation
for debt buyers and unresolved clinic referrals for identity theft and wrong party.

This review compares the local October 11 Word documents with the current chatbot.
It identifies content and implementation inconsistencies; it does not independently
validate the documents' legal propositions. Defense changes are proposed here,
with implementation deferred at the user's request.

Sources:

- [Basic decision tree](source-material/2026-10-11/2026.10.11%20basic-decision-tree.docx)
- [Affirmative-defense explanations](source-material/2026-10-11/2026.10.11%20explanations-aff-defenses.docx)
- [Preliminary explanations](source-material/2026-10-11/2026.10.11%20explanations-prelim-questions.docx)

## Decisions already made

- Use the October **one-year preservation screen** for statute of limitations.
  Label the result as preserving a defense, distinct from determining the legal
  filing deadline. The current state-law cutoff calculation has not been changed
  in this turn.
- Prepare this integration plan and inconsistency review before implementing the
  defense updates.
- Preliminary fields use one agreement question. Disagreement collects the
  litigant's preferred value and preserves the original parsed value.
- Display explanation paragraphs in document order, with applicable IF blocks
  appearing where they were written.

## Recommended implementation

1. Keep the October tree's defense order, question wording, and explicit branches
   in the consumer-debt YAML. Add section IDs and headings, and represent any
   grouped questions individually when their answers need different explanations
   or reuse. A section entry must remain visible even when preliminary facts allow
   all its questions to be answered automatically.
2. Store approved explanation content as ordered blocks. A block can contain
   unconditional text, a condition on named facts/results, or a question. Retain
   the document's general explanation, factual restatement, questions, and
   application order. If an application block asks a question, pause there and
   display its dependent text after the answer. Do not gather all unconditional
   text before conditional text. Conditions should be a small validated schema,
   not executable strings or instructions interpreted by the LLM.
3. Evaluate outcomes in `affirmative_defenses.py`. Have each assessment return
   the checklist status, a stable reason ID, and the facts supporting it. Select
   the approved application text from that same result, so the explanation cannot
   say a defense applies while the checklist leaves it unchecked. The LLM should
   classify answers and handle Q&A; it should not choose screening rules.
4. Distinguish parsed complaint facts, the litigant's effective answers, and facts
   about the complaint's contents. Use the effective payment date for preservation
   screening and retained complaint presence for missing-date questions. A
   preferred value must not silently rewrite a claim about what the complaint
   originally said. Reuse earlier identity-theft, fraud, claim-type, recognition,
   and consolidation answers through their declared branches.
5. Present a heading, the approved explanation and relevant known facts, then any
   unanswered question. After assessment, show the approved personalized outcome
   and an explicit continuation when a section needs no new answer. This avoids
   silently jumping over explanations or dumping several automatically assessed
   defenses into one turn.
6. Add rule-table and traversal tests for original creditors, debt buyers, mixed
   claim types, missing/unknown/disputed facts, referrals, document order, and the
   final summary. Confirm each application paragraph agrees with its recorded
   result. Keep the scraper input fact-only.

## Content decisions still needed

| Topic | Inconsistency or gap | Proposed resolution / decision needed |
| --- | --- | --- |
| SOL reference date and boundary | The tree says payment "within a year" or "more than a year ago" without identifying the reference date or equality boundary. The explanation compares filing date with payment date. | Recommend measuring backward from complaint filing, using a calendar year, with an explicit rule for exactly one year. Confirm this anchor and boundary. |
| SOL unknown payment information | The tree preserves when timing is not sure. For a debt buyer, it does not explicitly say what happens when the user is unsure whether any payment was made. Current code leaves unknown dates/payment history unresolved. | Preserve for unknown timing as the tree directs; confirm whether unknown payment occurrence also preserves, or requires clinic review. Unknown creditor type should remain unresolved. |
| SOL debt-buyer text | The explanation broadly encourages preservation for debt buyers even inside the legal period. The tree specifically says not to check when a payment to the buyer was within a year. | Give the explicit tree branch priority and revise the general application to include that exception. |
| SOL date meaning | Preliminary tree says last payment **to the original creditor**. Preliminary explanation says use a payment **to the buyer** if there was one. Defense logic asks buyer payments separately. | Keep two recipient-specific dates. Define the preliminary field as original-creditor payment and amend its explanatory sentence, or add explicit recipient metadata. Do not mix the dates. |
| Missing dates and SOL restatement | One explanation branch equates a missing complaint date plus disagreement with the user not recalling a date. The user might instead provide a known preferred date. Missing payment with agreement and unknown agreement are not covered. | Base statements separately on complaint presence, effective date, and agreement status. Never infer lack of recollection from absence in the complaint. Define all unknown/missing cases and how elapsed months are rounded. |
| Approximate payment dates | Preliminary explanation says an estimated year or a more/less-than-one-year answer is enough. Current input handling accepts exact dates and some approximations, but does not represent a year-only estimate or a relative-year category. | The new preservation screen should accept within-year / older-than-year / unsure directly, with optional dates for factual restatements. Store a year estimate as an interval or precision-bearing value; do not silently assign an exact day. |
| Standing, original creditor | Tree and explanations ask whether ownership is **stated**. Current code also checks whether an agreement was supplied and can preserve solely because that document is absent. | Remove the additional agreement requirement from this section to follow the October tree. Keep ownership-proof questions in the sections that explicitly use them. |
| Failure to state a cause: buyer attachments | Tree says a statement or purchase document can prevent checking, but also separately says missing ownership assertion or contract dates can support checking. Explanation uses `STATEMENT = false AND OWNERSHIP.PROOF = false`; current code treats either missing attachment as sufficient. | Confirm an explicit truth table. Recommend absence of **both** attachment alternatives as one trigger; keep missing ownership assertion and required breach dates as separate triggers. Specify whether a positive attachment ever overrides those other triggers. |
| Failure to state a cause: original creditor | Tree says "Legal owner of debt?" tagged `OWNERSHIP-PROOF`; explanations require `OWNERSHIP.PROOF`, while current code checks the `OWNERSHIP` assertion. | Confirm whether the trigger is a missing ownership statement, missing supporting proof, or either. The tag and question must describe the same fact. |
| Failure to state a cause: unconditional result | The explanation's `Return` and following "may not apply" text could display even after a preceding applicable condition. Its loop over `field != NA` could describe a false attachment answer as an included attachment. | Make outcomes mutually exclusive. For attachments, describe inclusion only when true; for dates, use complaint presence, with separate unknown text. |
| Statement qualification | `STATEMENT` varies between any account statement, final credit-card statement, statement identifying the original creditor, and final statement showing charge-off. The attachment alternatives overlap with `OWNERSHIP.PROOF`. | Decide which statement qualifies for each rule. Add separate fact flags if these distinctions affect outcomes; avoid treating every monthly bill as equivalent. |
| Last payment versus contract breach date | The tree uses the last-payment tag to answer whether the complaint includes a contract-breach date. These labels describe different events. | Confirm whether this is an intentional screening proxy. Otherwise add a separate complaint breach-date field rather than claiming one date establishes the other. |
| Wrong party wording | Under `RECOGNIZE = true`, explanation says "If you don’t recognize this account, this defense does not apply," contradicting its own condition and the tree. | Replace with wording consistent with recognition of an account the user opened. Also replace "you’re responsible" after a negative wrong-party answer with "you did not identify someone else as responsible"; that answer alone does not establish liability. |
| Identity theft / wrong party referrals | Tree and explanations request staff assistance. They do not specify whether the checkbox should be checked, unchecked, or left unresolved at referral, or whether the bot pauses. | Recommend retaining unresolved status, showing the staff referral immediately, and providing a deliberate continuation. Confirm whether staff must clear the referral before the rest of the flow proceeds. |
| Laches | The tree lists evidence-access problems without a clear outcome instruction. Explanation adds a link to delay and uses an ANY rule. The statement question mixes having one's own copies with relying only on supplied statements, which have opposite answer meanings. Current chatbot combines all three into one question. | Ask three separate questions, phrase the statement question in the negative direction, and clarify whether delay must be explicitly confirmed. Preserve when any approved trigger is true; unresolved when all remaining relevant answers are unknown. |
| Fraud and reused identity theft | Tree checks identity theft and hidden facts; explanation asks hidden facts only if identity theft is false. Neither specifies unknown identity theft. Current chatbot asks identity theft again. | Reuse the earlier suspicion answer. If true, show the identity-theft application; if false, ask hidden facts. Recommend asking hidden facts for unknown identity theft too, while retaining the unresolved fact. Confirm short-circuit behavior after a positive answer. |
| Lack of consideration | Tree requires **no to both** using the card and opening it explicitly for someone else, unless identity theft already triggers it. Current code asks only whether the user used the card. | Add the missing question and use `identity_theft OR (not used AND not opened for another)`, with explicit unknown handling. |
| Excuse/breach of contract | Tree first excludes complaints without a breach-of-contract claim. Current chatbot asks the reasons for every complaint. | Add the claim-type gate, reuse `SUIT.TYPE`, and treat `both` as including breach. Confirm how unknown claim type should be handled. |
| Reuse across defenses | Tree refers back to identity theft and fraud for common counts and lack of consideration; current chatbot repeats these or embeds them in a combined question. | Store named answers and assess them once. Reuse them without converting a staff-referral result into a negative identity-theft answer. |
| Unknowns | Outside SOL and mitigation, many branches mention only yes/no. The explanation templates have no general unknown outcome. | Retain `checked`, `unchecked`, and `unresolved`. Add approved unknown copy; avoid interpreting unknown as false. Preserve the mitigation exception: unknown contact checks its nested box; unknown rejected settlement does not. |
| Field names and missing-value notation | Documents mix dotted and hyphenated tags, `IDENTITY.THEFT` / `ID.THEFT`, `NA` / `N/A`, and boolean agreement tags absent from the scraper input. | Use one canonical internal registry with aliases. Derive agreement facts from the user's verification answer. Keep false, missing, unknown, disputed, and unasked distinct. For original creditors, use plaintiff name as the original-creditor name when the conditional original-creditor question was skipped. |
| Missing approved explanations | The explanations document ends after fraud: it covers 9 of the tree's 21 defenses. | Integrate approved text for those nine. For the other twelve, use the approved tree question and result label, or obtain additional explanation copy; do not invent substantive legal explanations. |
| Editorial notes and wording | Tree contains internal comments about documents/litigation, broad claims about what original creditors sue for, and "Recission." Explanations include slashes and a typo in standing wording. | Keep internal notes out of the dialogue. Resolve generalizations, normalize "Rescission," and approve final user-facing wording. |

## Defense-by-defense implementation map

The section order already matches the October tree. The detailed question gates,
reuse, and rules need the following changes.

| Defense | Explanation supplied? | Integration work |
| --- | --- | --- |
| Statute of limitations | Yes | Replace cutoff path with selected preservation screen after anchor/edge cases are resolved; display factual timing without calling it a legal deadline. |
| Ambiguity | Yes | Add explanation before existing question; use approved conditional outcome wording. |
| Standing/privity | Yes | Reuse creditor type and ownership statement; remove extra original-creditor document criterion. |
| Failure to State a Cause of Action | Yes | Resolve assertion/proof and attachment truth table; show only the corresponding application. |
| Mistake | Yes | Add explanation before existing question. |
| Identity theft | Yes | Reuse recognition; ask suspicion only where needed; show immediate referral and approved factual restatement. |
| Wrong party | Yes | Correct reversed sentence; reuse recognition; show referral when appropriate. |
| Laches | Yes | Split three questions, normalize answer direction, and agree on delay/outcome rule. |
| Fraud, misrepresentation, concealment | Yes | Reuse identity-theft suspicion; personalize creditor names; resolve unknown/short-circuit path. |
| Failure to mitigate | No | Preserve separate nested checkbox rules and consolidation wording. |
| Common counts only | No | Reuse claim type, identity theft, and fraud; consider splitting other reasons into named answers. |
| Unconscionable contract | No | Existing main question follows tree; approved explanation still needed. |
| Rescission | No | Keep consolidation-aware question; correct displayed spelling. |
| Lack of consideration | No | Add opened-for-another-person question and two-negative gate; reuse identity theft. |
| Accord and satisfaction | No | Keep consolidation-aware settlement question. |
| Excuse/breach of contract | No | Add breach-claim gate; reuse earlier overlapping payment/insurance facts if split into named answers. |
| Capacity | No | Preserve separate age, incapacity, and disclosure-consent questions; consider skipping remaining questions when age alone triggers preservation. |
| Waiver | No | Restore "to the original creditor" in question wording. |
| Oral modification | No | Existing question follows tree. |
| Tender of payment | No | Existing question follows tree. |
| Civil Code section 1632 / language | No | Existing three-question conjunction follows tree; reuse triage language if that intake is later added. |

## Suggested rollout

First resolve the SOL boundaries and the failure-to-state-a-cause truth table.
Then implement the October question gates and shared answer registry, add ordered
approved content for the nine documented defenses, and align result explanations
with the rule outputs. Keep the remaining twelve defenses' explanation-copy gaps
visible in the content backlog. Finish with full traversal and summary checks.
