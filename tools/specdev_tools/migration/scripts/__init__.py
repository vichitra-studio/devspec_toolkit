"""Migration scripts, one folder per toolkit version (``v1_2_0/``), one module per script named ``p<phase>_<name>``.

A module exports ``SCRIPT`` (a ``migration.registry.ScriptSpec``) and ``detect(ctx)``, ``apply(ctx)`` and
``verify(before, after)``; ``migration.registry.discover_scripts`` finds them.
"""
