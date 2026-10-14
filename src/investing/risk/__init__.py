"""Riesgo de cuenta. El kill switch llega en otra PR; aquí solo está la interfaz."""

from investing.risk.control import ControlRiesgo, ControlRiesgoNoImplementado

__all__ = ["ControlRiesgo", "ControlRiesgoNoImplementado"]
