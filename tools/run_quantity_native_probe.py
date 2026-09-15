"""Native acceptance on fresh isolated copies only; no installation writes."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from tools import run_type_word_native_probe as runner
from word_factori.campaign import campaign_for_level_set
from word_factori.data import locations_for_manifest
from word_factori.quantity_graphs import graph_budget, graph_payload
from word_factori.quantity_logic import graphs_for_location, graphs_for_word


def cases_for_campaign():
    cases=[]; missing=[]
    for location in locations_for_manifest(campaign_for_level_set('discovery_labs')):
        graphs=graphs_for_location(location)
        if not graphs:
            missing.append(location.stable_key)
            continue
        graph=graphs[0]
        cases.append(dict(graph_payload(graph),word=location.target,name=location.stable_key,budget=graph_budget(graph)))
    for word in ('CC','CV','CVC','ABCDEFGHIJKL'):
        graph=graphs_for_word(word)[0]
        cases.append(dict(graph_payload(graph),word=word,name='free-'+word,budget=graph_budget(graph)))
    return cases,missing


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('cli','original','runtime','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    runner.validate_probe_paths(args.cli,args.original,args.runtime,args.output)
    runner.verify_original(args.original.read_bytes())
    cases,missing=cases_for_campaign()
    staging=args.output.with_name(args.output.name+'-harness')
    staging.mkdir(exist_ok=False)
    (staging/'tools').mkdir()
    harness=(ROOT/'tools/quantity_word_acceptance.gml').read_text(encoding='utf-8')
    harness=harness.replace('QUANTITY_CASES',json.dumps(json.dumps(cases,separators=(',',':'))))
    (staging/'tools/type_word_completion_acceptance.gml').write_text(harness,encoding='utf-8')
    # Existing runner reads its authored harness through ROOT; all safety boundaries
    # were checked against the real checkout first, and output is fresh and explicit.
    runner.ROOT=staging
    result=runner.build_probe(args.cli,args.original,args.runtime,args.output)
    print(json.dumps({'native':result,'missing_campaign_witnesses':missing},indent=2))
    if missing:
        raise SystemExit(2)


if __name__=='__main__':
    main()
