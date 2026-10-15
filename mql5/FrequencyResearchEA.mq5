#property strict
#property version "1.000"
#property description "Research only: Pullback / UTC Session Breakout / C22 tuned. Refuses live charts."
#include "FrequencyResearchCore.mqh"

enum FRStrategy { TREND_PULLBACK=0, SESSION_BREAKOUT=1, C22_TUNED=2 };
enum FRCostView { BASE_SWAP=0, COST_SURCHARGE_STRESS=1 };
input FRStrategy Strategy=TREND_PULLBACK;
input FRCostView CostView=BASE_SWAP;
input bool CostsAttested=false;
input bool TesterEconomicsAttested=false;
input string CostSource="";
input double BaseCommissionUSDPerLotRoundTrip=-1;
input double SwapLongPoints=0;
input double SwapShortPoints=0;
input int SwapTripleWeekday=3;
input bool ServerOffsetAttested=false;
input int ServerUtcOffsetMinutes=0;
input datetime EvaluationFromUTC=D'2024.09.01 00:00:00';
input datetime EvaluationToUTC=D'2026.10.06 00:00:00';
input int Session1UtcMinute=420;
input int Session2UtcMinute=780;
input string ReportPrefix="frequency_research";

// Costs are applied by Tester, never deducted twice by this EA.
const double FR_FIXED_LOT=0.01;
const long FR_MAGIC=221014;
FRAssembler g_m5,g_m15,g_h1,g_h4;
FRSeries g_fast,g_c22,g_hour;
FRMacro g_macro;
FRSession g_sessions[2];
long g_last_minute=-1,g_day=-1;
int g_losses=0,g_send_code=0;
double g_day_equity=0,g_start_balance=0,g_peak=0,g_max_dd=0,g_risk_budget=0;
bool g_pending=false,g_halt=false,g_containment_sent=false;
ulong g_position_id=0,g_ticket=0;
double g_initial_stop=0;
string g_halt_reason="",g_report_prefix="";
int g_events=INVALID_HANDLE;
long g_first_tick=0,g_last_tick=0;

long FRUtc(const long server_epoch) { return server_epoch-(long)ServerUtcOffsetMinutes*60; }
double FRCommission() { return BaseCommissionUSDPerLotRoundTrip+(CostView==COST_SURCHARGE_STRESS ? 40.0 : 0.0); }
void FREvent(const long utc,const string kind,const string reason,const double value=0)
{
   if(g_events!=INVALID_HANDLE) FileWrite(g_events,utc,kind,reason,value);
}
void FRHalt(const string reason)
{ g_halt=true;g_halt_reason=reason;FREvent(g_last_tick,"HALT",reason); }

bool FRCostSpec()
{
   return MathIsValidNumber(BaseCommissionUSDPerLotRoundTrip) && BaseCommissionUSDPerLotRoundTrip>=0 &&
      MathIsValidNumber(SwapLongPoints) && MathIsValidNumber(SwapShortPoints) &&
      SymbolInfoInteger(_Symbol,SYMBOL_SWAP_MODE)==SYMBOL_SWAP_MODE_POINTS &&
      MathAbs(SymbolInfoDouble(_Symbol,SYMBOL_SWAP_LONG)-SwapLongPoints)<1e-8 &&
      MathAbs(SymbolInfoDouble(_Symbol,SYMBOL_SWAP_SHORT)-SwapShortPoints)<1e-8 &&
      SymbolInfoInteger(_Symbol,SYMBOL_SWAP_ROLLOVER3DAYS)==SwapTripleWeekday;
}

// Returns one owned position; never changes an unowned ticket.
int FROwned(ulong &ticket)
{
   ticket=0;int owned=0;
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong candidate=PositionGetTicket(i);
      if(candidate==0) { FRHalt("position_inventory_failed");return -1; }
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol || PositionGetInteger(POSITION_MAGIC)!=FR_MAGIC)
      { FRHalt("foreign_exposure");return -1; }
      ticket=candidate;owned++;
   }
   if(owned>1) { FRHalt("multiple_positions");return -1; }
   return owned;
}

bool FRProfit(const int direction,const double entry,const double stop,double &loss)
{
   double pnl=0;
   if(!OrderCalcProfit(direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,_Symbol,FR_FIXED_LOT,entry,stop,pnl) || pnl>=0)
      return false;
   loss=-pnl+FRCommission()*FR_FIXED_LOT;return MathIsValidNumber(loss);
}

