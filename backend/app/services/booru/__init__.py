"""Booru provider registry.

Import this module to get the PROVIDERS dict mapping site names to
their provider instances.  Adding a new site is a two-step process:
1. Create a new module under app/services/booru/
2. Register it here.
"""
from app.services.booru.danbooru import Danbooru
from app.services.booru.e621 import E621
from app.services.booru.rule34 import Rule34

PROVIDERS = {
    "danbooru": Danbooru(),
    "e621": E621(),
    "rule34": Rule34(),
}

AVAILABLE_SITES = list(PROVIDERS.keys())
