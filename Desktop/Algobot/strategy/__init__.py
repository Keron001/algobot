# This file makes the strategy directory a Python package
# Import strategy classes here to make them available when importing from strategy
import importlib
import pkgutil
import inspect
from typing import Type, Dict
from .base import BaseStrategy

# Registry for all discovered strategies
_STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {}

def _discover_strategies():
    # Discover all modules in this package
    package = __name__
    for _, modname, ispkg in pkgutil.iter_modules(__path__):
        if ispkg or modname == 'base':
            continue
        module = importlib.import_module(f"{package}.{modname}")
        # Register all subclasses of BaseStrategy
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                _STRATEGY_REGISTRY[name] = obj

_discover_strategies()

def get_strategy_registry() -> Dict[str, Type[BaseStrategy]]:
    """Return the strategy registry mapping class names to classes."""
    return dict(_STRATEGY_REGISTRY)
