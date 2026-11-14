"""Load the shared base tree used by guided content overrides and bindings.

Historical node identifiers remain stable for replay and source provenance.
User-facing pages use the validated tree in workflow.py.
"""

from pathlib import Path

from advocate_bot_qualtrics.core.tree_definition import TreeDefinition, load_tree_definition

BASE_TREE_PATH = Path(__file__).with_name("base_tree.yaml")
BASE_TREE_DEFINITION: TreeDefinition = load_tree_definition(BASE_TREE_PATH)