bool FRFilling(ENUM_ORDER_TYPE_FILLING &mode)
{
   long flags=SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((flags&SYMBOL_FILLING_FOK)!=0) { mode=ORDER_FILLING_FOK;return true; }
   if((flags&SYMBOL_FILLING_IOC)!=0) { mode=ORDER_FILLING_IOC;return true; }
   return false;
}

bool FRStops(const FRPlan &plan,const MqlTick &tick)
{
   double minimum=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double mark=plan.direction==1 ? tick.bid : tick.ask;
   return plan.direction*(mark-plan.stop)>0 && plan.direction*(plan.target-mark)>0 &&
      MathAbs(mark-plan.stop)>=minimum && MathAbs(plan.target-mark)>=minimum;
}

void FRContain(const ulong ticket,const MqlTick &tick)
{
   if(g_containment_sent || OrdersTotal()!=0 || !PositionSelectByTicket(ticket)) return;
   if(PositionGetInteger(POSITION_MAGIC)!=FR_MAGIC || PositionGetString(POSITION_SYMBOL)!=_Symbol) return;
   MqlTradeRequest request={};MqlTradeResult result={};
   request.action=TRADE_ACTION_DEAL;request.position=ticket;request.symbol=_Symbol;request.magic=FR_MAGIC;
   request.volume=PositionGetDouble(POSITION_VOLUME);
   request.type=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   request.price=request.type==ORDER_TYPE_BUY ? tick.ask : tick.bid;
   if(!FRFilling(request.type_filling)) return;
   request.comment="FR incident close";request.deviation=0;
   g_containment_sent=true; // Persist in run before send; no blind repeat after ambiguous result.
   bool sent=OrderSend(request,result);
   FREvent(FRUtc(tick.time),"CONTAIN_REQUEST",sent ? IntegerToString((int)result.retcode) : "send_unknown",request.volume);
}

bool FRLedgerClosed(const ulong id,double &net,double &charges,long &exit_utc)
{
   if(id==0 || !HistorySelect(0,TimeCurrent()+60)) return false;
   double signed_volume=0;net=0;charges=0;exit_utc=0;bool opening=false,closing=false;
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong deal=HistoryDealGetTicket(i);
      if((ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID)!=id) continue;
      long type=HistoryDealGetInteger(deal,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      signed_volume+=HistoryDealGetDouble(deal,DEAL_VOLUME)*(type==DEAL_TYPE_BUY ? 1 : -1);
      net+=HistoryDealGetDouble(deal,DEAL_PROFIT)+HistoryDealGetDouble(deal,DEAL_COMMISSION)+
           HistoryDealGetDouble(deal,DEAL_SWAP)+HistoryDealGetDouble(deal,DEAL_FEE);
      charges-=HistoryDealGetDouble(deal,DEAL_COMMISSION)+HistoryDealGetDouble(deal,DEAL_FEE);
      long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry==DEAL_ENTRY_IN) opening=true;
      if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
      { closing=true;exit_utc=(long)MathMax(exit_utc,FRUtc(HistoryDealGetInteger(deal,DEAL_TIME))); }
      if(entry==DEAL_ENTRY_INOUT) { FRHalt("reversal_unsupported");return false; }
   }
   return opening && closing && MathAbs(signed_volume)<1e-8;
}

