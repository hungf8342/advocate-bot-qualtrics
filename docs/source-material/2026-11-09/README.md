# November 9 affirmative-defense scripts

`2026.11.09 Affirmative-Defense-Scripts.docx` is retained as the November 9
source for the guided prototype. The current prototype uses the November 10
revision in `../2026.11.10/`. The copy is unchanged from Windows Downloads.

The prototype includes defenses 1, 2, 5, 8, and 9–21. Defenses 3, 4, 6, and 7 remain
excluded. The Common Counts fourth nested option, which depends on the excluded
Identity Theft defense, is not offered.

`guided_screen_layout.yaml` maps the document's footnote IDs to prototype screens.
Headers are extracted from `NEW SCREEN:` footnotes rather than rewritten in code.
Conditional variants use confirmed facts. Informational outcomes and derived
parent-checkbox explanations have their own Next screens before confirmation.
Mistake has no new screen footnote and retains its existing combined explanation
and checkbox question under the defense name.

Regenerate the checked-in source metadata with:

```bash
.venv/bin/python scripts/extract_guided_script_formatting.py
.venv/bin/python scripts/extract_guided_script_formatting.py --check
```

These assets describe the guided prototype. The canonical interactive-chat tree
and the October 30 preliminary-intake source remain separate.
