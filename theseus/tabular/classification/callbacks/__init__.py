from theseus.base.callbacks import CALLBACKS_REGISTRY

from .checkpoint_callbacks import SKLearnCheckpointCallbacks
from .explainer import *

CALLBACKS_REGISTRY.register(SKLearnCheckpointCallbacks)
CALLBACKS_REGISTRY.register(ShapValueExplainer)
CALLBACKS_REGISTRY.register(PermutationImportance)
CALLBACKS_REGISTRY.register(PartialDependencePlots)
CALLBACKS_REGISTRY.register(LIMEExplainer)