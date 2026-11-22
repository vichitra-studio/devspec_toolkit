"""The 1.1.x to 1.2.0 migration of a host's spec folder.

``runner.run_migration`` runs the scripts of ``scripts/`` (found by ``registry``) on a scratch copy and installs the result;
``context`` is what a script receives, ``report`` what a run reports, ``writer`` how a script writes a spec file.
"""
