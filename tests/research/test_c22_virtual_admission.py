"""Causal virtual admissions: synthetic regressions, not economic selection."""
from types import SimpleNamespace
import unittest
import pandas as pd
from scripts.research.c22_virtual_admission import NativeAdmissionVeto, effective_summary
from scripts.research.c22_profit_preservation import replay
from scripts.research.breakout_models import Costs
from tests.research.test_c22_risk_replay import BROKER, VALID_SWAP, frame_at, native_rules, tape_at


class VirtualAdmissionTests(unittest.TestCase):
    def test_exact_admission_only_and_outcome_fields_never_enter_decision(self):
        event=dict(time_utc='2026-04-07T12:15:00.076Z',direction=-1,reason='admitted')
        guard=NativeAdmissionVeto([event|dict(net=-999,exit_time_utc='2099-01-01')])
        changed=NativeAdmissionVeto([event|dict(net=999,exit_time_utc='2100-01-01')])
        ms=pd.Timestamp(event['time_utc']).value//10**6
        self.assertEqual(guard.evidence_sha256,changed.evidence_sha256)
        for gate in (guard,changed):
            self.assertIsNone(gate(SimpleNamespace(direction=-1),ms,1,[]))
            self.assertIsNotNone(gate(SimpleNamespace(direction=1),ms,100000,[]))
            self.assertIsNotNone(gate(SimpleNamespace(direction=-1),ms+1,100000,[]))
        for delta in ({'time_utc':'2026-04-07T12:15'}, {'time_utc':'2026-04-07T12:15+07:00'},
                      {'time_utc':'2026-04-07T12:15:00.000001Z'}, {'direction':True}):
            with self.assertRaises(ValueError):NativeAdmissionVeto([event|delta])
        with self.assertRaises(ValueError):
            NativeAdmissionVeto([event,event|{'reason':'risk_cap'}])

    def test_native_veto_control_has_same_ledger_and_future_changes_do_not_leak(self):
        frame=frame_at(['2026-04-07T12:00Z','2026-04-07T12:15Z','2026-04-07T12:30Z',
                        '2026-04-07T12:45Z','2026-04-07T13:00Z'],[-1,0,-1,1,0])
        stamps=['2026-04-07T12:15Z','2026-04-07T12:30Z','2026-04-07T12:45Z',
                '2026-04-07T13:00Z','2026-04-07T13:15Z']
        ticks=tape_at(stamps,[100,100,110,110,110]);future=tape_at(stamps,[100,100,90,90,90])
        start=pd.Timestamp('2026-04-07T00:00Z');end=pd.Timestamp('2026-04-07T13:16Z')
        cutoff=pd.Timestamp('2026-04-07T12:31Z')
        def run(tape,**kwargs):
            return replay(frame,tape,BROKER,native_rules(),Costs(),start=start,
                          end=kwargs.pop('end',end),swap_policy=VALID_SWAP,**kwargs)
        native=run(ticks);changed=run(future)
        self.assertNotEqual(native['ledger'],changed['ledger'])
        def past(events):return [e for e in events if pd.Timestamp(e['time_utc'])<cutoff]
        prefix=run(ticks,end=cutoff,finalize=False)
        self.assertEqual(past(native['admission_events']),prefix['admission_events'])
        self.assertEqual(past(native['admission_events']),past(changed['admission_events']))
        for reference in (native,changed):
            veto=NativeAdmissionVeto(reference['admission_events'])
            candidate_prefix=run(ticks,end=cutoff,finalize=False,gate=veto,gate_name='virtual-native-v1')
            self.assertEqual(candidate_prefix['admission_events'],prefix['admission_events'])
        control=run(ticks,gate=NativeAdmissionVeto(native['admission_events']),gate_name='virtual-native-v1')
        for key in ('ledger','final_balance','max_dd_pct'):
            self.assertEqual(control[key],native[key])

    def test_virtual_permission_cannot_bypass_actual_equity_cap(self):
        frame=frame_at(['2026-04-07T12:00Z','2026-04-07T12:15Z'],[1,0]);frame['atr']=10.
        ticks=tape_at(['2026-04-07T12:15Z','2026-04-07T12:30Z'],[100,100])
        veto=NativeAdmissionVeto([dict(time_utc='2026-04-07T12:15Z',direction=1,reason='admitted')])
        result=replay(frame,ticks,BROKER,native_rules(),Costs(),start=pd.Timestamp('2026-04-07T00:00Z'),
                      end=pd.Timestamp('2026-04-07T12:31Z'),swap_policy=VALID_SWAP,gate=veto,gate_name='virtual-native-v1')
        self.assertEqual(result['ledger'],[])
        self.assertEqual(result['rejections']['risk_cap'],1)
        self.assertEqual(result['final_balance'],200)

    def test_virtual_cap_rejections_cannot_disappear_from_effective_lock_metric(self):
        def event(day,reason):return dict(time_utc=f'2026-04-{day:02}T12:00Z',direction=1,reason=reason)
        base=dict(ledger=[],equity=[dict(equity_usd=200.)],final_balance=200.,max_dd_pct=0.)
        virtual=base|dict(admission_events=[event(7,'risk_cap'),event(8,'risk_cap'),event(9,'admitted')],
                          rejections={'risk_cap':2})
        actual=base|dict(admission_events=[event(7,'shadow_native_risk_cap'),event(8,'shadow_native_risk_cap')],
                         rejections={'risk_cap':0,'shadow_native_risk_cap':2})
        result=effective_summary(actual,virtual)
        native=effective_summary(virtual,virtual)
        self.assertEqual(result['actual_cap_rejection_span_days'],0)
        self.assertEqual(result['virtual_cap_rejection_span_days'],1)
        self.assertGreaterEqual(result['cap_rejection_span_days'],native['cap_rejection_span_days'])
        self.assertEqual(result['rejections']['risk_cap'],0)
        self.assertEqual(result['virtual_rejections']['risk_cap'],2)

    def test_equal_timestamp_order_cannot_inflate_native_duration_benchmark(self):
        def event(day,reason,direction=1):
            return dict(time_utc=f'2026-04-{day:02}T12:00Z',direction=direction,reason=reason)
        base=dict(ledger=[],equity=[],final_balance=200.,max_dd_pct=0.,rejections={})
        virtual=base|dict(admission_events=[event(1,'admitted'),event(4,'admitted'),
            event(7,'risk_cap'),event(14,'late_quote'),event(14,'risk_cap',-1),event(15,'risk_cap')])
        candidate=base|dict(admission_events=[event(1,'risk_cap'),event(4,'risk_cap'),
            event(7,'shadow_native_risk_cap'),event(14,'late_quote'),
            event(14,'shadow_native_risk_cap',-1),event(15,'shadow_native_risk_cap')])
        native=effective_summary(virtual,virtual)
        actual=effective_summary(candidate,virtual)
        self.assertEqual(native['cap_rejection_span_days'],1.)
        self.assertEqual(actual['actual_cap_rejection_span_days'],3.)
        self.assertGreater(actual['cap_rejection_span_days'],native['cap_rejection_span_days'])

if __name__=='__main__':unittest.main()
