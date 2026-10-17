#ifndef FREQUENCY_RESEARCH_CASES
#define FREQUENCY_RESEARCH_CASES
#include "FrequencyResearchCore.mqh"
int fr_failures=0;
void FRCheck(bool ok,const string &name);
FRBar FRCaseBar(const long utc,const double o,const double h,const double l,const double c)
{ FRBar b;b.utc=utc;b.open=o;b.high=h;b.low=l;b.close=c;return b; }
void FRRunCases()
{
   FRCheck(!FRTesterAllowed(false,true,true,true),"test_live_chart_is_rejected");
   FRCheck(!FRTesterAllowed(true,true,false,true),"test_unattested_costs_are_rejected");
   FRCheck(FRAdmit(20,200,0.01,0.01,0.01,100,200,0,1,false)==FR_OK &&
           FRAdmit(20.01,200,0.01,0.01,0.01,100,200,0,1,false)==FR_RISK,
           "test_exact_risk_cap_and_one_cent_over");
   FRCheck(FRAdmit(1,200,0.01,0.02,0.01,100,200,0,1,false)==FR_VOLUME,
           "test_minimum_lot_never_rounds_up");
   FRBar previous,current; previous.utc=600; previous.open=101; previous.high=102;
   previous.low=99; previous.close=100; current.utc=900; current.open=100;
   current.high=104; current.low=100; current.close=103;
   FRSignal sig={};
   FRCheck(FRPullback(previous,current,100,99,101,100,110,109,111,2,sig) &&
           sig.direction==1 && MathAbs(sig.stop_anchor-98.8)<1e-9,
           "test_pullback_reclaim_has_literal_swing_stop");
   FRSession session;session.Reset(420);
   for(int i=0;i<6;i++) session.Push(FRCaseBar(25200+i*300,100,102,98,100),2,sig);
   bool breakout=session.Push(FRCaseBar(27000,101,104,101,103),2,sig);
   bool retest=session.Push(FRCaseBar(27300,103,104,101.9,103),2,sig);
   FRCheck(!breakout && retest && sig.direction==1 && session.used &&
           MathAbs(sig.stop_anchor-101.7)<1e-9,
           "test_session_requires_later_retest_and_consumes_attempt");
   FRSeries series;series.Reset();
   for(int i=0;i<110;i++) series.Push(FRCaseBar(i*900,220-i,220.25-i,219.75-i,220-i));
   FRCheck(FRC22(series,150,true,sig) && sig.direction==-1 &&
           !FRC22(series,150,false,sig),"test_c22_sell_precedence_and_closed_macro_gate");
   FRPlan plan;sig.direction=-1;sig.atr=2;sig.stop_anchor=105;
   FRCheck(FRPrepare(sig,false,100,100.2,0.1,plan) &&
           MathAbs(plan.stop-105.2)<1e-9 && MathAbs(plan.target-89.6)<1e-9,
           "test_sell_structure_stop_uses_ask_spread");
   FRCheck(FRFillState(10010,true,0.005,5,20)==FR_CONTAIN &&
           FRFillState(10012,false,0,0,20)==FR_PENDING &&
           FRFillState(10009,true,0.01,21,20)==FR_CONTAIN &&
           FRFillState(10009,true,0.01,19,20)==FR_CONFIRMED,
           "test_partial_ambiguous_and_overrisk_never_confirm_fill");
   FRMonth month;month.entries=1;month.winners=0;month.cash=0;
   FRBookCash(month,10,-0.2,-0.3,-0.1);FRBookClosed(month,9.4);
   FRCheck(MathAbs(month.cash-9.4)<1e-9 && month.winners==1,
           "test_monthly_cash_includes_commission_swap_fee");
   FRCheck(FRAdmit(1,180,0.01,0.01,0.01,100,200,0,1,false)==FR_DAILY &&
           FRAdmit(1,200,0.01,0.01,0.01,100,200,1,1,false)==FR_DAILY &&
           FRAdmit(1,200,0.01,0.01,0.01,100,200,1,0,false)==FR_OK,
           "test_daily_equity_and_strategy_loss_count_contracts");
   previous=FRCaseBar(600,99,101,97,100);current=FRCaseBar(900,100,100,96,96.5);
   FRCheck(FRPullback(previous,current,100,101,99,100,90,91,89,2,sig) &&
           sig.direction==-1 && MathAbs(sig.stop_anchor-101.2)<1e-9,
           "test_pullback_sell_is_mirrored");
   current.utc=1200;
   FRCheck(!FRPullback(previous,current,100,101,99,100,90,91,89,2,sig),
           "test_pullback_missing_bar_never_triggers");
   FRAssembler assembler;assembler.Reset(300,60);FRBar sealed={};bool complete=false;
   for(int i=0;i<5;i++) complete=assembler.Push(FRCaseBar(i*60,100,101,99,100),sealed);
   FRCheck(complete && sealed.utc==0,"test_complete_M1_group_publishes_at_close");
   assembler.Reset(300,60);
   assembler.Push(FRCaseBar(0,100,101,99,100),sealed);
   for(int i=2;i<5;i++) complete=assembler.Push(FRCaseBar(i*60,100,101,99,100),sealed);
   FRCheck(!complete,"test_missing_M1_group_never_publishes");
   session.Reset(420);
   for(int i=1;i<6;i++) session.Push(FRCaseBar(25200+i*300,100,102,98,100),2,sig);
   session.Push(FRCaseBar(27000,101,104,101,103),2,sig);
   FRCheck(!session.Push(FRCaseBar(27300,103,104,101.9,103),2,sig),
           "test_incomplete_opening_range_never_trades");
   session.Reset(420);
   for(int i=0;i<6;i++) session.Push(FRCaseBar(25200+i*300,100,102,98,100),2,sig);
   session.Push(FRCaseBar(27000,99,99,96,97),2,sig);
   FRCheck(session.Push(FRCaseBar(27300,97,98.1,96,97),2,sig) && sig.direction==-1,
           "test_session_sell_retest_is_mirrored");
   FRCheck(!session.Push(FRCaseBar(27600,97,98.1,96,97),2,sig),
           "test_session_consumed_setup_never_reenters");
   series.Reset();for(int i=0;i<14;i++) series.Push(FRCaseBar(i*900,100,101,99,100));
   FRCheck(series.rsi==50 && series.atr==2,"test_flat_rolling_RSI_and_mean_TR_literals");
   series.Reset();for(int i=0;i<14;i++) series.Push(FRCaseBar(i*900,100+i,101+i,99+i,100+i));
   FRCheck(series.rsi==100,"test_all_gain_RSI_is_100");
   FRSummary stats;FRSummaryReset(stats);month.entries=20;month.winners=1;month.cash=10;
   FRAccumulate(stats,month,true);month.entries=0;month.cash=0;FRAccumulate(stats,month,true);
   month.entries=100;month.cash=-1;FRAccumulate(stats,month,false);
   FRCheck(stats.full==2 && stats.positive==1 && stats.entries==20 && stats.worst==0 && stats.total==9 &&
           !FRWindowFull(100,200,150,300) && FRWindowFull(200,300,150,300),
           "test_zero_month_counts_and_partial_month_excludes_frequency");
   session.Reset(420);
   for(int i=0;i<6;i++) session.Observe(FRCaseBar(25200+i*300,100,102,98,100),2,false,sig);
   session.Observe(FRCaseBar(27000,101,104,101,103),2,false,sig);
   FRCheck(!session.Observe(FRCaseBar(27300,103,104,101.9,103),2,true,sig),
           "test_warmup_cannot_reconstruct_session_eligibility");
   FRCheck(!FRReportReady(true,0,0) && !FRReportReady(false,1,0) && FRReportReady(false,0,0),
           "test_unresolved_request_invalidates_terminal_report");
   FRCheck(FRObservedScope(100,200,110,350)==FR_PARTIAL_MONTH &&
           FRObservedScope(200,300,110,350)==FR_FULL_MONTH &&
           FRObservedScope(400,500,110,350)==FR_UNOBSERVED_MONTH,
           "test_observed_month_scope_rejects_unobserved_zero_denominator");
}
#endif
