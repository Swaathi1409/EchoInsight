"""
backend/action_layer/__init__.py
Action Intelligence Layer package.

This package is additive-only. It reads core tables through a read-only
repository layer and writes exclusively to act_* tables.
It is fully disabled when ACTION_LAYER_ENABLED=false.
"""
