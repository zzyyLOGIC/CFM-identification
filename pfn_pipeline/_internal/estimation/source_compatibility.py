"""Explicit source-relocation compatibility for the two verified training releases.

Original hashes preserve checkpoint identity; migrated AST hashes guard the
adapter and DGP implementation. Never accept a checkpoint solely by its version.
Update this bridge only after source comparison and numerical parity checks.
Native local checkpoints continue to require the current exact cache identity.
"""
import ast
import hashlib
import json
from pathlib import Path

from .priors import checkpoint_dgp

ORIGINAL_SOURCE_HASHES = {'linear_b_random_a': {'linear_b_dgp.py': '978fb0d2e35ca506b3c45cc379221095bf8ac943ef5754e77456ea59099a389e',
                       'causalfm_dgp_v1/dgp.py': 'ca4e28a62dc806b39b7e72dee6d5c05129330393fba83a14adfb249f082b88b1',
                       'estimands.py': 'cad6d1daa8f65f6d64f13edcc59fdb2ffea8cd861465df97dd8d2c6b7963f0c7',
                       'random_lpe_prior.py': 'cf958eec5c344066911be35298c0c832f8dc0fe8ced001d77a3133de75b42e7b',
                       'cepo.py': 'df557956d91807a16d9448448307088bcfe00b673d8d44a56dce0da7a6437349',
                       'causalfm_experiment/data.py': '55fa539cb3aec738ccce9587553a78773d43e7eb18eb0df9822f443faaf5503f'},
 'random_functions': {'causalfm_dgp_v1/dgp.py': '3ccd8aeb8908030850f07f1f3372f9ac202f04b759344f4474274e43b8031459',
                      'causalfm_dgp_v1/outcomes.py': 'fdf01c81b13bab7114afc96fab3a2b76804f259fd1d769e23330967477050299',
                      'causalfm_dgp_v1/_upstream_outcome.py': 'b141ae40ec6686c93c0853f575d567e9db5e3be11f52edc4ef72f211fcf57a3b',
                      'causalfm_dgp_v1/_upstream_base.py': '54090f2480cb7fa24437015db07b3f89369089395225140a9aef064a3de421a7',
                      'causalfm_dgp_v1/_upstream_frontdoor.py': '2b1a5253ea3f1ed4cc949b7cf70ef3b27cc6699bd13b24e92e81342be8d7e8a3',
                      'estimands.py': 'cad6d1daa8f65f6d64f13edcc59fdb2ffea8cd861465df97dd8d2c6b7963f0c7',
                      'random_lpe_prior.py': '2466db78607e01986f392ddfc25021573e617d13814e6cbeac0218394231b268',
                      'cepo.py': '25142cf2257a68327bef234e2c509b3a5dd54d724b7cca20f970a6ba831382b8',
                      'causalfm_experiment/data.py': '66e4cf3ea8fb077d7b81f54517cd10ee73d5a65e989f7ac9cb16cc64f8297b0d'}}

MIGRATED_AST_HASHES = {'causalfm_dgp_v1/_upstream_base.py': 'bdaffdf4e22b21a11af86dc00430245bfcec44e0cac50db3078fb64a0016eb9d',
 'causalfm_dgp_v1/_upstream_frontdoor.py': '6c17def6d3ee2b0a53a1cce5fb2e2f7ae7f40403d836dc5a3cc75cb3bd9f9429',
 'causalfm_dgp_v1/_upstream_outcome.py': '31ef2606af92a9d9e77bb3607c4e12e74deadc7d88a8532b4c5520135c23ecc1',
 'causalfm_dgp_v1/dgp.py': '6dd75ac95cceeee5d045bcb5c86de5b49c50a26a488f547ceb88ee4629cd0cfe',
 'causalfm_dgp_v1/outcomes.py': '810d08135ab98a2628ae6e05cf163d8b3376c890eb88adbc958f51f750bc0a53',
 'causalfm_experiment/data.py': 'eeaa0c8d8daf1db269469e21634cf1a55a1dcd6ba3a4e69884fc9dc8df76f7be',
 'cepo.py': '5bb87f94ae8af1725839862e19831a32223f54f8fcfaac02824082018738b7e4',
 'estimands.py': '3e40dde9bdfabb16aa81f723a7853f99dfd4aee314301438b6c72969b5fde48a',
 'linear_b_dgp.py': 'd67b3f059fab674f641ac062b022628c60a832263b51ce93cf4b4ac2ca33559a',
 'priors.py': '85235b973c9ade9a248bce5829d764502c7fa78abf55c35766f5f5f6d00afd9b',
 'random_lpe_prior.py': '9984f8bff5496a135b98259448b0991b3a15982b63d624f05a97c06bd3377de0'}


def _source_ast_sha256(source):
    tree = ast.parse(source)
    # The recorded hashes use the Python 3.11 AST schema. Python 3.12 adds
    # empty type_params to ordinary functions/classes without changing meaning.
    # Retain nonempty type parameters so actual generic declarations still
    # change the fingerprint; all other AST fields remain part of the hash.
    for node in ast.walk(tree):
        if getattr(node, "type_params", None) == []:
            node._fields = tuple(field for field in node._fields if field != "type_params")
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def validate_checkpoint_data(state, bank):
    """Return the identity check used, or reject unknown data/source changes."""
    if checkpoint_dgp(state) != bank.dgp:
        raise ValueError("Checkpoint and evaluation/training DGP differ")
    if state.get("data_identity") == bank.fingerprint:
        if state.get("data_prior", bank.identity) != bank.identity:
            raise ValueError("Checkpoint data_prior differs from its data identity")
        return "exact_local_sources"
    original_sources = ORIGINAL_SOURCE_HASHES[bank.dgp]
    identity = {**bank.identity, "sources": original_sources}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if state.get("data_identity") != fingerprint:
        raise ValueError("DGP/graph identity differs from checkpoint")
    root = Path(__file__).resolve().parent
    for name in (*original_sources, "priors.py"):
        digest = _source_ast_sha256((root / name).read_text(encoding="utf-8-sig"))
        if digest != MIGRATED_AST_HASHES[name]:
            raise ValueError(f"Source compatibility must be revalidated after changing {name}")
    return "verified_source_migration"