void FRManage(const MqlTick &tick)
{
   ulong ticket=0;int owned=FROwned(ticket);
   if(owned<0) return;
   if(owned==0)
   {
      if(g_position_id!=0)
      {
         double net=0,charges=0;long exit_utc=0;
         if(!FRLedgerClosed(g_position_id,net,charges,exit_utc)) { FRHalt("closing_ledger_incomplete");return; }
         if(MathAbs(charges-FRCommission()*FR_FIXED_LOT)>1e-6) FRHalt("tester_commission_mismatch");
         if(net<0 && exit_utc-exit_utc%86400==g_day) g_losses++;
         FREvent(exit_utc,"CLOSED",g_halt ? g_halt_reason : "ledger_confirmed",net);
         g_position_id=0;g_ticket=0;g_pending=false;
      }
      return;
   }
   if(!PositionSelectByTicket(ticket)) { FRHalt("position_selection_failed");return; }
   ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
   if(g_position_id!=0 && g_position_id!=id) { FRHalt("position_identifier_changed");return; }
   g_position_id=id;g_ticket=ticket;
   int direction=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1;
   double entry=PositionGetDouble(POSITION_PRICE_OPEN),stop=PositionGetDouble(POSITION_SL),loss=0;
   if(g_pending)
   {
      bool valid=stop>0 && PositionGetDouble(POSITION_TP)>0 && FRProfit(direction,entry,stop,loss);
      int fill=FRFillState(g_send_code,true,PositionGetDouble(POSITION_VOLUME),valid ? loss : -1,g_risk_budget);
      if(fill!=FR_CONFIRMED)
      { FRHalt("filled_contract_violation");FRContain(ticket,tick);return; }
      g_pending=false;g_initial_stop=stop;
      FREvent(FRUtc(tick.time),"FILLED","broker_position_confirmed",entry);
   }
   if(g_halt) { if(g_halt_reason=="filled_contract_violation") FRContain(ticket,tick);return; }
   double initial_distance=MathAbs(entry-g_initial_stop),mark=direction==1 ? tick.bid : tick.ask;
   if(initial_distance<=0 || direction*(mark-entry)<initial_distance) return;
   double grid=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double break_even=FRGrid(entry,grid,direction);
   if(direction*(break_even-stop)<=0) return;
   double minimum=(double)MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),
      SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))*SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(direction*(mark-break_even)<=minimum) return;
   MqlTradeRequest request={};MqlTradeResult result={};
   request.action=TRADE_ACTION_SLTP;request.position=ticket;request.symbol=_Symbol;request.magic=FR_MAGIC;
   request.sl=break_even;request.tp=PositionGetDouble(POSITION_TP);
   bool sent=OrderSend(request,result);
   FREvent(FRUtc(tick.time),"BE_REQUEST",sent ? IntegerToString((int)result.retcode) : "send_unknown",break_even);
}

void FREnter(const FRSignal &signal,const MqlTick &tick)
{
   long utc=FRUtc(tick.time);
   FREvent(utc,"SIGNAL",EnumToString(Strategy),signal.direction);
   if(utc<(long)EvaluationFromUTC || utc>=(long)EvaluationToUTC || signal.decision>utc || utc-signal.decision>90) return;
   if(g_halt || g_pending) { FREvent(utc,"BLOCKED","halt_or_pending");return; }
   if(!FRCostSpec()) { FRHalt("cost_spec_changed");return; }
   FRPlan plan;
   if(!FRPrepare(signal,Strategy==C22_TUNED,tick.bid,tick.ask,SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE),plan))
   { FREvent(utc,"BLOCKED","invalid_geometry");return; }
   double loss=0,equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(!FRProfit(plan.direction,plan.entry,plan.stop,loss)) { FREvent(utc,"BLOCKED","profit_calc_failed");return; }
   int admitted=FRAdmit(loss,equity,FR_FIXED_LOT,SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),
      SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP),SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),
      g_day_equity,g_losses,Strategy==C22_TUNED ? 0 : 1,PositionsTotal()!=0 || OrdersTotal()!=0);
   if(admitted!=FR_OK) { FREvent(utc,"BLOCKED",IntegerToString(admitted),loss);return; }
   double margin=0;
   ENUM_ORDER_TYPE side=plan.direction==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(side,_Symbol,FR_FIXED_LOT,plan.entry,margin) || margin+FRCommission()*FR_FIXED_LOT>=AccountInfoDouble(ACCOUNT_MARGIN_FREE))
   { FREvent(utc,"BLOCKED","margin");return; }
   if(!FRStops(plan,tick)) { FREvent(utc,"BLOCKED","broker_stops");return; }
   MqlTradeRequest request={};MqlTradeResult result={};MqlTradeCheckResult check={};
   request.action=TRADE_ACTION_DEAL;request.symbol=_Symbol;request.magic=FR_MAGIC;
   request.type=side;request.volume=FR_FIXED_LOT;request.price=plan.entry;request.sl=plan.stop;request.tp=plan.target;
   request.deviation=0;request.comment="FR research only";
   if(!FRFilling(request.type_filling) || !OrderCheck(request,check))
   { FREvent(utc,"BLOCKED","order_check");return; }
   g_pending=true;g_risk_budget=equity*0.1;g_send_code=0;
   bool sent=OrderSend(request,result);
   if(sent) g_send_code=(int)result.retcode;
   if(result.deal!=0 && HistoryDealSelect(result.deal))
      g_position_id=(ulong)HistoryDealGetInteger(result.deal,DEAL_POSITION_ID);
   int outcome=FRFillState(g_send_code,false,0,0,g_risk_budget);
   if(outcome==FR_REJECTED) g_pending=false;
   FREvent(utc,"SEND_RESPONSE",IntegerToString(g_send_code));
   FRManage(tick);
   if(g_pending && g_position_id==0 && g_send_code!=10009) FRHalt("ambiguous_market_request");
}

