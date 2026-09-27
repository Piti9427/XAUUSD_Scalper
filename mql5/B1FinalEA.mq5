#property strict
#property version "1.100"
#property description "B1-FINAL execution EA. Order execution is Strategy Tester only in this release."
#include "B1FinalEngine.mqh"

input long       ExpectedLogin=0;
input string     ExpectedServer="";
input string     TargetSymbol="XAUUSDm";
input long       Magic=26092701;
input B1ExitMode ExitMode=B1_EXIT_FIXED;
input double     CommissionPerLot=0.0;     // expected entry commission, account currency per lot
input double     ExitFeePerLot=0.0;        // exit-fee reserve, account currency per lot
input double     AdmissionReserveR=0.0;
input int        ModifyDelayMs=0;
input int        ReconcileTimeoutSec=30;
input int        BrokerUtcOffsetSec=0;
input int        CloseRetrySec=10;
input int        DeviationPoints=50;
input bool       BootstrapState=false;    // explicit operator action: create a new HWM from current equity
input string     AcknowledgeIncident="";
input datetime   SeedAnchor=D'2026.05.07 00:00';

string Version()
{
   if(ExitMode==B1_EXIT_COST_BE) return "B1-FINAL-v1.1";
   if(ExitMode==B1_EXIT_ENTRY_BE) return "B1-FINAL-v1.1-CONTROL-ENTRY-BE";
   return "B1-FINAL-v1";
}
string Code()
{
   if(ExitMode==B1_EXIT_COST_BE) return "B1F11";
   if(ExitMode==B1_EXIT_ENTRY_BE) return "B1F11E";
   return "B1F1";
}

int B1MapRetcode(const uint code)
{
   switch(code)
   {
      case TRADE_RETCODE_DONE: return B1_SEND_DONE;
      case TRADE_RETCODE_DONE_PARTIAL: return B1_SEND_PARTIAL;
      case TRADE_RETCODE_REQUOTE: case TRADE_RETCODE_REJECT: case TRADE_RETCODE_CANCEL:
      case TRADE_RETCODE_INVALID: case TRADE_RETCODE_INVALID_VOLUME: case TRADE_RETCODE_INVALID_PRICE:
      case TRADE_RETCODE_INVALID_STOPS: case TRADE_RETCODE_TRADE_DISABLED: case TRADE_RETCODE_MARKET_CLOSED:
      case TRADE_RETCODE_NO_MONEY: case TRADE_RETCODE_PRICE_CHANGED: case TRADE_RETCODE_PRICE_OFF:
      case TRADE_RETCODE_INVALID_EXPIRATION: case TRADE_RETCODE_ORDER_CHANGED: case TRADE_RETCODE_TOO_MANY_REQUESTS:
      case TRADE_RETCODE_NO_CHANGES: case TRADE_RETCODE_SERVER_DISABLES_AT: case TRADE_RETCODE_CLIENT_DISABLES_AT:
      case TRADE_RETCODE_LOCKED: case TRADE_RETCODE_FROZEN: case TRADE_RETCODE_INVALID_FILL:
      case TRADE_RETCODE_ONLY_REAL: case TRADE_RETCODE_LIMIT_ORDERS: case TRADE_RETCODE_LIMIT_VOLUME:
      case TRADE_RETCODE_INVALID_ORDER: case TRADE_RETCODE_POSITION_CLOSED: case TRADE_RETCODE_INVALID_CLOSE_VOLUME:
      case TRADE_RETCODE_LIMIT_POSITIONS:
         return B1_SEND_REJECTED;
   }
   // Placed, timeout, connection loss, generic error or no retcode: outcome unknown.
   return B1_SEND_UNKNOWN;
}

class CB1MtBroker : public CB1Broker
{
public:
   string sym;
   long   magic;
   string lock_name;
   double lock_token;

