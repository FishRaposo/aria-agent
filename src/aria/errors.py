"""ARIA error compatibility exports from the internal vendor namespace."""

# Keep the historical public import while using the packaged local module.
from aria.internal.vendor_core.errors import application_error_handler  # noqa: F401
