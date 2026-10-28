"""Seal passive Selected26b8 backup evidence; no broker connection or authority.

Version2 binds the deployed archive, account and complete bootstrap audit prefix.
All in-window audit rows remain sealed, including excluded cohorts/accounts and
malformed records. Reports disclose every denominator and missing data field.
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError('forward_aware_utc_required')
    return stamp


def _raw(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _hex(value, size=64):
    return isinstance(value, str) and len(value) == size and all(c in '0123456789abcdef' for c in value)


def _new_output(path, *inputs):
    path = Path(path).resolve()
    if (not path.is_relative_to(ROOT / 'runs') or path.exists()
            or any(path == Path(item).resolve() or Path(item).resolve().is_relative_to(path) for item in inputs)):
        raise ValueError('forward_new_ignored_output_required')
    path.mkdir(mode=0o700, parents=True)
    return path


def _write(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _read_rows(path):
    path = Path(path).resolve()
    if not path.is_file() or Path(str(path) + '-wal').exists():
        raise ValueError('forward_consistent_backup_required')
    before = _file_hash(path)
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        connection.execute('BEGIN')
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('forward_journal_integrity_failed')
        rows = connection.execute('SELECT id,payload FROM audit_events ORDER BY id').fetchall()
        identity = connection.execute("SELECT value FROM kv WHERE key='identity'").fetchone()
        connection.rollback()
    finally:
        connection.close()
    if _file_hash(path) != before:
        raise ValueError('forward_source_changed_during_read')
    return rows, before, json.loads(identity[0]) if identity else None


def _prefix(rows, maximum):
    digest = hashlib.sha256()
    selected = [(ident, raw) for ident, raw in rows if ident <= maximum]
    for ident, raw in selected:
        digest.update(_raw([ident, raw]))
    return dict(count=len(selected), last_audit_id=maximum,
                prefix_sha256=digest.hexdigest(), last_payload_sha256=_hash(selected[-1][1].encode()) if selected else None)


def _source_binding(manifest_path):
    manifest_path = Path(manifest_path)
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    fields = manifest.get('files')
    required = {'config/c22-selected-demo.json', 'scripts/c22_selected/runner.py',
                'scripts/c22_selected/strategy.py', 'scripts/c22_selected/execution.py',
                'scripts/demo_runtime/runner.py'}
    if (not isinstance(fields, dict) or not required.issubset(fields)
            or any(not _hex(value) for value in fields.values())):
        raise ValueError('forward_source_manifest_invalid')
    archive = manifest_path.parent / 'release.tar.gz'
    with tarfile.open(archive) as stream:
        payload = {}
        for name, digest in fields.items():
            member = stream.getmember(name)
            if not member.isfile() or member.size > 16 * 1024 * 1024:
                raise ValueError('forward_source_archive_invalid')
            raw = stream.extractfile(member).read()
            if _hash(raw) != digest:
                raise ValueError('forward_source_archive_hash_mismatch')
            payload[name] = raw
    config = json.loads(payload['config/c22-selected-demo.json'])
    bindings = config.get('source_hashes')
    if (config.get('contract_id') != '26b8bcd69e043653' or config.get('volume') != .01
            or not isinstance(bindings, dict) or len(bindings) < 21
            or any(name not in payload or _hash(payload[name]) != digest for name, digest in bindings.items())):
        raise ValueError('forward_selected_config_binding_invalid')
    # Exact deployed runtime hash algorithm; no imports or broker initialization.
    base = b''.join(payload[name] for folder in ('demo_runtime', 'c22h4', 'trial30')
        for name in sorted(payload) if name.startswith('scripts/' + folder + '/') and name.endswith('.py'))
    digest = hashlib.sha256(_hash(base).encode())
    for name in sorted(payload):
        if name.startswith('scripts/c22_selected/') and name.endswith('.py'):
            digest.update(Path(name).name.encode())
            digest.update(payload[name])
    return dict(manifest_sha256=_hash(raw_manifest), archive_sha256=_file_hash(archive),
        config_sha256=_hash(json.dumps(config, sort_keys=True).encode()), release_hash=digest.hexdigest(),
        source_bindings=len(bindings), source_files_sha256=fields), raw_manifest, payload['config/c22-selected-demo.json']


def freeze_protocol(journal, manifest, output, *, release_hash, config_hash,
                    account_fingerprint, freeze_utc, exposed_through_utc, now):
    """Freeze a verified current bootstrap before later unseen audit records."""
    now, freeze, exposed = _utc(now), _utc(freeze_utc), _utc(exposed_through_utc)
    if not _hex(release_hash) or not _hex(config_hash) or not _hex(account_fingerprint, 16):
        raise ValueError('forward_cohort_identity_required')
    if not exposed <= now <= freeze:
        raise ValueError('forward_freeze_cannot_be_backdated')
    rows, source_sha, identity = _read_rows(journal)
    if not rows or identity != account_fingerprint:
        raise ValueError('forward_bootstrap_account_invalid')
    events = [json.loads(raw) for _, raw in rows]
    latest = max(_utc(event['utc']) for event in events)
    if not latest <= exposed or not timedelta(0) <= now - latest <= timedelta(minutes=5):
        raise ValueError('forward_current_bootstrap_required')
    matching = [event for event in events if event.get('release_hash') == release_hash and event.get('config_hash') == config_hash]
    if not matching or any(event.get('account_fingerprint') != account_fingerprint for event in matching):
        raise ValueError('forward_bootstrap_account_invalid')
    source, raw_manifest, config_bytes = _source_binding(manifest)
    if source['release_hash'] != release_hash or source['config_sha256'] != config_hash:
        raise ValueError('forward_source_cohort_mismatch')
    protocol = dict(version=2, candidate_id='26b8bcd69e043653', created_utc=now.isoformat(),
        freeze_utc=freeze.isoformat(), exposed_through_utc=exposed.isoformat(),
        release_hash=release_hash, config_hash=config_hash, account_fingerprint=account_fingerprint,
        cohort_id=release_hash + ':' + config_hash, source_binding=source,
        source_manifest_sha256=_hash(raw_manifest), bootstrap_journal_sha256=source_sha,
        bootstrap_anchor=_prefix(rows, rows[-1][0]), bootstrap_latest_utc=latest.isoformat(),
        collector_source_sha256=_file_hash(Path(__file__)),
        collection_policy='ALL_WINDOW_AUDIT_ROWS_WITH_EXCLUSION_DENOMINATORS',
        qualification='SEPARATE_T21_PROTOCOL_REQUIRED', execution_authorized=False)
    protocol['protocol_sha256'] = _hash(_raw(protocol))
    target = _new_output(output, journal, manifest)
    _write(target / 'source-manifest.json', raw_manifest)
    _write(target / 'selected-config.json', config_bytes)
    _write(target / 'protocol.json', _raw(protocol))
    _write(target / 'collector-source.py', Path(__file__).read_bytes())
    return protocol


def _protocol(path):
    path = Path(path)
    value = json.loads((path / 'protocol.json').read_bytes())
    material = {key: item for key, item in value.items() if key != 'protocol_sha256'}
    if (value.get('version') != 2 or value.get('execution_authorized') is not False
            or value.get('candidate_id') != '26b8bcd69e043653'
            or not _hex(value.get('account_fingerprint'), 16)
            or value.get('cohort_id') != value['release_hash'] + ':' + value['config_hash']
            or _hash(_raw(material)) != value['protocol_sha256']
            or _file_hash(path / 'source-manifest.json') != value['source_manifest_sha256']
            or _file_hash(path / 'collector-source.py') != value['collector_source_sha256']
            or _hash(json.dumps(json.loads((path / 'selected-config.json').read_bytes()), sort_keys=True).encode()) != value['config_hash']
            or not _utc(value['bootstrap_latest_utc']) <= _utc(value['exposed_through_utc']) <= _utc(value['created_utc']) <= _utc(value['freeze_utc'])):
        raise ValueError('forward_protocol_integrity_failed')
    return value


def _selection(event, protocol):
    if not isinstance(event, dict) or not isinstance(event.get('kind'), str):
        return 'malformed_event'
    if event.get('release_hash') != protocol['release_hash'] or event.get('config_hash') != protocol['config_hash']:
        return 'different_or_missing_cohort'
    if event.get('account_fingerprint') != protocol['account_fingerprint']:
        return 'account_mismatch'
    if not isinstance(event.get('event_id'), str) or not event['event_id']:
        return 'event_id_missing'
    return None


def _report(rows, *, since, until):
    matching = [row for row in rows if row['exclusion_reason'] is None]
    excluded = Counter(row['exclusion_reason'] for row in rows if row['exclusion_reason'] is not None)
    kinds, blockers = Counter(), Counter()
    signal_bars = set()
    cycles, unknown, closed, fills = 0, 0, [], 0
    cycle_times = []
    for row in matching:
        event = row['payload']
        kind = event['kind']
        kinds[kind] += 1
        if kind == 'SIGNAL' and event.get('direction') in (-1, 1):
            signal_bars.add(str(event.get('bar') or event.get('bar_close_utc') or event.get('correlation_id') or row['audit_id']))
        if kind == 'CYCLE':
            cycles += 1
            cycle_times.append(_utc(event['utc']))
            result = event.get('result') or {}
            if result.get('status') == 'BLOCKED':
                blockers[str(result.get('reason') or 'UNSPECIFIED')] += 1
            unknown += result.get('status') == 'UNKNOWN' or result.get('position_protection') == 'unknown'
        if kind == 'LIFECYCLE':
            lifecycle = event.get('event') or {}
            fills += lifecycle.get('kind') == 'FILLED'
            if lifecycle.get('kind') in {'CLOSED', 'SAFETY_CLOSED'}:
                closed.append(lifecycle)
    ordered = sorted(cycle_times)
    gaps = [(right - left).total_seconds() for left, right in zip(ordered, ordered[1:])]
    known_net = [float(item['net']) for item in closed if type(item.get('net')) in (int, float) and math.isfinite(item['net'])]
    missing_net = len(closed) - len(known_net)
    ids = [row['audit_id'] for row in rows]
    id_gaps = [{'after_id': left, 'before_id': right, 'missing_count': right - left - 1}
               for left, right in zip(ids, ids[1:]) if right > left + 1]
    return dict(coverage='OBSERVED_AUDIT_ONLY' if matching else 'NO_MATCHING_RECORDS',
        window_seconds=(until - since).total_seconds(), source_window_records=len(rows), matched_records=len(matching),
        excluded_records=sum(excluded.values()), excluded_by_reason=dict(excluded), audit_id_gaps=id_gaps,
        audit_records=len(matching), audit_kind_counts=dict(kinds), cycle_count=cycles,
        distinct_signal_bars=len(signal_bars), blocked_cycles=dict(blockers), unknown_cycles=unknown,
        request_count=kinds['REQUEST'], response_count=kinds['RESPONSE'],
        broker_fill_count=fills if kinds['LIFECYCLE'] else None, closed_position_events=len(closed),
        observed_closed_net_usd=sum(known_net) if closed and not missing_net else None, closed_net_missing_events=missing_net,
        cashflows='NOT_CAPTURED_IN_AUDIT', cashflow_total_usd=None,
        broker_full_history_coverage='NOT_PROVEN_BY_AUDIT_BATCH', tick_feed_coverage='NOT_CAPTURED',
        first_cycle_utc=ordered[0].isoformat() if ordered else None, last_cycle_utc=ordered[-1].isoformat() if ordered else None,
        maximum_observed_cycle_gap_seconds=max(gaps) if gaps else None,
        timestamp_regressions=sum(right < left for left, right in zip(cycle_times, cycle_times[1:])),
        costs='COST_INCONCLUSIVE', profitability='INCONCLUSIVE',
        independent_trade_samples=len({item.get('position_id') for item in closed}) if closed and all(type(item.get('position_id')) is int for item in closed) else None,
        limitations=['All in-window audit cohorts retained; report metrics use matching account/cohort only',
            'Requests and cost views are not independent broker fills', 'Missing cashflow/tick/ledger data is unknown, never zero',
            'Audit observation counts do not establish profitability or execution authority'])


def _broker_attachment(raw, protocol, *, since, until, now):
    if raw is None:
        return None
    if not isinstance(raw, bytes):
        raise ValueError('forward_broker_packet_bytes_required')
    packet = json.loads(raw)
    stamp = _utc(packet['captured_utc'])
    start, end = _utc(packet['history_start_utc']), _utc(packet['history_end_utc'])
    if (packet.get('account_fingerprint') != protocol['account_fingerprint']
            or packet.get('release_hash') != protocol['release_hash'] or packet.get('config_hash') != protocol['config_hash']
            or packet.get('source') != 'existing_sender_reads' or packet.get('execution_authorized') is not False
            or packet.get('demo_verified') is not True or packet.get('hedging_verified') is not True
            or packet.get('history_complete') is not True or packet.get('symbol') != 'XAUUSDm'
            or packet.get('positions') != 0 or packet.get('orders') != 0
            or packet.get('terminal', {}).get('connected') is not True
            or packet.get('account', {}).get('currency') != 'USD'
            or not stamp <= _utc(packet['read_observed_utc']) <= now
            or not timedelta(0) <= now - stamp <= timedelta(minutes=5)
            or start != datetime(1970, 1, 1, tzinfo=timezone.utc) or not until <= end <= stamp
            or type(packet.get('history_deals_total')) is not int
            or packet['history_deals_total'] != len(packet['history_deals'])):
        raise ValueError('forward_broker_packet_binding_invalid')
    deals, tickets, cash = packet['history_deals'], set(), []
    cashflows = []
    for deal in deals:
        if (type(deal['ticket']) is not int or deal['ticket'] <= 0 or deal['ticket'] in tickets
                or type(deal['type']) is not int or deal['type'] < 0
                or type(deal['time_msc']) is not int or not 0 <= deal['time_msc'] <= end.timestamp() * 1000):
            raise ValueError('forward_broker_ledger_invalid')
        tickets.add(deal['ticket'])
        amounts = [deal[name] for name in ('profit', 'commission', 'swap', 'fee')]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in amounts):
            raise ValueError('forward_broker_ledger_invalid')
        cash.extend(amounts)
        if deal['type'] not in (0, 1) and since.timestamp() * 1000 <= deal['time_msc'] < until.timestamp() * 1000:
            cashflows.append(dict(ticket=deal['ticket'], type=deal['type'], time_msc=deal['time_msc'], net_usd=math.fsum(amounts)))
    balance = packet['account']['balance']
    if type(balance) not in (int, float) or not math.isfinite(balance) or abs(math.fsum(cash) - balance) > .02:
        raise ValueError('forward_broker_cash_reconciliation_failed')
    return dict(packet_sha256=_hash(raw), captured_utc=stamp.isoformat(), history_end_utc=end.isoformat(),
        epoch_deal_count=len(deals), epoch_cash_total_usd=math.fsum(cash), balance_usd=balance,
        cashflows=cashflows, window_cashflow_total_usd=math.fsum(item['net_usd'] for item in cashflows),
        costs='OBSERVED_SIGNED_COMPONENTS_NOT_QUALIFIED', qualification='COST_INCONCLUSIVE')


def _classification(rows, definition, since, lineage):
    matching = [row for row in rows if row['exclusion_reason'] is None]
    prospective = (bool(matching) and lineage and since >= _utc(definition['freeze_utc'])
        and all(row['audit_id'] > definition['bootstrap_anchor']['last_audit_id'] for row in matching)
        and not any(row['exclusion_reason'] in {'account_mismatch', 'malformed_event', 'event_id_missing'} for row in rows))
    return ('PROSPECTIVE_COLLECTION_ONLY', len(matching)) if prospective else ('REUSED_HISTORY', 0)


def seal_batch(journal, protocol, output, *, since, until, now, broker_bytes=None):
    """Seal complete audit window plus optional actual same-sender ledger bytes."""
    since, until, now = _utc(since), _utc(until), _utc(now)
    if not since < until <= now:
        raise ValueError('forward_window_invalid')
    definition = _protocol(protocol)
    source, source_sha, identity = _read_rows(journal)
    if identity != definition['account_fingerprint']:
        raise ValueError('forward_source_account_mismatch')
    anchor = definition['bootstrap_anchor']
    lineage = _prefix(source, anchor['last_audit_id']) == anchor
    if since >= _utc(definition['freeze_utc']) and not lineage:
        raise ValueError('forward_bootstrap_lineage_changed')
    records, event_ids, unscoped = [], set(), []
    for ident, raw in source:
        try:
            event = json.loads(raw)
            stamp = _utc(event['utc'])
        except (ValueError, KeyError, TypeError):
            unscoped.append(dict(audit_id=ident, payload_sha256=_hash(raw.encode()), payload_raw=raw))
            continue
        if not since <= stamp < until:
            continue
        reason = _selection(event, definition)
        if reason is None:
            if event['event_id'] in event_ids:
                reason = 'event_id_duplicate'
            event_ids.add(event['event_id'])
        records.append(dict(audit_id=ident, payload_sha256=_hash(raw.encode()), payload_raw=raw,
                            payload=event, exclusion_reason=reason))
        if len(records) > 100000:
            raise ValueError('forward_batch_record_limit_exceeded')
    classification, count = _classification(records, definition, since, lineage)
    if unscoped:
        classification, count = 'REUSED_HISTORY', 0
    previous, sealed = definition['protocol_sha256'], []
    for sequence, record in enumerate(records, 1):
        value = dict(sequence=sequence, previous_sha256=previous, **record)
        value['record_sha256'] = _hash(_raw(value))
        previous = value['record_sha256']
        sealed.append(value)
    raw = b''.join(_raw(row) for row in sealed)
    attachment = _broker_attachment(broker_bytes, definition, since=since, until=until, now=now)
    report = _report(records, since=since, until=until)
    report['unscoped_malformed_source_records'] = len(unscoped)
    if attachment is not None:
        report.update(cashflows='OBSERVED_RECONCILED_SAME_SENDER_LEDGER',
            cashflow_total_usd=attachment['window_cashflow_total_usd'], broker_full_history_coverage='EPOCH_CASH_RECONCILED',
            broker_cost_components='OBSERVED_SIGNED_COMPONENTS_NOT_QUALIFIED')
    result = dict(version=2, candidate_id=definition['candidate_id'], cohort_id=definition['cohort_id'],
        account_fingerprint=definition['account_fingerprint'], protocol_sha256=definition['protocol_sha256'],
        source_journal_sha256=source_sha, source_manifest_sha256=definition['source_manifest_sha256'],
        since_utc=since.isoformat(), until_utc=until.isoformat(), sealed_utc=now.isoformat(),
        data_classification=classification, records=len(records), matched_records=report['matched_records'],
        prospective_observations=count, audit_ids=[row['audit_id'] for row in records], audit_sha256=_hash(raw),
        bootstrap_lineage_verified=lineage, last_record_sha256=previous, report=report,
        unscoped_malformed=unscoped, broker_attachment=attachment,
        execution_authorized=False, qualification='NOT_ESTABLISHED')
    target = _new_output(output, journal, protocol)
    _write(target / 'audit.jsonl', raw)
    for name in ('protocol.json', 'source-manifest.json', 'selected-config.json', 'collector-source.py'):
        _write(target / name, (Path(protocol) / name).read_bytes())
    if broker_bytes is not None:
        _write(target / 'broker.json', broker_bytes)
    _write(target / 'manifest.json', _raw(result))
    return result


def verify_batch(path, *, journal=None):
    """Recompute chain, scope, classification, denominators and real attachment."""
    path = Path(path)
    protocol = _protocol(path)
    manifest = json.loads((path / 'manifest.json').read_bytes())
    raw = (path / 'audit.jsonl').read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('forward_audit_tail_incomplete')
    if _hash(raw) != manifest['audit_sha256'] or manifest['protocol_sha256'] != protocol['protocol_sha256']:
        raise ValueError('forward_batch_hash_mismatch')
    rows, seen, previous = [], set(), protocol['protocol_sha256']
    for sequence, line in enumerate(raw.splitlines(), 1):
        record = json.loads(line)
        material = {key: value for key, value in record.items() if key != 'record_sha256'}
        event = record['payload']
        selection = _selection(event, protocol)
        if selection is None:
            selection = 'event_id_duplicate' if event['event_id'] in seen else None
            seen.add(event['event_id'])
        if (record['sequence'] != sequence or record['previous_sha256'] != previous
                or _hash(record['payload_raw'].encode()) != record['payload_sha256']
                or json.loads(record['payload_raw']) != event or selection != record['exclusion_reason']
                or record['record_sha256'] != _hash(_raw(material))):
            raise ValueError('forward_audit_chain_invalid')
        previous = record['record_sha256']
        rows.append(record)
    since, until, sealed = _utc(manifest['since_utc']), _utc(manifest['until_utc']), _utc(manifest['sealed_utc'])
    classification, count = _classification(rows, protocol, since, manifest['bootstrap_lineage_verified'])
    if manifest['unscoped_malformed']:
        classification, count = 'REUSED_HISTORY', 0
    if (manifest['data_classification'] != classification or manifest['prospective_observations'] != count
            or manifest['execution_authorized'] is not False or manifest['qualification'] != 'NOT_ESTABLISHED'):
        raise ValueError('forward_classification_invalid')
    if not since < until <= sealed or any(not since <= _utc(row['payload']['utc']) < until for row in rows):
        raise ValueError('forward_window_invalid')
    report = _report(rows, since=since, until=until)
    report['unscoped_malformed_source_records'] = len(manifest['unscoped_malformed'])
    attachment = None
    if manifest['broker_attachment'] is not None:
        attachment = _broker_attachment((path / 'broker.json').read_bytes(), protocol, since=since, until=until, now=sealed)
        report.update(cashflows='OBSERVED_RECONCILED_SAME_SENDER_LEDGER',
            cashflow_total_usd=attachment['window_cashflow_total_usd'], broker_full_history_coverage='EPOCH_CASH_RECONCILED',
            broker_cost_components='OBSERVED_SIGNED_COMPONENTS_NOT_QUALIFIED')
    if (len(rows) != manifest['records'] or previous != manifest['last_record_sha256']
            or manifest['audit_ids'] != [row['audit_id'] for row in rows]
            or manifest['report'] != report or attachment != manifest['broker_attachment']):
        raise ValueError('forward_report_coverage_mismatch')
    if journal is not None:
        source, source_sha, identity = _read_rows(journal)
        if source_sha != manifest['source_journal_sha256'] or identity != protocol['account_fingerprint']:
            raise ValueError('forward_verification_source_mismatch')
        lineage = _prefix(source, protocol['bootstrap_anchor']['last_audit_id']) == protocol['bootstrap_anchor']
        expected, unscoped = [], []
        for ident, raw_payload in source:
            try:
                stamp = _utc(json.loads(raw_payload)['utc'])
            except (ValueError, KeyError, TypeError):
                unscoped.append(dict(audit_id=ident, payload_sha256=_hash(raw_payload.encode()), payload_raw=raw_payload))
                continue
            if since <= stamp < until:
                expected.append((ident, raw_payload))
        if (expected != [(row['audit_id'], row['payload_raw']) for row in rows]
                or unscoped != manifest['unscoped_malformed']
                or lineage != manifest['bootstrap_lineage_verified']):
            raise ValueError('forward_source_coverage_mismatch')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path)
    parser.add_argument('--protocol', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--since')
    parser.add_argument('--until')
    parser.add_argument('--broker', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    if args.verify is not None:
        result = verify_batch(args.verify, journal=args.journal)
    else:
        if not all((args.journal, args.protocol, args.out, args.since, args.until)):
            parser.error('seal requires journal/protocol/out/since/until')
        result = seal_batch(args.journal, args.protocol, args.out,
            since=args.since, until=args.until, now=datetime.now(timezone.utc),
            broker_bytes=args.broker.read_bytes() if args.broker else None)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
