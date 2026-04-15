"""Step validators for the DevSpec pipeline.

Each ``step_NN`` module exposes a ``validate_step_NN`` function that
performs deep (semantic) validation beyond what JSON Schema alone catches.
"""

# Re-export strategy: only step_16a / 16b / 16c are re-exported here
# because they are the only validators consumed by validate.py's
# DEEP_VALIDATORS dispatch table.  All other step validators are invoked
# directly via their own module paths and do not need package-level
# re-export.  If a new step validator is added to DEEP_VALIDATORS,
# add a corresponding import here.
from . import (  # noqa: F401 – re-exported for validate.py DEEP_VALIDATORS
    step_16a,
    step_16b,
    step_16c,
    step_16_anchor,
)
