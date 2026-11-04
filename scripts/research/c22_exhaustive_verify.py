"""Independent full-domain C22 audit with resumable accounting checkpoints."""

import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path

from scripts.research.c22_learning_verify import (
    DATA, DOMAINS, GUARDS, LANES, RISK_FIELDS, ROOT, VIEWS,
    IndependentTapeAudit, complete_rows, equal, identity, objective, qualified_rows,
    qualify, read, reduced_risk, repair_eligible, sha, choose,
)


PARENT = ROOT / 'runs/c22-learning-loop-2026-10-25'
HELPER = ROOT / 'scripts/research/c22_learning_verify.py'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + '.pending')
    pending.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    pending.replace(path)


def full_catalog(initial_rules):
    axes = tuple(DOMAINS)
    result = []
    for values in itertools.product(*(DOMAINS[field] for field in axes)):
        rules = dict(initial_rules, **dict(zip(axes, values)))
        result.append(dict(name=identity(rules), rules=rules))
    assert len(result) == len({case['name'] for case in result}) == 5184
    return result


class Payloads:
    """Validate parent ancestry independently from the runner's store helpers."""

    def __init__(self, out, protocol):
        self.out = out
        self.bindings = protocol['parent_cell_bindings']
        parent_complete = read(PARENT / 'COMPLETE.json')
        proof_paths = sorted((PARENT / 'cells-integrity').glob('*.json'))
        assert set(self.bindings) == {path.stem for path in proof_paths}
        assert len(proof_paths) == 570
        for path in proof_paths:
            key = path.stem
            binding = self.bindings[key]
            proof = read(path)
            assert sha(path) == binding['proof_sha256']
            assert parent_complete['artifacts'][str(path.relative_to(PARENT))] == binding['proof_sha256']
            assert binding['path'] == proof['path'] and binding['sha256'] == proof['sha256']

    def proof(self, key, folder='cells'):
        assert folder in ('cells', 'repeats')
        parts = key.split('-')
        assert len(parts) == 3 and len(parts[0]) == 16
        assert all(character in '0123456789abcdef' for character in parts[0])
        assert parts[1] in VIEWS and parts[2] in GUARDS
        proof_path = self.out / (folder + '-integrity') / (key + '.json')
        proof = read(proof_path)
        assert set(proof) == {'path', 'sha256', 'origin'}
        relative = Path(proof['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        path = (ROOT / relative).resolve()
        assert path.is_relative_to((ROOT / 'runs').resolve())
        if proof['origin'] == 'new':
            assert path == self.out / folder / (key + '.json.gz')
        else:
            assert proof['origin'] == 'reused' and folder == 'cells'
            assert key in self.bindings
            assert proof['path'] == self.bindings[key]['path']
            assert proof['sha256'] == self.bindings[key]['sha256']
        assert sha(path) == proof['sha256'], key
        return proof, path, sha(proof_path)

    def read(self, key, folder='cells', verified=None):
        proof, path, digest = verified or self.proof(key, folder)
        cell = read(path)
        name, view, guard = key.split('-')
        rules = cell['result']['rules']
        assert identity(rules) == name
        assert cell['case']['name'] == name and cell['case']['rules'] == rules
        assert cell['view'] == view and cell['guard'] == guard
        return cell, proof, path, digest


class AccountingCache:
    """Only resume identical audited math on identical immutable source payloads."""

    def __init__(self, out, context, enabled=True):
        self.enabled = enabled
        self.context = context
        self.identity = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        self.root = out / 'audit-cache' / self.identity
        self.index_path = self.root / 'index.json'
        self.hits = 0
        self.written = 0
        if enabled and self.index_path.exists():
            index = read(self.index_path)
            assert index['context'] == context
            self.records = index['records']
        else:
            self.records = {}

    def get(self, key, proof, proof_sha256):
        if not self.enabled or key not in self.records:
            return None
        path = self.root / 'records' / (key + '.json')
        assert sha(path) == self.records[key], 'Audit-cache record drift'
        record = read(path)
        assert record['context_id'] == self.identity and record['key'] == key
        assert record['payload_path'] == proof['path']
        assert record['payload_sha256'] == proof['sha256']
        assert record['proof_sha256'] == proof_sha256
        self.hits += 1
        return record['checked']

    def put(self, key, proof, proof_sha256, checked):
        if not self.enabled:
            return
        path = self.root / 'records' / (key + '.json')
        write(path, dict(context_id=self.identity, key=key, payload_path=proof['path'],
            payload_sha256=proof['sha256'], proof_sha256=proof_sha256, checked=checked))
        self.records[key] = sha(path)
        self.written += 1
        if self.written % 100 == 0:
            self.flush()

    def flush(self):
        if self.enabled:
            write(self.index_path, dict(context=self.context, records=self.records))


def validate_inputs(out, protocol):
    assert protocol['algorithm'] == 'exhaustive_native_grid_v1'
    assert protocol['domains'] == DOMAINS and protocol['finite_domain'] == 5184
    assert protocol['lanes'] == list(LANES) and protocol['risk_fields'] == list(RISK_FIELDS)
    assert protocol['batch_size'] == 32
    assert protocol['initial'] == read(PARENT / 'results.json')['selected']['profit']
    assert sha(PARENT / 'COMPLETE.json') == protocol['parent_complete_sha256']
    assert sha(PARENT / 'results.json') == protocol['parent_results_sha256']
    assert sha(PARENT / 'independent-verification.json') == protocol['parent_audit_sha256']
    parent_audit = read(PARENT / 'independent-verification.json')
    assert parent_audit['status'] == 'PASS'
    assert parent_audit['parent_completion_sha256'] == protocol['parent_complete_sha256']
    assert sha(HELPER) == parent_audit['source_sha256']
    parent_protocol = read(PARENT / 'protocol.json')
    assert sha(DATA / 'manifest.json') == protocol['input_manifest_sha256'] == parent_protocol['input_manifest_sha256']
    assert protocol['cost_status'] == 'COST_INCONCLUSIVE' and protocol['holdout'] is False
    for name, digest in read(PARENT / 'COMPLETE.json')['artifacts'].items():
        assert sha(PARENT / name) == digest, name
    for name, digest in protocol['sources'].items():
        assert sha(ROOT / name) == digest, name
        assert sha(out / 'source_snapshot' / name) == digest, name
    for name, digest in protocol['input_hashes'].items():
        assert sha(DATA / name) == digest, name
    for name, digest in protocol['benchmark_hashes'].items():
        assert sha(ROOT / name) == digest, name
        cell = read(ROOT / name)
        guard = 'cent' if name.endswith('-cent.json') else 'raw'
        view = Path(name).stem.removesuffix('-cent').rsplit('-', 1)[1]
        assert cell['metrics'] == protocol['original_floors'][guard][view]
    catalog = read(out / 'catalog.json')
    initial = protocol['initial']
    initial_rules = read(PARENT / 'results.json')['cases'][initial]['rules']
    expected = full_catalog(initial_rules)
    assert catalog == dict(schema=1, axes=list(DOMAINS), cases=expected, finite_domain=5184)
    assert sha(out / 'catalog.json') == protocol['catalog_sha256']
    return catalog, initial_rules


def audit_cells(out, protocol, catalog, initial_rules, cache, payloads, summary=None):
    auditor = IndependentTapeAudit(protocol, read(DATA / 'manifest.json')['last_quote_utc'])
    cases = {case['name']: case for case in catalog['cases']}
    summaries = {}
    proof_hashes = {}
    source_hashes = {}
    origins = Counter()
    entries = 0
    proof_paths = sorted((out / 'cells-integrity').glob('*.json'))
    for number, proof_path in enumerate(proof_paths, 1):
        key = proof_path.stem
        name, view, guard = key.split('-')
        assert name in cases
        verified = payloads.proof(key)
        proof, path, proof_sha256 = verified
        checked = cache.get(key, proof, proof_sha256)
        if checked is None:
            cell, _, _, _ = payloads.read(key, verified=verified)
            checked = auditor.audit_cell(cell)
            cache.put(key, proof, proof_sha256, checked)
        assert checked['rules'] == cases[name]['rules']
        assert all(checked['rules'][field] == value for field, value in initial_rules.items()
                   if field not in DOMAINS)
        summaries.setdefault(name, {}).setdefault(guard, {})[view] = dict(
            metrics=checked['metrics'], risk=checked['risk'])
        if summary is not None:
            recorded = summary['summaries'][name][guard][view]
            assert recorded['metrics'] == checked['metrics']
            for field, value in recorded['risk'].items():
                equal(value, checked['risk'][field], 'summary risk ' + field)
        entries += checked['entries']
        proof_hashes[str(proof_path.relative_to(ROOT))] = proof_sha256
        source_hashes[str(path.relative_to(ROOT))] = proof['sha256']
        origins[proof['origin']] += 1
        if number % 250 == 0:
            print('PASS immutable accounting', number, '/', len(proof_paths), 'cells /',
                  entries, 'entries /', cache.hits, 'checkpoint hits', flush=True)
    cache.flush()
    return auditor, summaries, proof_hashes, source_hashes, origins, entries


def leaders(names, summaries, initial, floors, incumbents=None):
    """Independent globally ranked leaders, preserving current IDs on ties."""
    baseline = summaries[initial]
    accepted = sorted(name for name in names if qualified_rows(summaries[name], floors))
    assert initial in accepted
    current = {lane: initial for lane in LANES} if incumbents is None else incumbents
    assert set(current) == set(LANES) and all(name in accepted for name in current.values())
    selected = {lane: choose(current[lane], accepted, summaries, lane, floors, baseline) for lane in LANES}
    strict = sorted(name for name in accepted if reduced_risk(summaries[name], baseline))
    alternatives = dict(max_worst_net=min(accepted, key=lambda name: (
        -min(summaries[name][guard][view]['metrics']['net_usd'] for guard in GUARDS for view in VIEWS),
        *objective(summaries[name], 'profit'), name)))
    for field in RISK_FIELDS:
        alternatives['min_' + field] = min(accepted, key=lambda name: (
            max(summaries[name][guard][view]['risk'][field] for guard in GUARDS for view in VIEWS),
            *objective(summaries[name], 'profit'), name))
    return dict(selected=selected, qualified=accepted, strict_downside_improvers=strict,
                repair_status='STRICT_DOWNSIDE_IMPROVEMENT' if strict else 'NO_STRICT_DOWNSIDE_IMPROVEMENT',
                selected_repair_strict=reduced_risk(summaries[selected['repair']], baseline),
                diagnostic_alternatives=alternatives)


def audit_batches(out, protocol, catalog, summary, summaries):
    floors, initial = protocol['original_floors'], protocol['initial']
    active = set(read(PARENT / 'results.json')['visited'])
    assert len(active) == 163
    expected_batch_count = (5184 + protocol['batch_size'] - 1) // protocol['batch_size']
    assert len(summary['batches']) == expected_batch_count == 162
    assert summary['phases'] == summary['batches']
    ordered_names = [case['name'] for case in catalog['cases']]
    covered = []
    incumbents = {lane: initial for lane in LANES}
    for number, recorded in enumerate(summary['batches'], 1):
        start = (number - 1) * protocol['batch_size']
        stop = min(start + protocol['batch_size'], 5184)
        names = ordered_names[start:stop]
        frozen = dict(number=number, start_index=start, stop_index=stop,
                      catalog_sha256=protocol['catalog_sha256'], candidates=names)
        assert read(out / 'batches' / f'{number:03}-catalog.json') == frozen
        assert read(out / 'batches' / f'{number:03}-result.json') == recorded
        before = leaders(active, summaries, initial, floors, incumbents)
        assert before['selected'] == incumbents
        raw_pass = [name for name in names if qualify(
            {view: summaries[name]['raw'][view]['metrics'] for view in VIEWS}, floors['raw'])]
        full_pass = [name for name in names if qualified_rows(summaries[name], floors)]
        active.update(names)
        after = leaders(active, summaries, initial, floors, incumbents)
        for lane in LANES:
            if after['selected'][lane] != incumbents[lane]:
                assert objective(summaries[after['selected'][lane]], lane) < objective(summaries[incumbents[lane]], lane)
        incumbents = after['selected']
        expected = dict(frozen, raw_qualified=raw_pass, fully_qualified=full_pass,
            selected_before=before['selected'], selected_after=after['selected'],
            strict_downside_improvers=len(after['strict_downside_improvers']), visited_cases=len(active),
            improved={lane: objective(summaries[after['selected'][lane]], lane) <
                            objective(summaries[before['selected'][lane]], lane) for lane in LANES})
        assert recorded == expected, ('Historical batch state drift', number)
        covered.extend(names)
    assert covered == ordered_names and len(set(covered)) == 5184
    assert active == set(ordered_names) == set(summary['visited'])
    expected_final = leaders(active, summaries, initial, floors, incumbents)
    for field, value in expected_final.items():
        assert summary[field] == value, field
    for lane, name in expected_final['selected'].items():
        eligible = [candidate for candidate in expected_final['qualified'] if lane == 'profit' or
                    repair_eligible(summaries[candidate], summaries[initial])]
        best_score = min(objective(summaries[candidate], lane) for candidate in eligible)
        assert objective(summaries[name], lane) == best_score, 'Full-domain leader is not globally best'
    return expected_final


def run(out, checkpoint_only=False, use_cache=True):
    completion = out / 'COMPLETE.json'
    if not checkpoint_only:
        assert completion.exists(), 'Exhaustive campaign incomplete; final audit requires COMPLETE'
    protocol = read(out / 'protocol.json')
    catalog, initial_rules = validate_inputs(out, protocol)
    helper_sha256 = sha(HELPER)
    auditor_sha256 = sha(Path(__file__))
    context = dict(auditor_sha256=auditor_sha256, helper_sha256=helper_sha256,
                   protocol_sha256=sha(out / 'protocol.json'),
                   input_manifest_sha256=protocol['input_manifest_sha256'])
    cache = AccountingCache(out, context, use_cache)
    payloads = Payloads(out, protocol)
    complete_hash = sha(completion) if completion.exists() else None
    if checkpoint_only:
        audited = audit_cells(out, protocol, catalog, initial_rules, cache, payloads)
        _, summaries, proof_hashes, _, origins, entries = audited
        assert sha(Path(__file__)) == auditor_sha256 and sha(HELPER) == helper_sha256
        report = dict(status='INCOMPLETE_ACCOUNTING_CHECKPOINT', economic_replays=0,
            cells=len(proof_hashes), entries=entries, profiles_with_any_checked_cell=len(summaries),
            new_cell_proofs=origins['new'], reused_cell_proofs=origins['reused'],
            cache_context=cache.identity, cache_hits=cache.hits, auditor_sha256=auditor_sha256,
            protocol_sha256=context['protocol_sha256'],
            scope='Committed immutable cell accounting only; no full-domain selection or completion certification',
            campaign_complete_at_start=complete_hash is not None)
        write(out / 'audit-checkpoint.json', report)
        print('CHECKPOINT ONLY', len(proof_hashes), 'cells /', entries, 'entries; no completion verdict', flush=True)
        return report

    complete = read(completion)
    summary = read(out / 'results.json')
    assert complete['status'] == summary['status'] == 'EXHAUSTIVE_COMPLETE'
    assert complete['finite_domain'] == summary['finite_domain'] == 5184
    assert summary['initial'] == protocol['initial']
    assert summary['cost_status'] == 'COST_INCONCLUSIVE' and summary['holdout'] is False
    for name, digest in complete['artifacts'].items():
        assert sha(out / name) == digest, name
    auditor, summaries, proof_hashes, source_hashes, origins, entries = audit_cells(
        out, protocol, catalog, initial_rules, cache, payloads, summary)
    names = {case['name'] for case in catalog['cases']}
    assert len(names) == 5184
    assert summary['cases'] == {case['name']: case for case in catalog['cases']}
    assert set(summaries) == names == set(summary['summaries'])
    assert summary['visited'] == sorted(names)
    raw_pass = []
    for name, rows in summaries.items():
        assert set(rows.get('raw', {})) == set(VIEWS), ('Incomplete raw coverage', name)
        if qualify({view: rows['raw'][view]['metrics'] for view in VIEWS}, protocol['original_floors']['raw']):
            assert complete_rows(rows), ('Missing cent review', name)
            raw_pass.append(name)
    raw_proofs = sum(len(rows['raw']) for rows in summaries.values())
    cent_proofs = sum(len(rows.get('cent', {})) for rows in summaries.values())
    assert raw_proofs == 5184 * 3 == 15552
    assert cent_proofs == len(raw_pass) * 3
    assert len(proof_hashes) == raw_proofs + cent_proofs
    selected = audit_batches(out, protocol, catalog, summary, summaries)
    assert complete['selected'] == selected['selected']
    assert complete['visited_cases'] == 5184 and complete['processed_batches'] == 162
    assert complete['new_economic_cells'] == origins['new']
    assert complete['reused_parent_cells'] == origins['reused'] == 570
    assert len(list((out / 'cells').glob('*.json.gz'))) == origins['new']
    repeat_keys = {f'{name}-{view}-{guard}' for name in set(selected['selected'].values())
                   for guard in GUARDS for view in VIEWS}
    assert {path.stem for path in (out / 'repeats-integrity').glob('*.json')} == repeat_keys
    assert complete['fresh_repeats'] == len(repeat_keys)
    for key in sorted(repeat_keys):
        repeated, proof, _, _ = payloads.read(key, 'repeats')
        original, _, _, _ = payloads.read(key)
        assert proof['origin'] == 'new'
        for field in ('result', 'metrics', 'diagnostics'):
            assert repeated[field] == original[field], ('Fresh full-result mismatch', key, field)
    full_tick = {}
    for name in sorted(set(selected['selected'].values())):
        for guard in GUARDS:
            for view in VIEWS:
                key = f'{name}-{view}-{guard}'
                cell, _, _, _ = payloads.read(key)
                full_tick[key] = auditor.full_tick(cell)
                print('PASS independent full-tick', key, round(full_tick[key]['max_dd_pct'], 6), flush=True)
    for lane, name in selected['selected'].items():
        descriptor = read(out / f'selected-{lane}-research.json')
        assert descriptor['rules_id'] == name and descriptor['rules'] == summary['cases'][name]['rules']
        assert descriptor['status'] == 'RESEARCH_ONLY' and descriptor['lane'] == lane
        assert descriptor['protocol_sha256'] == sha(out / 'protocol.json')
        assert descriptor['runtime_qualified'] is False and descriptor['adapter_required'] is True
    assert sha(completion) == complete_hash
    assert sha(Path(__file__)) == auditor_sha256 and sha(HELPER) == helper_sha256
    assert sha(out / 'protocol.json') == context['protocol_sha256']
    report = dict(status='PASS', economic_replays=0, finite_domain=5184, visited_cases=5184,
        processed_batches=162, cells=len(proof_hashes), entries=entries, raw_cells=raw_proofs,
        cent_cells=cent_proofs, raw_qualified=len(raw_pass), fully_qualified=len(selected['qualified']),
        new_cell_proofs=origins['new'], reused_cell_proofs=origins['reused'],
        selected=selected['selected'], independent_full_tick_dd=full_tick,
        strict_downside_improvers=selected['strict_downside_improvers'],
        any_strict_downside_improvement=bool(selected['strict_downside_improvers']),
        selected_repair_strict=selected['selected_repair_strict'],
        scope='Complete frozen5184 catalog, all raw/required cent accounting, exact historical batches, globally best qualified objectives and selected full-tick DD',
        cost_status='COST_INCONCLUSIVE', source_sha256=auditor_sha256, helper_sha256=helper_sha256,
        parent_completion_sha256=complete_hash, input_manifest_sha256=sha(DATA / 'manifest.json'),
        audit_cache_context=cache.identity, audit_cache_hits=cache.hits,
        audit_cache_index_sha256=sha(cache.index_path) if use_cache else None,
        audited_cells=proof_hashes, payload_hashes=source_hashes)
    write(out / 'independent-verification.json', report)
    print('PASS EXHAUSTIVE', len(proof_hashes), 'cells /', entries,
          'entries /5184profiles /162batches', flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='runs/c22-exhaustive-loop-2026-10-25')
    parser.add_argument('--checkpoint-only', action='store_true')
    parser.add_argument('--no-cache', action='store_true')
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to((ROOT / 'runs').resolve()):
        raise ValueError('Audit output must remain under runs/')
    run(out, args.checkpoint_only, not args.no_cache)


if __name__ == '__main__':
    main()
