#!/usr/bin/env python3
"""Compatibility entrypoint: retained upstream protocols stay in Russian.
English-only translation is no longer a correctness requirement.
"""
from check_integrity import check
import sys
errors = check()
for error in errors:
    print(error, file=sys.stderr)
print(f"Integrity: {len(errors)} errors. Original Russian protocols are intentional.")
sys.exit(bool(errors))
