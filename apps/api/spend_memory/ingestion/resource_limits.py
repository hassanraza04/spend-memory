from __future__ import annotations

import resource
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    """Kernel limits for an untrusted local document worker."""

    cpu_seconds: int
    address_space_bytes: int
    max_open_files: int


def apply_resource_limits(limits: ResourceLimits) -> None:
    """Apply the effective limits supported by the active local runtime."""
    _set_soft_resource_limit(resource.RLIMIT_CPU, limits.cpu_seconds)
    _set_soft_resource_limit(resource.RLIMIT_NOFILE, limits.max_open_files)
    address_space_limit = getattr(resource, "RLIMIT_AS", None)
    if sys.platform.startswith("linux") and address_space_limit is not None:
        _set_soft_resource_limit(address_space_limit, limits.address_space_bytes)


def _set_soft_resource_limit(resource_type: int, requested_limit: int) -> None:
    try:
        current_soft_limit, hard_limit = resource.getrlimit(resource_type)
        effective_limit = requested_limit
        if hard_limit != resource.RLIM_INFINITY:
            effective_limit = min(effective_limit, hard_limit)
        if current_soft_limit != resource.RLIM_INFINITY:
            effective_limit = min(effective_limit, current_soft_limit)
        resource.setrlimit(resource_type, (effective_limit, hard_limit))
    except (OSError, ValueError):
        return
