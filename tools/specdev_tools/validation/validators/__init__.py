"""Step validators for the DevSpec pipeline.

Each ``step_NN`` module exposes a ``validate_step_NN`` function that
performs deep (semantic) validation beyond what JSON Schema alone catches.
"""

# Re-export strategy: the three Step-16 validator modules (step_16a, step_16c,
# step_16_anchor) are re-exported here because they are consumed by
# validate.py's DEEP_VALIDATORS dispatch table.  Step 16b has no validator
# module: DEEP_VALIDATORS maps it to validate_step_16a.  The validators of
# steps 02 to 15 are imported by validate.py as submodules of this package and
# need no import here.
from . import (  # noqa: F401 – re-exported for validate.py DEEP_VALIDATORS
    step_16a,
    step_16c,
    step_16_anchor,
)