   ENUM_ORDER_TYPE_FILLING Filling()
   {
      long mode=SymbolInfoInteger(sym,SYMBOL_FILLING_MODE);
      if((mode&SYMBOL_FILLING_FOK)!=0) return ORDER_FILLING_FOK;
      if((mode&SYMBOL_FILLING_IOC)!=0) return ORDER_FILLING_IOC;
      return ORDER_FILLING_RETURN;
   }
   virtual bool Quote(double &bid,double &ask,long &msc)
   {
      MqlTick t;
      if(!SymbolInfoTick(sym,t)) return false;
      bid=t.bid; ask=t.ask; msc=t.time_msc;
      return true;
   }
   virtual double Equity() { return AccountInfoDouble(ACCOUNT_EQUITY); }
   virtual double MarginFree() { return AccountInfoDouble(ACCOUNT_MARGIN_FREE); }
   virtual bool Spec(B1Spec &s)
   {
      s.vol_min=SymbolInfoDouble(sym,SYMBOL_VOLUME_MIN); s.vol_step=SymbolInfoDouble(sym,SYMBOL_VOLUME_STEP);
      s.vol_max=SymbolInfoDouble(sym,SYMBOL_VOLUME_MAX); s.tick_size=SymbolInfoDouble(sym,SYMBOL_TRADE_TICK_SIZE);
      s.point=SymbolInfoDouble(sym,SYMBOL_POINT);
      s.stops_level=(int)SymbolInfoInteger(sym,SYMBOL_TRADE_STOPS_LEVEL);
      s.freeze_level=(int)SymbolInfoInteger(sym,SYMBOL_TRADE_FREEZE_LEVEL);
      s.trade_full=SymbolInfoInteger(sym,SYMBOL_TRADE_MODE)==SYMBOL_TRADE_MODE_FULL;
      return s.vol_min>0 && s.vol_step>0 && s.vol_max>=s.vol_min && s.tick_size>0 && s.point>0;
   }
   virtual bool CalcProfit(const int dir,const double v,const double o,const double c,double &p)
   { return OrderCalcProfit(dir>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,sym,v,o,c,p); }
   virtual bool CalcMargin(const int dir,const double v,const double price,double &m)
   { return OrderCalcMargin(dir>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,sym,v,price,m); }
   void Fill(MqlTradeRequest &r,const int dir,const double v,const double price,const double sl,const double tp,const string c)
   {
      ZeroMemory(r);
      r.action=TRADE_ACTION_DEAL; r.symbol=sym; r.volume=v; r.type=dir>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      r.price=price; r.sl=sl; r.tp=tp; r.deviation=DeviationPoints; r.magic=magic; r.comment=c;
      r.type_filling=Filling();
   }
   virtual bool CheckOrder(const int dir,const double v,const double price,const double sl,const double tp,string &reason)
   {
      MqlTradeRequest r; MqlTradeCheckResult res; ZeroMemory(res);
      Fill(r,dir,v,price,sl,tp,"check");
      bool ok=OrderCheck(r,res);
      reason=IntegerToString(res.retcode);
      return ok && res.retcode==0;
   }
   virtual int OwnedPositions(B1Position &out[])
   {
      ArrayResize(out,0);
      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong t=PositionGetTicket(i);
         if(t==0 || PositionGetString(POSITION_SYMBOL)!=sym || PositionGetInteger(POSITION_MAGIC)!=magic) continue;
         int n=ArraySize(out); ArrayResize(out,n+1);
         out[n].ticket=t;
         out[n].direction=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1;
         out[n].volume=PositionGetDouble(POSITION_VOLUME); out[n].price_open=PositionGetDouble(POSITION_PRICE_OPEN);
         out[n].sl=PositionGetDouble(POSITION_SL); out[n].tp=PositionGetDouble(POSITION_TP);
         out[n].swap=PositionGetDouble(POSITION_SWAP); out[n].comment=PositionGetString(POSITION_COMMENT);
      }
      return ArraySize(out);
   }
   virtual int ForeignExposure()
   {
      int n=0;
      for(int i=PositionsTotal()-1;i>=0;i--)
         if(PositionGetTicket(i)!=0 && PositionGetString(POSITION_SYMBOL)==sym && PositionGetInteger(POSITION_MAGIC)!=magic) n++;
      for(int i=OrdersTotal()-1;i>=0;i--)
         if(OrderGetTicket(i)!=0 && OrderGetString(ORDER_SYMBOL)==sym && OrderGetInteger(ORDER_MAGIC)!=magic) n++;
      return n;
   }
   virtual int OwnedPendingOrders(const string c)
   {
      int n=0;
      for(int i=OrdersTotal()-1;i>=0;i--)
         if(OrderGetTicket(i)!=0 && OrderGetString(ORDER_SYMBOL)==sym && OrderGetInteger(ORDER_MAGIC)==magic &&
            (c=="" || OrderGetString(ORDER_COMMENT)==c)) n++;
      return n;
   }
   virtual int CancelOwnedOrders(const string c)
   {
      int result=B1_SEND_DONE;
      for(int i=OrdersTotal()-1;i>=0;i--)
      {
         ulong t=OrderGetTicket(i);
         if(t==0 || OrderGetString(ORDER_SYMBOL)!=sym || OrderGetInteger(ORDER_MAGIC)!=magic ||
            (c!="" && OrderGetString(ORDER_COMMENT)!=c)) continue;
         MqlTradeRequest r; ZeroMemory(r);
         r.action=TRADE_ACTION_REMOVE; r.order=t;
         ulong ignored=0;
         int one=Send(r,ignored);
         if(one!=B1_SEND_DONE) result=one;
      }
      return result;
   }
   virtual bool FindFilledPosition(const string c,const ulong order,B1Position &filled)
   {
      if(!HistorySelect(0,TimeCurrent()+86400)) return false;
      ulong position=0;
      for(int i=HistoryDealsTotal()-1;i>=0 && position==0;i--)
      {
         ulong d=HistoryDealGetTicket(i);
         if(d==0 || HistoryDealGetString(d,DEAL_SYMBOL)!=sym || HistoryDealGetInteger(d,DEAL_MAGIC)!=magic) continue;
         if(HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_IN) continue;
         if(HistoryDealGetString(d,DEAL_COMMENT)==c || (order!=0 && (ulong)HistoryDealGetInteger(d,DEAL_ORDER)==order))
            position=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
      }
      if(position==0 || !HistorySelectByPosition(position)) return false;
      double volume=0.0,notional=0.0;
      filled.ticket=position; filled.swap=0.0; filled.comment=c; filled.sl=0.0; filled.tp=0.0; filled.direction=0;
      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong d=HistoryDealGetTicket(i);
         if(d==0 || HistoryDealGetInteger(d,DEAL_ENTRY)!=DEAL_ENTRY_IN) continue;
         double v=HistoryDealGetDouble(d,DEAL_VOLUME);
         volume+=v; notional+=v*HistoryDealGetDouble(d,DEAL_PRICE);
         filled.direction=HistoryDealGetInteger(d,DEAL_TYPE)==DEAL_TYPE_BUY ? 1 : -1;
         filled.sl=HistoryDealGetDouble(d,DEAL_SL); filled.tp=HistoryDealGetDouble(d,DEAL_TP);
      }
      if(volume<=0.0) return false;
      filled.volume=volume; filled.price_open=notional/volume;
      return true;
   }
   virtual bool EntryCommission(const ulong position,double &cost)
   {
      if(!HistorySelectByPosition(position)) return false;
      double sum=0.0; bool found=false;
      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong d=HistoryDealGetTicket(i);
         if(d!=0 && HistoryDealGetInteger(d,DEAL_ENTRY)==DEAL_ENTRY_IN) { sum+=HistoryDealGetDouble(d,DEAL_COMMISSION); found=true; }
      }
      cost=-sum;
      return found;
   }
   virtual bool CloseDeal(const ulong position,B1CloseDeal &deal)
   {
      if(!HistorySelectByPosition(position)) return false;
      double in=0.0,out=0.0;
      deal.profit=0; deal.commission=0; deal.swap=0; deal.volume=0; deal.price=0; deal.time_msc=0; deal.reason="";
      for(int i=0;i<HistoryDealsTotal();i++)
      {
         ulong d=HistoryDealGetTicket(i);
         if(d==0) continue;
         long entry=HistoryDealGetInteger(d,DEAL_ENTRY);
         double v=HistoryDealGetDouble(d,DEAL_VOLUME);
         if(entry==DEAL_ENTRY_IN) { in+=v; deal.swap+=HistoryDealGetDouble(d,DEAL_SWAP); continue; }
         out+=v;
         deal.profit+=HistoryDealGetDouble(d,DEAL_PROFIT); deal.commission+=HistoryDealGetDouble(d,DEAL_COMMISSION);
         deal.swap+=HistoryDealGetDouble(d,DEAL_SWAP); deal.price=HistoryDealGetDouble(d,DEAL_PRICE);
         deal.time_msc=HistoryDealGetInteger(d,DEAL_TIME_MSC);
         long reason=HistoryDealGetInteger(d,DEAL_REASON);
         deal.reason=reason==DEAL_REASON_SL ? "SL" : (reason==DEAL_REASON_TP ? "TP" : (reason==DEAL_REASON_SO ? "STOP_OUT" : "EXPERT"));
      }
      deal.volume=out;
      return out>0.0 && out>=in-1e-9;
   }
   int Send(MqlTradeRequest &r,ulong &order)
   {
      MqlTradeResult res; ZeroMemory(res);
      bool sent=OrderSend(r,res);
      order=res.order;
      if(!sent && res.retcode==0) return B1_SEND_UNKNOWN;
      return B1MapRetcode(res.retcode);
   }
   virtual int SendMarket(const int dir,const double v,const double price,const double sl,const double tp,const string c,ulong &order)
   { MqlTradeRequest r; Fill(r,dir,v,price,sl,tp,c); return Send(r,order); }
   virtual int ModifyStops(const ulong ticket,const double sl,const double tp)
   {
      MqlTradeRequest r; ZeroMemory(r);
      r.action=TRADE_ACTION_SLTP; r.symbol=sym; r.position=ticket; r.sl=sl; r.tp=tp; r.magic=magic;
      ulong ignored=0;
      return Send(r,ignored);
   }
   virtual int ClosePosition(const ulong ticket,const double v)
   {
      if(!PositionSelectByTicket(ticket) || PositionGetInteger(POSITION_MAGIC)!=magic) return B1_SEND_REJECTED;
      int dir=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? -1 : 1;
      MqlTick t; SymbolInfoTick(sym,t);
      MqlTradeRequest r; Fill(r,dir,v,dir>0 ? t.ask : t.bid,0,0,"B1 incident close");
      r.position=ticket;
      ulong ignored=0;
      return Send(r,ignored);
   }
   bool AcquireLock()
   {
      if(!GlobalVariableCheck(lock_name)) GlobalVariableTemp(lock_name);
      return GlobalVariableSetOnCondition(lock_name,lock_token,0.0);
   }
   virtual bool OwnerLock() { return GlobalVariableCheck(lock_name) && GlobalVariableGet(lock_name)==lock_token; }
};

