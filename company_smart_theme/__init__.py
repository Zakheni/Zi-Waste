"""Company Smart Theme: per-company backend colors from logo or manual override."""

from . import models
from . import controllers

from .hooks import post_init_hook  # noqa: F401