void FRFeed(const FRBar &minute,const MqlTick &tick,const bool evaluate)
{
   FRBar h1,m5,m15,h4;FRSignal signal={};
   if(g_h1.Push(minute,h1)) g_hour.Push(h1);
   if(g_m5.Push(minute,m5))
   {
      g_fast.Push(m5);
      bool found=false;
      if(Strategy==TREND_PULLBACK && g_fast.count>=54 && g_hour.count>=54 &&
         m5.utc+300<g_hour.bars[0].utc+7200)
         found=FRPullback(g_fast.bars[1],g_fast.bars[0],g_fast.ema20[1],g_fast.ema50[1],
            g_fast.ema20[0],g_fast.ema50[0],g_hour.ema50[0],g_hour.ema50[4],g_hour.bars[0].close,g_fast.atr,signal);
      if(Strategy==SESSION_BREAKOUT)
         for(int i=0;i<2;i++)
         { FRSignal candidate;if(g_sessions[i].Observe(m5,g_fast.atr,evaluate,candidate)) { signal=candidate;found=true; } }
      if(evaluate && found) FREnter(signal,tick);
   }
   if(g_m15.Push(minute,m15))
   {
      g_c22.Push(m15);
      if(g_h4.Push(m15,h4))
      g_macro.Push(h4);
      bool valid=g_macro.Ready(m15.utc+900);
      if(Strategy==C22_TUNED && FRC22(g_c22,g_macro.value,valid,signal) && evaluate) FREnter(signal,tick);
   }
}

int OnInit()
{
   bool utc=ServerOffsetAttested && ServerUtcOffsetMinutes>=-840 && ServerUtcOffsetMinutes<=840 &&
      ServerUtcOffsetMinutes%15==0;
   if(!FRTesterAllowed((bool)MQLInfoInteger(MQL_TESTER),AccountInfoString(ACCOUNT_CURRENCY)=="USD",
      CostsAttested && TesterEconomicsAttested && CostSource!="" && FRCostSpec(),utc))
   { Print("NO_GO tester/USD/cost/swap/UTC attestation required");return INIT_PARAMETERS_INCORRECT; }
   if((long)EvaluationFromUTC<=0 || (long)EvaluationFromUTC%60!=0 || (long)EvaluationToUTC%60!=0 || EvaluationFromUTC>=EvaluationToUTC || Session1UtcMinute<0 || Session2UtcMinute<0 ||
      Session1UtcMinute>1260 || Session2UtcMinute>1260 || MathAbs(Session1UtcMinute-Session2UtcMinute)<180 ||
      Session1UtcMinute%5!=0 || Session2UtcMinute%5!=0 || ReportPrefix=="" ||
      StringFind(ReportPrefix,"/")>=0 || StringFind(ReportPrefix,"\\")>=0)
      return INIT_PARAMETERS_INCORRECT;
   g_m5.Reset(300,60);g_m15.Reset(900,60);g_h1.Reset(3600,60);g_h4.Reset(14400,900);
   g_fast.Reset();g_c22.Reset();g_hour.Reset();g_macro.Reset();
   g_sessions[0].Reset(Session1UtcMinute);g_sessions[1].Reset(Session2UtcMinute);
   g_start_balance=AccountInfoDouble(ACCOUNT_BALANCE);g_peak=g_start_balance;
   g_report_prefix=ReportPrefix+"_"+EnumToString(Strategy)+"_"+EnumToString(CostView)+"_"+
      StringFormat("%I64u",GetMicrosecondCount());
   g_events=FileOpen(g_report_prefix+"_events.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(g_events==INVALID_HANDLE) return INIT_FAILED;
   FileWrite(g_events,"utc_epoch","kind","reason","value");
   Print("COST_INCONCLUSIVE native points swap; view=",EnumToString(CostView),
         "; expected instant commission+fee USD/lot/roundtrip=",FRCommission(),"; source=",CostSource);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.bid<=0 || tick.ask<tick.bid || TimeCurrent()-tick.time>5) return;
   long utc=FRUtc(tick.time);g_last_tick=utc;if(g_first_tick==0) g_first_tick=utc;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_peak=MathMax(g_peak,equity);if(g_peak>0) g_max_dd=MathMax(g_max_dd,100*(g_peak-equity)/g_peak);
   long day=utc-utc%86400;
   if(day!=g_day) { g_day=day;g_day_equity=equity;g_losses=0; }
   FRManage(tick);
   long through=(long)tick.time-(long)tick.time%60-60;
   long from=g_last_minute<0 ? through-70*86400 : g_last_minute+60;
   if(from>through) return;
   MqlRates rates[];ArraySetAsSeries(rates,false);
   int count=CopyRates(_Symbol,PERIOD_M1,(datetime)from,(datetime)through,rates);
   if(count<0) { FREvent(utc,"BLOCKED","M1_history_unavailable");return; }
   for(int i=0;i<count;i++)
   {
      if((long)rates[i].time<=g_last_minute || (long)rates[i].time>through) continue;
      FRBar b;b.utc=FRUtc((long)rates[i].time);b.open=rates[i].open;b.high=rates[i].high;
      b.low=rates[i].low;b.close=rates[i].close;
      if(!FRBarValid(b)) { FRHalt("invalid_M1_bar");return; }
      g_last_minute=(long)rates[i].time;
      FRFeed(b,tick,b.utc+60==utc-utc%60);
   }
}