string JsonEscape(string s)
{
   StringReplace(s,"\\","\\\\"); StringReplace(s,"\"","\\\"");
   return s;
}

// Engine numbers come from IntegerToString/DoubleToString: optional '-', digits, at most one '.'.
bool IsNumber(const string s)
{
   int n=StringLen(s), digits=0, dots=0;
   for(int i=0;i<n;i++)
   {
      ushort c=StringGetCharacter(s,i);
      if(c>='0' && c<='9') digits++;
      else if(c=='.' && dots==0 && digits>0) dots++;
      else if(!(c=='-' && i==0)) return false;
   }
   return digits>0 && StringGetCharacter(s,n-1)!='.';
}

string IsoUtc(const long utc_msc)
{
   string t=TimeToString((datetime)(utc_msc/1000),TIME_DATE|TIME_SECONDS);
   StringReplace(t,".","-"); StringReplace(t," ","T");
   return t+"."+StringFormat("%03d",(int)(utc_msc%1000))+"Z";
}

// Durable append-only outbox; each line is flushed and closed before returning.
class CB1JsonlSink : public CB1Sink
{
public:
   string file,version,symbol;
   int    failed;
   CB1JsonlSink() { failed=0; }
   virtual void Emit(const string id,const string type,const bool confirmed,const long utc,CB1Doc &f)
   {
      string pub="",prv="";
      for(int i=0;i<ArraySize(f.keys);i++)
      {
         string v=IsNumber(f.values[i]) ? f.values[i] : "\""+JsonEscape(f.values[i])+"\"";
         if(StringFind(f.keys[i],"private_")==0)
            prv+=(prv=="" ? "" : ",")+"\""+StringSubstr(f.keys[i],8)+"\":"+v;
         else pub+=(pub=="" ? "" : ",")+"\""+JsonEscape(f.keys[i])+"\":"+v;
      }
      string line="{\"event_id\":\""+JsonEscape(id)+"\",\"type\":\""+type+"\",\"confirmed\":"+(confirmed ? "true" : "false")+
                  ",\"utc_ms\":"+IntegerToString(utc)+",\"utc\":\""+IsoUtc(utc)+"\",\"strategy\":\"B1-FINAL\",\"version\":\""+version+
                  "\",\"symbol\":\""+symbol+"\",\"fields\":{"+pub+"},\"private\":{"+prv+"}}";
      int h=FileOpen(file,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
      if(h==INVALID_HANDLE)
      {
         // Execution must not depend on the outbox; the journal keeps the lost event.
         failed++;
         Print("OUTBOX_WRITE_FAILED ",GetLastError()," ",line);
         return;
      }
      FileSeek(h,0,SEEK_END);
      FileWriteString(h,line+"\n");
      FileFlush(h); FileClose(h);
   }
};

CB1MtBroker   g_broker;
CB1JsonlSink  g_sink;
CB1FileStore *g_store=NULL;
CB1Engine     g_engine;
datetime      g_last_bar=0;
long          g_mark_day=-1;

bool Preflight(string &reason)
{
   if(!MQLInfoInteger(MQL_TESTER)) { reason="ORDER_MODE_TESTER_ONLY"; return false; }
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)!=ACCOUNT_TRADE_MODE_DEMO) { reason="NOT_DEMO_ACCOUNT"; return false; }
   if(ExpectedLogin<=0 || ExpectedServer=="") { reason="EXPECTED_IDENTITY_NOT_CONFIGURED"; return false; }
   if(AccountInfoInteger(ACCOUNT_LOGIN)!=ExpectedLogin || AccountInfoString(ACCOUNT_SERVER)!=ExpectedServer)
   { reason="ACCOUNT_IDENTITY_MISMATCH"; return false; }
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) { reason="NOT_HEDGING"; return false; }
   if(_Symbol!=TargetSymbol || !SymbolSelect(TargetSymbol,true)) { reason="SYMBOL_MISMATCH"; return false; }
   if(SymbolInfoInteger(TargetSymbol,SYMBOL_TRADE_MODE)!=SYMBOL_TRADE_MODE_FULL) { reason="SYMBOL_NOT_FULLY_TRADABLE"; return false; }
   if(SymbolInfoString(TargetSymbol,SYMBOL_CURRENCY_PROFIT)!=AccountInfoString(ACCOUNT_CURRENCY)) { reason="PROFIT_CURRENCY_MISMATCH"; return false; }
   // Fixed offset only (no DST handling); must keep M15 bars aligned to UTC quarter hours.
   if(BrokerUtcOffsetSec%900!=0) { reason="UTC_OFFSET_BREAKS_M15_ALIGNMENT"; return false; }
   if(!MQLInfoInteger(MQL_TESTER) && MathAbs((long)TimeTradeServer()-(long)TimeGMT()-BrokerUtcOffsetSec)>60)
   { reason="UTC_OFFSET_INCONSISTENT"; return false; }
   return true;
}

