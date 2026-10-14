"""Task entity_match_amazon_google (layer G, public test set): "do the two product records describe the same product?"

Same converter as build_entity_match_abt_buy.py, applied to the DeepMatcher version of Amazon-Google (structured,
test split); see that file for the source, the sampling and the item format.
    python3 reference/build/build_entity_match_amazon_google.py CACHE_DIR"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_entity_match_abt_buy import build  # noqa: E402

if __name__ == "__main__":
    build("amazon_google", sys.argv[1])