struct FRPositionLedger
{
   ulong id;
   long entry_utc;
   double signed_volume,net,charges,opening_volume;
   bool opened,closed;
};
int FRMonthKey(const long utc)
{ MqlDateTime t;TimeToStruct((datetime)utc,t);return t.year*12+t.mon-1; }
string FRMonthLabel(const int key)
{ return IntegerToString(key/12)+"-"+StringFormat("%02d",key%12+1); }
long FRMonthStart(const int key)
{ MqlDateTime t={};t.year=key/12;t.mon=key%12+1;t.day=1;return (long)StructToTime(t); }

double OnTester()
{
   // Run after Tester's end-of-sample liquidation; book actual native deals once.
   if(!HistorySelect(0,TimeCurrent()+86400)) { FRHalt("report_history_unavailable");return -1e100; }
   int first=FRMonthKey((long)EvaluationFromUTC),last=FRMonthKey((long)EvaluationToUTC-1),n=last-first+1;
   FRMonth months[];ArrayResize(months,n);for(int i=0;i<n;i++) { months[i].entries=0;months[i].winners=0;months[i].cash=0; }
   FRPositionLedger positions[];
   int ledger=FileOpen(g_report_prefix+"_deals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(ledger==INVALID_HANDLE) { FRHalt("report_open_failed");return -1e100; }
   FileWrite(ledger,"utc_epoch","deal","position_id","entry","type","volume","price","profit","commission","swap","fee");
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong deal=HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(deal,DEAL_MAGIC)!=FR_MAGIC || HistoryDealGetString(deal,DEAL_SYMBOL)!=_Symbol) continue;
      long type=HistoryDealGetInteger(deal,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) { FRHalt("separate_charge_unsupported");continue; }
      long utc=FRUtc(HistoryDealGetInteger(deal,DEAL_TIME));
      ulong id=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      double volume=HistoryDealGetDouble(deal,DEAL_VOLUME),profit=HistoryDealGetDouble(deal,DEAL_PROFIT),
         commission=HistoryDealGetDouble(deal,DEAL_COMMISSION),swap=HistoryDealGetDouble(deal,DEAL_SWAP),fee=HistoryDealGetDouble(deal,DEAL_FEE);
      int entry=(int)HistoryDealGetInteger(deal,DEAL_ENTRY),index=FRMonthKey(utc)-first;
      FileWrite(ledger,utc,deal,id,entry,type,volume,HistoryDealGetDouble(deal,DEAL_PRICE),profit,commission,swap,fee);
      if(index>=0 && index<n) FRBookCash(months[index],profit,commission,swap,fee);
      int p=-1;for(int j=0;j<ArraySize(positions);j++) if(positions[j].id==id) { p=j;break; }
      if(p<0) { p=ArraySize(positions);ArrayResize(positions,p+1);ZeroMemory(positions[p]);positions[p].id=id; }
      positions[p].signed_volume+=volume*(type==DEAL_TYPE_BUY ? 1 : -1);
      positions[p].net+=profit+commission+swap+fee;positions[p].charges-=commission+fee;
      if(entry==DEAL_ENTRY_IN)
      {
         if(!positions[p].opened)
         { positions[p].opened=true;positions[p].entry_utc=utc;if(index>=0 && index<n) months[index].entries++; }
         positions[p].opening_volume+=volume;
      }
      else if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY) positions[p].closed=true;
      else FRHalt("reversal_unsupported");
   }
   FileClose(ledger);
   for(int p=0;p<ArraySize(positions);p++)
   {
      int index=FRMonthKey(positions[p].entry_utc)-first;
      if(!positions[p].opened || !positions[p].closed || MathAbs(positions[p].signed_volume)>1e-8 ||
         MathAbs(positions[p].opening_volume-FR_FIXED_LOT)>1e-8) { FRHalt("report_position_incomplete");continue; }
      if(MathAbs(positions[p].charges-FRCommission()*FR_FIXED_LOT)>1e-6) FRHalt("tester_commission_mismatch");
      if(index>=0 && index<n) FRBookClosed(months[index],positions[p].net);
   }
   int output=FileOpen(g_report_prefix+"_months.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(output==INVALID_HANDLE) { FRHalt("report_open_failed");return -1e100; }
   FileWrite(output,"month_utc","requested_full","observed_scope","included_full_month","entries","winning_positions_by_entry_month","native_net_cash_by_deal_month");
   double full_nets[];FRSummary stats;FRSummaryReset(stats);
   for(int i=0;i<n;i++)
   {
      int key=first+i;bool requested_full=FRWindowFull(FRMonthStart(key),FRMonthStart(key+1),(long)EvaluationFromUTC,(long)EvaluationToUTC);
      int observed=FRObservedScope(FRMonthStart(key),FRMonthStart(key+1),g_first_tick,g_last_tick);
      bool complete=requested_full && observed==FR_FULL_MONTH;
      FileWrite(output,FRMonthLabel(key),requested_full,observed,complete,months[i].entries,months[i].winners,months[i].cash);
      if(complete) { ArrayResize(full_nets,stats.full+1);full_nets[stats.full]=months[i].cash; }
      FRAccumulate(stats,months[i],complete);
   }
   FileClose(output);ArraySort(full_nets);
   double final_equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_peak>0) g_max_dd=MathMax(g_max_dd,100*(g_peak-final_equity)/g_peak);
   if(MathAbs(stats.total-(AccountInfoDouble(ACCOUNT_BALANCE)-g_start_balance))>1e-6)
      FRHalt("native_cash_ledger_mismatch");
   if(!FRReportReady(g_pending,PositionsTotal(),OrdersTotal())) FRHalt("end_execution_unresolved");
   double median=stats.full==0 ? 0 : (stats.full%2!=0 ? full_nets[stats.full/2] : (full_nets[stats.full/2-1]+full_nets[stats.full/2])/2);
   output=FileOpen(g_report_prefix+"_summary.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(output==INVALID_HANDLE) { FRHalt("report_open_failed");return -1e100; }
   FileWrite(output,"status","cost_view","strategy","cost_source","first_tick_utc","last_tick_utc","requested_from_utc","requested_to_utc","net_usd","tick_equity_dd_pct","full_observed_months_in_requested_window","mean_entries_full_month","positive_month_ratio","median_month_net","worst_month_net","halt_reason");
   FileWrite(output,g_halt ? "INVALID" : "COST_INCONCLUSIVE",EnumToString(CostView),EnumToString(Strategy),CostSource,
      g_first_tick,g_last_tick,(long)EvaluationFromUTC,(long)EvaluationToUTC,stats.total,g_max_dd,stats.full,
      stats.full>0 ? (double)stats.entries/stats.full : 0,stats.full>0 ? (double)stats.positive/stats.full : 0,median,stats.worst,g_halt_reason);
   FileClose(output);
   Print("Research report: ",g_report_prefix,"; data coverage/broker parity UNVERIFIED; no qualification.");
   return g_halt || stats.full==0 ? -1e100 : median;
}

void OnDeinit(const int reason)
{ if(g_events!=INVALID_HANDLE) { FileFlush(g_events);FileClose(g_events);g_events=INVALID_HANDLE; } }