void FeedBars(const bool initial)
{
   datetime forming=iTime(TargetSymbol,PERIOD_M15,0);
   if(forming==0 || forming==g_last_bar) return;
   datetime from=g_engine.ind.count>0 ? g_engine.ind.last_time+1 : SeedAnchor;
   MqlRates bars[];
   int n=CopyRates(TargetSymbol,PERIOD_M15,from,forming-1,bars);
   if(n<0)
   {
      // Retried next tick; bars are never skipped, so no signal can be formed meanwhile.
      if(initial) g_engine.Untrust("HISTORY_UNAVAILABLE");
      return;
   }
   datetime now=TimeCurrent();
   // Seed history is silent; later bars always emit, so a signal observed only after
   // its entry window (session break) is logged and expired rather than dropped.
   for(int i=0;i<n;i++)
      if(bars[i].time<forming) g_engine.OnBar(bars[i],!initial || (long)bars[i].time+1800>(long)now);
   g_last_bar=forming;
   if(initial && g_engine.ind.count<B1_WARMUP) g_engine.Untrust("WARMUP_INCOMPLETE");
}

void MarkEquity()
{
   long day=g_engine.UtcMsc(g_engine.last_msc)/86400000;
   if(day==g_mark_day) return;
   g_mark_day=day;
   CB1Doc f;
   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   f.Set("equity",B1F(equity)); f.Set("balance",B1F(AccountInfoDouble(ACCOUNT_BALANCE)));
   f.Set("hwm",B1F(g_engine.hwm)); f.Set("max_dd",B1F(g_engine.max_dd)); f.SetL("dd_stop",g_engine.dd_stop);
   f.SetL("open_position",g_engine.pos_ticket!=0);
   g_engine.Emit("EQUITY_MARK",false,IntegerToString(day),f);
}

