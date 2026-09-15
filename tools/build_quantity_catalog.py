"""Import derived, native-verified research witnesses, never game source/binaries."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from word_factori.quantity_graphs import (catalog_from_payload, graph_from_payload,
    graph_budget, graph_payload, payload_digest, validate_graph)


def build_catalog(research: dict, native: dict, *, research_sha256: str, native_sha256: str) -> dict:
    if research['native_table_sha256'] != native_sha256 or native.get('failure'):
        raise ValueError('native transition evidence does not match research')
    transitions = frozenset((e['machine'], tuple(sorted(e['inputs'])), e['output'])
                            for e in native['snapshots']['edges'])
    evidence = {entry['witness_id']: entry for entry in research['native_evidence']}
    recipes, alphabet, proofs = {}, {}, []
    for ti, record in enumerate(research['records']):
        if not record.get('ap_code') and not record['id'].startswith('letter-'):
            continue
        graphs = []
        for ri, route in enumerate(record['routes']):
            proof = evidence[f'r{ti:03d}-v{ri:02d}']
            case = dict(route, output=record['output'])
            if proof['graph_sha256'] != payload_digest(case) or proof['outputs'] != 10:
                raise ValueError('route lacks matching native production evidence')
            graph = graph_from_payload({'nodes': route['nodes'], 'roots': [route['root']]})
            validate_graph(graph, transitions)
            if tuple(route['counts']) != graph_budget(graph) or route['sources'] != sum(n.machine == 'oIFactory' for n in graph.nodes):
                raise ValueError('research budget differs from actual graph')
            graphs.append(graph_payload(graph))
            proofs.append({'graph': payload_digest(graphs[-1]), 'native_result': proof['result_sha256']})
        if record.get('ap_code'):
            recipes[str(record['ap_code'])] = graphs
        else:
            alphabet[record['output']] = graphs
    payload = {'schema': 1, 'provenance': {'research_sha256': research_sha256,
        'native_table_sha256': native_sha256, 'recipe_source_sha256': research['source_recipe_sha256'],
        'witnesses': proofs, 'model': 'fixed-output acyclic, conservative alternatives'},
        'transitions': sorted(transitions), 'recipes': recipes, 'alphabet': alphabet}
    payload['digest'] = payload_digest(payload)
    # Validate the serialized form, including strict complete AP identities.
    payload = json.loads(json.dumps(payload))
    catalog_from_payload(payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('research', type=Path)
    parser.add_argument('native_table', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'word_factori/data/quantity_recipes.json')
    args = parser.parse_args()
    research, native = args.research.read_bytes(), args.native_table.read_bytes()
    payload = build_catalog(json.loads(research), json.loads(native),
        research_sha256=hashlib.sha256(research).hexdigest(), native_sha256=hashlib.sha256(native).hexdigest())
    args.output.write_text(json.dumps(payload, separators=(',', ':'), sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps({'recipes': len(payload['recipes']), 'alphabet': len(payload['alphabet']),
                      'digest': payload['digest'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
