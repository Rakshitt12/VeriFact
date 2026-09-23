"""API package initialization.

Kept intentionally side-effect free: importing ``backend.api.schemas``
must NOT eagerly import ``backend.api.routes`` (which pulls in scoring,
verification, and report services). Routers are imported explicitly via
``backend.api.routes`` / ``backend.main``.
"""

__all__ = []