int OnInit()
{
   string reason="";
   if(!Preflight(reason)) { Print("NO_GO preflight: ",reason); return INIT_FAILED; }
   g_broker.sym=TargetSymbol; g_broker.magic=Magic;
   // One owner per account/symbol/magic regardless of version: versions sharing a magic would see each other's positions.
   g_broker.lock_name="B1LOCK_"+IntegerToString(ExpectedLogin)+"_"+TargetSymbol+"_"+IntegerToString(Magic);
   g_broker.lock_token=(double)(GetTickCount64()%1000000000+1);
   if(!g_broker.AcquireLock()) { Print("NO_GO: another owner holds ",Code()," on ",TargetSymbol); return INIT_FAILED; }
   g_sink.file="B1FINAL_"+Code()+"_events.jsonl"; g_sink.version=Version(); g_sink.symbol=TargetSymbol;
   g_store=new CB1FileStore("B1FINAL_"+Code()+"_"+IntegerToString(Magic)+".state");
   g_engine.broker=GetPointer(g_broker); g_engine.sink=GetPointer(g_sink); g_engine.store=g_store;
   g_engine.cfg.version=Version(); g_engine.cfg.code=Code(); g_engine.cfg.symbol=TargetSymbol; g_engine.cfg.magic=Magic;
   g_engine.cfg.exit_mode=ExitMode; g_engine.cfg.commission_per_lot=CommissionPerLot; g_engine.cfg.exit_fee_per_lot=ExitFeePerLot;
   g_engine.cfg.admission_reserve_r=AdmissionReserveR; g_engine.cfg.modify_delay_ms=ModifyDelayMs;
   g_engine.cfg.reconcile_timeout_sec=ReconcileTimeoutSec; g_engine.cfg.utc_offset_sec=BrokerUtcOffsetSec;
   g_engine.cfg.close_retry_sec=CloseRetrySec; g_engine.cfg.bootstrap_state=BootstrapState;
   g_engine.cfg.acknowledge_incident=AcknowledgeIncident;
   MqlTick t;
   if(SymbolInfoTick(TargetSymbol,t)) g_engine.last_msc=t.time_msc;
   g_engine.Init();
   FeedBars(true);
   Print("B1-FINAL ",Version()," initialized; trusted=",g_engine.trusted," reason=",g_engine.block_reason);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   MqlTick t;
   if(SymbolInfoTick(TargetSymbol,t)) g_engine.last_msc=t.time_msc;
   FeedBars(false);
   g_engine.OnTick();
   MarkEquity();
}

void ExportDeals()
{
   if(!HistorySelect(0,TimeCurrent()+86400)) return;
   int h=FileOpen("B1FINAL_"+Code()+"_deals.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE) return;
   FileWrite(h,"deal","position","time_msc_server","type","entry","volume","price","profit","commission","swap","magic","reason","comment");
   for(int i=0;i<HistoryDealsTotal();i++)
   {
      ulong d=HistoryDealGetTicket(i);
      if(d==0) continue;
      FileWrite(h,(long)d,HistoryDealGetInteger(d,DEAL_POSITION_ID),HistoryDealGetInteger(d,DEAL_TIME_MSC),
                HistoryDealGetInteger(d,DEAL_TYPE),HistoryDealGetInteger(d,DEAL_ENTRY),
                DoubleToString(HistoryDealGetDouble(d,DEAL_VOLUME),2),DoubleToString(HistoryDealGetDouble(d,DEAL_PRICE),5),
                DoubleToString(HistoryDealGetDouble(d,DEAL_PROFIT),2),DoubleToString(HistoryDealGetDouble(d,DEAL_COMMISSION),2),
                DoubleToString(HistoryDealGetDouble(d,DEAL_SWAP),2),HistoryDealGetInteger(d,DEAL_MAGIC),
                HistoryDealGetInteger(d,DEAL_REASON),HistoryDealGetString(d,DEAL_COMMENT));
   }
   FileClose(h);
}

// Exact completed bars the engine consumed, for reference parity on identical input.
void ExportBars()
{
   MqlRates bars[];
   int n=CopyRates(TargetSymbol,PERIOD_M15,SeedAnchor,g_engine.ind.last_time,bars);
   int h=FileOpen("B1FINAL_"+Code()+"_bars.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE) return;
   FileWrite(h,"bar_open_epoch","open","high","low","close");
   for(int i=0;i<n;i++)
      FileWrite(h,(long)bars[i].time-BrokerUtcOffsetSec,DoubleToString(bars[i].open,5),DoubleToString(bars[i].high,5),
                DoubleToString(bars[i].low,5),DoubleToString(bars[i].close,5));
   FileClose(h);
}

void OnDeinit(const int reason)
{
   if(MQLInfoInteger(MQL_TESTER))
   {
      ExportDeals();
      ExportBars();
      CB1Doc f;
      f.Set("final_equity",B1F(AccountInfoDouble(ACCOUNT_EQUITY))); f.Set("hwm",B1F(g_engine.hwm));
      f.Set("max_dd",B1F(g_engine.max_dd)); f.SetL("dd_stop",g_engine.dd_stop); f.SetL("incident",g_engine.incident);
      f.SetL("trusted",g_engine.trusted); f.Set("block_reason",g_engine.block_reason);
      f.SetL("outbox_write_failures",g_sink.failed);
      g_engine.Emit("RUN_SUMMARY",false,"deinit",f);
   }
   if(GlobalVariableCheck(g_broker.lock_name) && GlobalVariableGet(g_broker.lock_name)==g_broker.lock_token)
      GlobalVariableDel(g_broker.lock_name);
   if(g_store!=NULL) { delete g_store; g_store=NULL; }
}
