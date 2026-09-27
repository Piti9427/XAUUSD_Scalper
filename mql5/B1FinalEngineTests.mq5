#property strict
#property version "1.000"
#property description "B1-FINAL engine fault-injection tests against a fake broker. Tester only; no orders."
#property tester_file "B1_FINAL_parity_input.csv"
#include "B1FinalEngine.mqh"

input string ResultFile="B1_engine_tests.csv";

//--- deterministic broker double
class CFakeBroker : public CB1Broker
{
public:
   double bid,ask,balance,contract,leverage,commission_per_lot,slippage,swap;
   long   msc;
   B1Spec spec;
   B1Position pos[];
   double pos_commission[];
   ulong  closed_ticket[];
   string closed_comment[];
   B1CloseDeal closed[];
   B1Position closed_entry[];
   int    foreign,pending_orders,sends,modifies,closes,checks,cancels;
   string pending_comment;
   bool   lock_ok,omit_sl,check_fail,spec_ok,rewrite_comment,cancel_fail;
   int    send_mode;      // 0 fill,1 partial+remainder,2 reject,3 unknown+fill,4 unknown no fill
   int    modify_mode;    // 0 apply,1 reject,2 unknown+apply,3 unknown no apply,4 apply+reject retcode
   int    close_mode;     // 0 ok,1 fail
   double partial_ratio;
   ulong  next_ticket;

   CFakeBroker()
   {
      bid=100.0; ask=100.2; balance=100000.0; contract=100.0; leverage=1000.0; commission_per_lot=0.0;
      slippage=0.0; swap=0.0; msc=0;
      spec.vol_min=0.01; spec.vol_step=0.01; spec.vol_max=200.0; spec.tick_size=0.001; spec.point=0.001;
      spec.stops_level=0; spec.freeze_level=0; spec.trade_full=true;
      foreign=0; pending_orders=0; sends=0; modifies=0; closes=0; checks=0; cancels=0; pending_comment="";
      lock_ok=true; omit_sl=false; check_fail=false; spec_ok=true; rewrite_comment=false; cancel_fail=false;
      send_mode=0; modify_mode=0; close_mode=0; partial_ratio=0.5; next_ticket=1000;
   }
   double Mark(const B1Position &p) { return p.direction>0 ? bid : ask; }
   virtual bool Quote(double &b,double &a,long &t) { b=bid; a=ask; t=msc; return true; }
   virtual double Equity()
   {
      double e=balance;
      for(int i=0;i<ArraySize(pos);i++) e+=pos[i].direction*(Mark(pos[i])-pos[i].price_open)*contract*pos[i].volume+pos[i].swap;
      return e;
   }
   virtual double MarginFree()
   {
      double used=0.0;
      for(int i=0;i<ArraySize(pos);i++) used+=pos[i].volume*contract*pos[i].price_open/leverage;
      return Equity()-used;
   }
   virtual bool Spec(B1Spec &s) { s=spec; return spec_ok; }
   virtual bool CalcProfit(const int dir,const double v,const double o,const double c,double &p)
   { p=dir*(c-o)*contract*v; return true; }
   virtual bool CalcMargin(const int dir,const double v,const double price,double &m)
   { m=v*contract*price/leverage; return true; }
   virtual bool CheckOrder(const int dir,const double v,const double price,const double sl,const double tp,string &reason)
   { checks++; reason=check_fail ? "10019" : ""; return !check_fail; }
   virtual int OwnedPositions(B1Position &out[])
   {
      int n=ArraySize(pos); ArrayResize(out,n);
      for(int i=0;i<n;i++) out[i]=pos[i];
      return n;
   }
   virtual int ForeignExposure() { return foreign; }
   virtual int OwnedPendingOrders(const string c)
   { return (c=="" || c==pending_comment) ? pending_orders : 0; }
   virtual int CancelOwnedOrders(const string c)
   {
      cancels++;
      if(cancel_fail) return B1_SEND_REJECTED;
      if(c=="" || c==pending_comment) pending_orders=0;
      return B1_SEND_DONE;
   }
   virtual bool FindFilledPosition(const string c,const ulong order,B1Position &filled)
   {
      for(int i=0;i<ArraySize(closed_comment);i++)
         if(closed_comment[i]==c || (order!=0 && closed_ticket[i]==order)) { filled=closed_entry[i]; return true; }
      return false;
   }
   virtual bool EntryCommission(const ulong position,double &cost)
   {
      for(int i=0;i<ArraySize(pos);i++) if(pos[i].ticket==position) { cost=pos_commission[i]; return true; }
      return false;
   }
   virtual bool CloseDeal(const ulong position,B1CloseDeal &deal)
   {
      for(int i=0;i<ArraySize(closed_ticket);i++) if(closed_ticket[i]==position) { deal=closed[i]; return true; }
      return false;
   }
   ulong Open(const int dir,const double v,const double price,const double sl,const double tp,const string c)
   {
      int n=ArraySize(pos); ArrayResize(pos,n+1); ArrayResize(pos_commission,n+1);
      pos[n].ticket=next_ticket++; pos[n].direction=dir; pos[n].volume=v; pos[n].price_open=price+dir*slippage;
      pos[n].sl=omit_sl ? 0.0 : sl; pos[n].tp=tp; pos[n].swap=0.0; pos[n].comment=rewrite_comment ? "broker-rewritten" : c;
      pos_commission[n]=commission_per_lot*v; balance-=pos_commission[n];
      return pos[n].ticket;
   }
   virtual int SendMarket(const int dir,const double v,const double price,const double sl,const double tp,const string c,ulong &order)
   {
      sends++;
      order=0;
      if(send_mode==2) return B1_SEND_REJECTED;
      if(send_mode==4) return B1_SEND_UNKNOWN;
      double filled=v;
      if(send_mode==1)
      {
         filled=MathFloor(v*partial_ratio/spec.vol_step+1e-9)*spec.vol_step;
         pending_orders=1; pending_comment=c;
      }
      order=Open(dir,filled,price,sl,tp,c);
      return send_mode==3 ? B1_SEND_UNKNOWN : (send_mode==1 ? B1_SEND_PARTIAL : B1_SEND_DONE);
   }
   virtual int ModifyStops(const ulong ticket,const double sl,const double tp)
   {
      modifies++;
      if(modify_mode==1) return B1_SEND_REJECTED;
      if(modify_mode==3) return B1_SEND_UNKNOWN;
      for(int i=0;i<ArraySize(pos);i++) if(pos[i].ticket==ticket) { pos[i].sl=sl; pos[i].tp=tp; }
      if(modify_mode==4) return B1_SEND_REJECTED;   // e.g. NO_CHANGES: stop already in place
      return modify_mode==2 ? B1_SEND_UNKNOWN : B1_SEND_DONE;
   }
   void CloseAt(const int i,const double price,const string reason)
   {
      int n=ArraySize(closed_ticket);
      ArrayResize(closed_ticket,n+1); ArrayResize(closed_comment,n+1); ArrayResize(closed,n+1); ArrayResize(closed_entry,n+1);
      double profit=pos[i].direction*(price-pos[i].price_open)*contract*pos[i].volume;
      closed_ticket[n]=pos[i].ticket; closed_comment[n]=pos[i].comment; closed_entry[n]=pos[i];
      closed[n].price=price; closed[n].profit=profit; closed[n].commission=0.0; closed[n].swap=pos[i].swap;
      closed[n].volume=pos[i].volume; closed[n].time_msc=msc; closed[n].reason=reason;
      balance+=profit+pos[i].swap;
      for(int j=i;j<ArraySize(pos)-1;j++) { pos[j]=pos[j+1]; pos_commission[j]=pos_commission[j+1]; }
      ArrayResize(pos,ArraySize(pos)-1); ArrayResize(pos_commission,ArraySize(pos_commission)-1);
   }
   virtual int ClosePosition(const ulong ticket,const double v)
   {
      closes++;
      if(close_mode==1) return B1_SEND_REJECTED;
      for(int i=0;i<ArraySize(pos);i++) if(pos[i].ticket==ticket) { CloseAt(i,Mark(pos[i]),"INCIDENT_CLOSE"); return B1_SEND_DONE; }
      return B1_SEND_REJECTED;
   }
   virtual bool OwnerLock() { return lock_ok; }
   // Price moves first, then broker-side SL/TP at executable side (gaps fill at market).
   void Tick(const double b,const double a,const long t)
   {
      bid=b; ask=a; msc=t;
      for(int i=ArraySize(pos)-1;i>=0;i--)
      {
         pos[i].swap=swap;
         double m=Mark(pos[i]); int d=pos[i].direction;
         if(pos[i].sl>0 && d*(m-pos[i].sl)<=0) CloseAt(i,m,"SL");
         else if(pos[i].tp>0 && d*(m-pos[i].tp)>=0) CloseAt(i,pos[i].tp,"TP");
      }
   }
};

class CFakeSink : public CB1Sink
{
public:
   string ids[],types[],bodies[];
   bool   confirmed[];
   virtual void Emit(const string id,const string type,const bool conf,const long utc,CB1Doc &f)
   {
      int n=ArraySize(ids);
      ArrayResize(ids,n+1); ArrayResize(types,n+1); ArrayResize(bodies,n+1); ArrayResize(confirmed,n+1);
      ids[n]=id; types[n]=type; bodies[n]=f.Body(); confirmed[n]=conf;
   }
   int Count(const string type) { int c=0; for(int i=0;i<ArraySize(types);i++) if(types[i]==type) c++; return c; }
   string Last(const string type) { for(int i=ArraySize(types)-1;i>=0;i--) if(types[i]==type) return bodies[i]; return ""; }
   string Field(const string type,const string key)
   {
      string body=Last(type), lines[];
      int n=StringSplit(body,'\n',lines);
      for(int i=0;i<n;i++) if(StringFind(lines[i],key+"=")==0) return StringSubstr(lines[i],StringLen(key)+1);
      return "";
   }
   int ConfirmedCount() { int c=0; for(int i=0;i<ArraySize(confirmed);i++) if(confirmed[i]) c++; return c; }
};

//--- tiny test harness
int g_pass=0,g_fail=0,g_out=INVALID_HANDLE;
string g_test="";
void Check(const bool ok,const string what)
{
   if(ok) g_pass++; else { g_fail++; Print("FAIL ",g_test,": ",what); }
   if(g_out!=INVALID_HANDLE) FileWrite(g_out,g_test,what,ok ? "PASS" : "FAIL");
}

const datetime T0=D'2026.09.21 10:00';
long Msc(const int seconds_after_close) { return ((long)T0+900+seconds_after_close)*1000; }

class CRig
{
public:
   CFakeBroker    b;
   CFakeSink      s;
   CB1MemoryStore m;
   CB1Engine      e;
   CRig() { Wire(e); }
   void Wire(CB1Engine &eng)
   {
      eng.broker=GetPointer(b); eng.sink=GetPointer(s); eng.store=GetPointer(m);
      eng.cfg.version="B1-FINAL-v1.1"; eng.cfg.code="B1F11"; eng.cfg.symbol="XAUUSDm"; eng.cfg.magic=26092701;
      eng.cfg.exit_mode=B1_EXIT_FIXED; eng.cfg.commission_per_lot=0.0; eng.cfg.exit_fee_per_lot=0.0;
      eng.cfg.admission_reserve_r=0.0; eng.cfg.modify_delay_ms=2000; eng.cfg.reconcile_timeout_sec=30;
      eng.cfg.utc_offset_sec=0; eng.cfg.close_retry_sec=10; eng.cfg.bootstrap_state=true; eng.cfg.acknowledge_incident="";
   }
   void Arm(const int dir,const double atr) { e.sig_bar=(long)T0; e.sig_dir=dir; e.sig_atr=atr; }
   void Tick(const double bid,const int sec) { b.Tick(bid,bid+0.2,Msc(sec)); e.OnTick(); }
};

//--- bar fixtures
void Series(MqlRates &bars[],const int n,const datetime first)
{
   ArrayResize(bars,n);
   for(int i=0;i<n;i++)
   {
      double c=(i%2==0) ? 100.0 : 101.0;
      bars[i].time=first+i*900; bars[i].open=c; bars[i].close=c; bars[i].high=c+1.0; bars[i].low=c-1.0;
   }
}

void TestBuyFromBarsToTakeProfit()
{
   g_test="buy_bars_fill_tp";
   CRig r; r.e.Init();
   MqlRates bars[]; int n=110;
   Series(bars,n,T0-(n-1)*900);
   bars[n-1].close=103.0; bars[n-1].high=103.5; bars[n-1].open=101.0;
   for(int i=0;i<n;i++) r.e.OnBar(bars[i],i==n-1);
   Check(r.s.Count("SIGNAL")==1 && r.e.sig_dir==1,"completed breakout bar produces one long signal");
   r.b.Tick(103.0,103.2,Msc(-1)); r.e.OnTick();
   Check(r.b.sends==0,"no entry inside signal bar");
   r.Tick(103.0,0);
   Check(r.b.sends==1 && ArraySize(r.b.pos)==1,"first tick in next interval sends one market order");
   double atr=r.e.pos_r/B1_SL_ATR;
   Check(ArraySize(r.b.pos)==1 && MathAbs(r.b.pos[0].price_open-103.2)<1e-9,"BUY fills at Ask");
   Check(ArraySize(r.b.pos)==1 && MathAbs(r.b.pos[0].sl-B1Price(103.2-2.5*atr,0.001))<1e-9,"SL quote-anchored 2.5 ATR from Ask");
   Check(ArraySize(r.b.pos)==1 && MathAbs(r.b.pos[0].tp-B1Price(103.2+3.5*MathAbs(103.2-r.b.pos[0].sl),0.001))<1e-9,"TP 3.5R quote-anchored");
   double budget=100000.0*0.01, per_lot=MathAbs(103.2-r.e.pos_sl)*100.0;
   Check(MathAbs(r.e.pos_volume-MathFloor(budget/per_lot/0.01+1e-10)*0.01)<1e-9,"volume floored inside 1% budget");
   Check(r.s.Count("FILL_CONFIRMED")==1,"fill event emitted once");
   double tp=r.e.pos_tp;
   r.Tick(tp+0.5,5);
   Check(ArraySize(r.b.pos)==0 && r.s.Count("CLOSE_CONFIRMED")==1 && r.s.Field("CLOSE_CONFIRMED","reason")=="TP","TP close confirmed");
   Check(r.e.pos_ticket==0 && r.e.req_status==B1_REQ_NONE,"lifecycle cleared after close");
   Check(r.s.ConfirmedCount()==2,"only fill and close are confirmed events");
}

void TestSellFromBarsToStopLoss()
{
   g_test="sell_bars_fill_sl";
   CRig r; r.e.Init();
   MqlRates bars[]; int n=110;
   Series(bars,n,T0-(n-1)*900);
   bars[n-1].close=97.0; bars[n-1].low=96.5; bars[n-1].open=100.0; bars[n-1].high=100.0;
   for(int i=0;i<n;i++) r.e.OnBar(bars[i],i==n-1);
   Check(r.e.sig_dir==-1,"breakdown produces short signal");
   r.Tick(97.0,1);
   Check(ArraySize(r.b.pos)==1 && MathAbs(r.b.pos[0].price_open-97.0)<1e-9 && r.b.pos[0].direction==-1,"SELL fills at Bid");
   double sl=r.e.pos_sl;
   r.b.Tick(sl-0.3,sl-0.1,Msc(3)); r.e.OnTick();
   Check(ArraySize(r.b.pos)==1,"SELL stop not hit while Ask below SL");
   r.b.Tick(sl-0.1,sl+0.1,Msc(4)); r.e.OnTick();
   Check(ArraySize(r.b.pos)==0 && r.s.Field("CLOSE_CONFIRMED","reason")=="SL","SELL SL triggers on Ask");
}

void TestSignalTimingAndDuplicates()
{
   g_test="expiry_duplicates";
   CRig r; r.e.Init();
   r.Arm(1,2.0);
   r.Tick(100.0,900);
   Check(r.b.sends==0 && r.s.Field("ADMISSION","reason")=="SIGNAL_EXPIRED","first tick after next interval expires signal");
   r.Tick(100.0,901);
   Check(r.s.Count("ADMISSION")==1,"expired signal not retried");
   MqlRates bars[]; Series(bars,3,T0-2*900);
   for(int i=0;i<3;i++) r.e.OnBar(bars[i],false);
   r.e.OnBar(bars[2],true);
   Check(r.s.Count("DUPLICATE_BAR")==1,"duplicate completed bar rejected with reason");
}

void TestAdmissionRejections()
{
   g_test="admission_rejections";
   { CRig r; r.b.balance=100.0; r.e.Init(); r.Arm(1,6.0); r.Tick(100.0,0);
     Check(r.b.sends==0 && r.s.Field("ADMISSION","reason")=="RISK_BELOW_MINIMUM_LOT","small equity rejected, never clamped up");
     Check(StringToDouble(r.s.Field("ADMISSION","minimum_lot_risk"))>StringToDouble(r.s.Field("ADMISSION","risk_budget")),"rejection logs budget and minimum-lot risk"); }
   { CRig r; r.b.leverage=0.1; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.b.sends==0 && r.s.Field("ADMISSION","reason")=="INSUFFICIENT_MARGIN","margin shortfall rejected"); }
   { CRig r; r.b.foreign=1; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.b.sends==0 && r.b.closes==0 && r.s.Field("ADMISSION","reason")=="FOREIGN_EXPOSURE","foreign exposure blocks and is untouched"); }
   { CRig r; r.b.lock_ok=false; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.b.sends==0 && r.s.Field("ADMISSION","reason")=="DUPLICATE_OWNER","second owner blocked"); }
   { CRig r; r.b.check_fail=true; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.b.sends==0 && StringFind(r.s.Field("ADMISSION","reason"),"ORDER_CHECK_FAILED")==0,"OrderCheck failure blocks send"); }
   { CRig r; r.b.spec_ok=false; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.b.sends==0 && r.s.Field("ADMISSION","reason")=="SPEC_UNAVAILABLE","missing specification fails closed"); }
   { CRig r; r.e.cfg.commission_per_lot=7.0; r.e.cfg.exit_fee_per_lot=7.0; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double loss=MathAbs(r.e.req_quote-r.e.req_sl)*100.0*r.e.req_volume;
     Check(r.b.sends==1 && loss+14.0*r.e.req_volume<=1000.0+1e-9,"known fees reserved inside budget"); }
}

void TestRejectedAndAmbiguousSends()
{
   g_test="send_outcomes";
   { CRig r; r.b.send_mode=2; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0); r.Tick(100.0,1);
     Check(r.b.sends==1 && r.s.Count("REQUEST_REJECTED")==1 && r.e.req_status==B1_REQ_NONE,"definitive reject ends attempt, no retry"); }
   { CRig r; r.b.send_mode=3; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.e.req_status==B1_REQ_FILLED && r.s.Count("REQUEST_UNKNOWN")==1,"timeout-after-fill reconciled to fill");
     r.Arm(1,2.0); r.Tick(100.0,2);
     Check(r.b.sends==1 && ArraySize(r.b.pos)==1,"no duplicate order after timeout-after-fill"); }
   { CRig r; r.b.send_mode=4; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0); r.Tick(100.0,10);
     Check(r.e.req_status==B1_REQ_PENDING && r.b.sends==1,"unknown outcome stays pending inside window");
     r.Tick(100.0,31);
     Check(r.e.req_status==B1_REQ_NONE && r.s.Count("REQUEST_NO_FILL")==1 && r.b.sends==1,"no fill after window, never resubmitted"); }
   { CRig r; r.b.send_mode=1; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(ArraySize(r.b.pos)==1 && MathAbs(r.e.pos_volume-r.b.pos[0].volume)<1e-12 && r.e.pos_volume<r.e.req_volume,"partial fill keeps confirmed volume only");
     Check(r.s.Field("FILL_CONFIRMED","partial")=="1","partial flag in fill event");
     Check(r.b.cancels==1 && r.b.pending_orders==0 && r.s.Count("REMAINDER_CANCEL_REQUESTED")==1,"remainder cancelled, never topped up");
     r.Tick(r.e.pos_tp+0.1,5);
     r.Arm(1,2.0); r.Tick(100.0,6);
     Check(r.b.sends==2,"entries resume after remainder reconciled"); }
   { CRig r; r.b.send_mode=1; r.b.cancel_fail=true; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     r.Tick(r.e.pos_tp+0.1,5);
     r.Arm(1,2.0); r.Tick(100.0,6);
     Check(r.b.sends==1 && r.s.Field("ADMISSION","reason")=="UNRESOLVED_REQUEST","uncancelled remainder blocks new risk"); }
   { CRig r; r.b.rewrite_comment=true; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0); r.Tick(100.0,1);
     Check(r.e.req_status==B1_REQ_FILLED && r.e.pos_ticket==r.b.pos[0].ticket && !r.e.incident,"fill matched by order ticket when broker rewrites comment"); }
   { CRig r; r.b.rewrite_comment=true; r.b.send_mode=3; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0); r.Tick(100.0,40);
     Check(r.e.req_status==B1_REQ_FILLED && r.b.sends==1 && !r.e.incident,"ambiguous send with rewritten comment adopted by order ticket"); }
   { CRig r; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     r.b.pos[0].volume*=3.0; r.Tick(100.0,1);
     Check(r.s.Count("POSITION_VOLUME_CHANGED")==1 && r.e.incident && StringFind(r.e.incident_id,"FILL_RISK_OVER_BUDGET")==0 && r.b.closes==1,
           "late volume growth re-verified against budget"); }
}

void TestRestartRecovery()
{
   g_test="restart_recovery";
   { // crash after persisting request and broker fill, before response handling
     CRig r; r.e.Init(); r.Arm(1,2.0);
     r.b.send_mode=4; r.Tick(100.0,0);
     r.b.Open(1,r.e.req_volume,r.e.req_quote,r.e.req_sl,r.e.req_tp,r.e.req_id);
     CB1Engine e2; r.Wire(e2); e2.Init();
     Check(r.s.Count("RECOVERY_PENDING_REQUEST")==1,"restart reports pending request");
     r.b.Tick(100.0,100.2,Msc(3)); e2.OnTick();
     Check(e2.req_status==B1_REQ_FILLED && e2.pos_ticket==r.b.pos[0].ticket && r.b.sends==1,"restart-before-response adopts fill without resend");
     e2.sig_bar=(long)T0; e2.sig_dir=1; e2.sig_atr=2.0; r.b.Tick(100.0,100.2,Msc(4)); e2.OnTick();
     Check(ArraySize(r.b.pos)==1 && r.b.sends==1,"duplicate tick/signal after restart keeps one position"); }
   { // filled and stopped out while offline
     CRig r; r.e.Init(); r.Arm(1,2.0); r.b.send_mode=4; r.Tick(100.0,0);
     r.b.Open(1,r.e.req_volume,r.e.req_quote,r.e.req_sl,r.e.req_tp,r.e.req_id);
     r.b.CloseAt(0,r.e.req_sl,"SL");
     CB1Engine e2; r.Wire(e2); e2.Init();
     r.b.Tick(100.0,100.2,Msc(40)); e2.OnTick();
     Check(r.s.Count("FILL_CONFIRMED")==1 && r.s.Count("CLOSE_CONFIRMED")==1 && r.b.sends==1,"offline fill+close reconstructed from history, no resend");
     Check(e2.req_status==B1_REQ_NONE && e2.pos_ticket==0,"state clean after offline close"); }
   { // offline fill with slippage and partial volume: event carries the broker's deal values
     CRig r; r.e.Init(); r.Arm(1,2.0); r.b.send_mode=4; r.Tick(100.0,0);
     double half=MathFloor(r.e.req_volume*0.5/0.01+1e-9)*0.01;
     r.b.slippage=0.05; r.b.Open(1,half,r.e.req_quote,r.e.req_sl,r.e.req_tp,r.e.req_id);
     r.b.CloseAt(0,r.e.req_tp,"TP");
     CB1Engine e2; r.Wire(e2); e2.Init();
     r.b.Tick(100.0,100.2,Msc(40)); e2.OnTick();
     Check(MathAbs(StringToDouble(r.s.Field("FILL_CONFIRMED","fill_price"))-(r.e.req_quote+0.05))<1e-9 &&
           MathAbs(StringToDouble(r.s.Field("FILL_CONFIRMED","volume"))-half)<1e-9,"offline fill reports broker price and volume, not request"); }
   { // restart with open position keeps managing it
     CRig r; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     CB1Engine e2; r.Wire(e2); e2.Init();
     Check(e2.pos_ticket==r.e.pos_ticket && e2.pos_r==r.e.pos_r,"position identity and R restored");
     r.b.Tick(e2.pos_sl-0.1,e2.pos_sl+0.1,Msc(5)); e2.OnTick();
     Check(r.s.Count("CLOSE_CONFIRMED")==1,"restored engine confirms close"); }
   { // owned position unknown to state
     CRig r; r.e.Init(); r.b.Open(1,0.1,100.2,95.0,110.0,"manual");
     r.Tick(100.0,0);
     Check(r.e.incident && r.b.closes==0,"unexpected owned exposure halts without closing"); }
}

void TestStateIntegrity()
{
   g_test="state_integrity";
   { CRig r; r.e.Init(); r.b.Tick(100.0,100.2,Msc(0)); r.b.balance=110000.0; r.e.OnTick();
     r.b.balance=96000.0; r.e.OnTick();
     double hwm=r.e.hwm, persisted=r.e.saved_hwm;
     Check(hwm==110000.0 && persisted>=hwm,"persisted HWM never below true HWM");
     CB1Engine e2; r.Wire(e2); e2.Init();
     Check(e2.trusted && e2.hwm>=hwm && e2.RiskPct(96000.0)<=r.e.RiskPct(96000.0),"restart never lowers HWM or raises risk");
     string saved=r.m.text;
     r.m.text=saved; StringSetCharacter(r.m.text,10,'9');
     CB1Engine e3; r.Wire(e3); e3.Init();
     Check(!e3.trusted,"tampered state untrusted");
     e3.sig_bar=(long)T0; e3.sig_dir=1; e3.sig_atr=2.0; r.b.Tick(100.0,100.2,Msc(1)); e3.OnTick();
     Check(r.b.sends==0 && StringFind(r.s.Field("ADMISSION","reason"),"STATE_UNTRUSTED")==0,"corrupt state blocks entries");
     Check(r.m.text!=saved && StringLen(r.m.text)==StringLen(saved),"corrupt evidence not overwritten"); }
   { CRig r; r.e.cfg.bootstrap_state=false; r.e.Init();
     Check(!r.e.trusted && r.e.block_reason=="STATE_MISSING_NO_BOOTSTRAP","missing HWM without explicit bootstrap blocks"); }
   { CRig r; r.b.Open(1,0.1,100.2,95.0,110.0,"x"); r.e.Init();
     Check(!r.e.trusted && r.e.block_reason=="STATE_MISSING_WITH_OWNED_EXPOSURE","no optimistic HWM with live exposure"); }
   { CRig r; r.e.Init(); CB1Engine e2; r.Wire(e2); e2.cfg.version="B1-FINAL-v1"; e2.Init();
     Check(!e2.trusted,"version mismatch rejected"); }
   { CB1Doc d; d.SetD("x",0.1+0.2); d.SetD("y",-1e-300); CB1Doc p;
     Check(p.Parse(d.Serialize()) && p.D("x")==0.1+0.2 && p.D("y")==-1e-300,"exact double round trip"); }
   { CRig r; r.m.fail_save=true; r.e.Init();
     Check(!r.e.trusted && r.e.block_reason=="STATE_WRITE_FAILED","write failure blocks entries"); }
}

void TestDrawdownTiers()
{
   g_test="drawdown_tiers";
   double dds[]={2.9999,3.0,5.9999,6.0,8.9999,9.0,11.9999};
   double expected[]={0.01,0.0075,0.0075,0.005,0.005,0.0025,0.0025};
   for(int i=0;i<ArraySize(dds);i++)
   {
      CRig r; r.e.Init();
      r.b.balance=100000.0*(1-dds[i]/100.0); r.Arm(1,2.0); r.Tick(100.0,0);
      Check(MathAbs(StringToDouble(r.s.Field("ADMISSION","risk_pct"))-expected[i])<1e-12 && r.b.sends==1,
            "tier at DD "+DoubleToString(dds[i],4));
   }
   { CRig r; r.e.Init(); r.b.balance=88000.0; r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.e.dd_stop && r.b.sends==0 && r.s.Count("STOP_NEW_ENTRIES")==1,"12% latches STOP_NEW_ENTRIES");
     r.b.balance=100000.0; r.Arm(1,2.0); r.Tick(100.0,1);
     Check(r.b.sends==0 && r.s.Field("ADMISSION","reason")=="HARD_DD_STOP","latch survives equity recovery");
     CB1Engine e2; r.Wire(e2); e2.Init();
     Check(e2.dd_stop,"latch survives restart"); }
   { // intratrade marks raise HWM
     CRig r; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     r.Tick(r.e.pos_entry+1.0,1);
     double peak=r.b.Equity();
     r.Tick(r.e.pos_entry-1.0,2);
     Check(peak>100000.0 && r.e.hwm==peak && ArraySize(r.b.pos)==1,"intratrade peak raises HWM before close"); }
   { // DD crosses 12% intratrade while protected: latch, no panic close
     CRig r; r.e.Init(); r.b.balance=88050.0; r.Arm(1,2.0); r.Tick(100.0,0);
     Check(MathAbs(StringToDouble(r.s.Field("ADMISSION","risk_pct"))-0.0025)<1e-12,"entry at 0.25% tier near limit");
     r.Tick(r.e.pos_entry-r.e.pos_r*0.5,1);
     Check(r.e.dd_stop && ArraySize(r.b.pos)==1 && r.b.closes==0,"intratrade 12% latches without closing protected trade"); }
}

void TestIncidents()
{
   g_test="incidents";
   { CRig r; r.b.omit_sl=true; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.e.incident && r.b.closes==1 && ArraySize(r.b.pos)==0,"missing SL closes owned exposure and halts");
     r.Tick(100.0,1);
     Check(r.s.Count("CLOSE_CONFIRMED")==1 && !r.e.close_required,"incident close confirmed");
     r.Arm(1,2.0); r.Tick(100.0,2);
     Check(r.b.sends==1 && r.s.Field("ADMISSION","reason")=="INCIDENT_HALT","incident halt blocks new entries"); }
   { CRig r; r.b.slippage=3.0; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.s.Count("INCIDENT")==1 && StringFind(r.s.Field("INCIDENT","reason"),"FILL_RISK_OVER_BUDGET")==0 && r.b.closes==1,"adverse fill over budget closes and halts"); }
   { CRig r; r.b.omit_sl=true; r.b.close_mode=1; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     Check(r.s.Count("CLOSE_FAILED_CRITICAL")==1 && ArraySize(r.b.pos)==1,"failed close recorded critical");
     r.Tick(100.0,5);
     Check(r.b.closes==1,"close retry throttled");
     r.Tick(100.0,11);
     Check(r.b.closes==2 && r.e.close_required,"close retried while unresolved");
     r.Arm(1,2.0); r.Tick(100.0,12);
     Check(r.b.sends==1,"entries blocked during unresolved incident");
     string id=r.e.incident_id;
     r.b.close_mode=0; r.Tick(100.0,22); r.Tick(100.0,23);
     CB1Engine e2; r.Wire(e2); e2.cfg.acknowledge_incident=id; e2.Init();
     Check(!e2.incident,"operator acknowledgement clears resolved incident"); }
}

void TestCostCoveringStop()
{
   g_test="cost_covering_stop";
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.e.cfg.exit_fee_per_lot=3.0; r.b.commission_per_lot=3.5;
     r.e.cfg.commission_per_lot=3.5; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r, tp=r.e.pos_tp, v=r.e.pos_volume;
     r.b.swap=-4.0;
     r.Tick(entry+2*R-0.01,1);
     Check(r.e.exit_state==B1_EX_NONE,"below +2R Bid no trigger");
     r.Tick(entry+2*R+0.01,2);
     Check(r.e.exit_state==B1_EX_ARMED && r.b.modifies==0,"+2R arms; modification waits for delay");
     r.Tick(entry+2*R+0.02,4);
     double need=3.5*v+3.0*v+4.0;
     double stop=r.b.pos[0].sl;
     Check(r.b.modifies==1 && r.e.exit_state==B1_EX_CONFIRMED,"one modification confirmed by broker state");
     Check((stop-entry)*100*v>=need-1e-9 && (stop-0.001-entry)*100*v<need,"stop covers commission+fee+negative swap on tick grid, minimal");
     Check(MathAbs(r.b.pos[0].tp-tp)<1e-12,"original TP preserved");
     Check(r.s.Count("SL_MODIFIED_CONFIRMED")==1,"confirmed modification event");
     r.Tick(entry+3*R,6);
     Check(r.b.modifies==1,"no second modification"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.e.Init(); r.Arm(-1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r;
     r.b.Tick(entry-2*R+0.1,entry-2*R+0.3,Msc(1)); r.e.OnTick();
     Check(r.e.exit_state==B1_EX_NONE,"SELL trigger uses Ask not Bid");
     r.b.Tick(entry-2*R-0.3,entry-2*R-0.1,Msc(2)); r.e.OnTick();
     r.b.Tick(entry-2*R-0.3,entry-2*R-0.1,Msc(5)); r.e.OnTick();
     Check(r.e.exit_state==B1_EX_CONFIRMED && MathAbs(r.b.pos[0].sl-entry)<1e-9,"SELL zero-cost stop at entry"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r, sl=r.e.pos_sl;
     r.b.swap=50.0;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4);
     Check(MathAbs(r.b.pos[0].sl-entry)<1e-9,"positive swap never moves stop below entry-cost floor"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r, sl=r.e.pos_sl;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry-0.5,2); r.Tick(entry-0.5,4);
     Check(r.b.modifies==0 && r.e.exit_state==B1_EX_ARMED,"+2R then retrace below target stop: no request");
     r.Tick(sl-0.01,6);
     Check(r.s.Field("CLOSE_CONFIRMED","reason")=="SL" && r.b.modifies==0,"retrace to original SL closes at original stop"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.b.modify_mode=1; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r, sl=r.e.pos_sl;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4); r.Tick(entry+2*R+0.01,8);
     Check(r.b.modifies==1 && r.e.exit_state==B1_EX_REJECTED && MathAbs(r.b.pos[0].sl-sl)<1e-12,"rejection keeps original stop, no retry"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.b.modify_mode=2; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4);
     Check(r.e.exit_state==B1_EX_CONFIRMED && r.b.modifies==1,"broker stop read-back confirms ambiguous success"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.b.modify_mode=4; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4);
     Check(r.e.exit_state==B1_EX_CONFIRMED && r.b.modifies==1,"reject retcode with stop already applied counts as confirmed"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.b.modify_mode=3; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4); r.Tick(entry+2*R+0.01,40);
     Check(r.e.exit_state==B1_EX_REJECTED && r.b.modifies==1,"unapplied ambiguous modification not resent"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r, tp=r.e.pos_tp;
     r.Tick(entry+2*R+0.01,1); r.Tick(tp+0.01,2);
     Check(r.s.Field("CLOSE_CONFIRMED","reason")=="TP" && r.b.modifies==0,"TP during pending delay closes without modification"); }
   { // crash after persisting modification request
     CRig r; r.e.cfg.exit_mode=B1_EXIT_COST_BE; r.b.modify_mode=3; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4);
     r.b.pos[0].sl=r.e.exit_sl;
     CB1Engine e2; r.Wire(e2); e2.cfg.exit_mode=B1_EXIT_COST_BE; e2.Init();
     r.b.Tick(entry+2*R+0.01,entry+2*R+0.21,Msc(6)); e2.OnTick();
     Check(e2.exit_state==B1_EX_CONFIRMED && r.b.modifies==1,"restart confirms from broker stop without resend"); }
   { CRig r; r.e.cfg.exit_mode=B1_EXIT_ENTRY_BE; r.e.cfg.exit_fee_per_lot=5.0; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4);
     Check(MathAbs(r.b.pos[0].sl-entry)<1e-9,"entry-price BE control ignores costs"); }
   { CRig r; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double entry=r.e.pos_entry, R=r.e.pos_r;
     r.Tick(entry+2*R+0.01,1); r.Tick(entry+2*R+0.01,4);
     Check(r.b.modifies==0,"fixed exit never modifies"); }
   { CRig r; r.e.Init(); r.Arm(1,2.0); r.Tick(100.0,0);
     double sl=r.e.pos_sl;
     r.Tick(sl-3.0,2);
     Check(r.s.Field("CLOSE_CONFIRMED","reason")=="SL" && StringToDouble(r.s.Field("CLOSE_CONFIRMED","net_r"))<-1.0,"gap through stop reported at executable price"); }
}

//--- indicator parity and checkpoint equivalence on the hashed reference bars
bool ReadBars(MqlRates &bars[])
{
   int h=FileOpen("B1_FINAL_parity_input.csv",FILE_READ|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE) return false;
   for(int c=0;c<5;c++) FileReadString(h);
   int n=0;
   while(!FileIsEnding(h))
   {
      string stamp=FileReadString(h);
      if(stamp=="" && FileIsEnding(h)) break;
      ArrayResize(bars,n+1);
      bars[n].time=(datetime)StringToInteger(stamp);
      bars[n].open=StringToDouble(FileReadString(h)); bars[n].high=StringToDouble(FileReadString(h));
      bars[n].low=StringToDouble(FileReadString(h)); bars[n].close=StringToDouble(FileReadString(h));
      n++;
   }
   FileClose(h);
   return n>0;
}

bool Same(const double a,const double b) { return a==b; }

void TestIndicatorCheckpoint()
{
   g_test="indicator_checkpoint";
   MqlRates bars[];
   if(!ReadBars(bars)) { Check(false,"parity input available"); return; }
   int n=ArraySize(bars);
   double atr[],rsi[],hh[],ll[]; int dir[];
   B1Indicators(bars,atr,rsi,hh,ll,dir);
   B1IndState s; B1IndReset(s);
   int mismatches=0,signals=0;
   int cut=n/2;
   CB1Doc doc;
   for(int i=0;i<cut;i++)
   {
      double a,r,h,l; int d;
      B1IndUpdate(s,bars[i],a,r,h,l,d);
      if(!Same(a,atr[i])||!Same(r,rsi[i])||!Same(h,hh[i])||!Same(l,ll[i])||d!=dir[i]) mismatches++;
   }
   B1IndSave(s,doc);
   CB1Doc restored; B1IndState s2; B1IndReset(s2);
   bool ok=restored.Parse(doc.Serialize()) && B1IndLoad(s2,restored);
   for(int i=cut;i<n;i++)
   {
      double a,r,h,l,a2,r2,h2,l2; int d,d2;
      B1IndUpdate(s,bars[i],a,r,h,l,d);
      B1IndUpdate(s2,bars[i],a2,r2,h2,l2,d2);
      if(!Same(a,atr[i])||!Same(r,rsi[i])||!Same(h,hh[i])||!Same(l,ll[i])||d!=dir[i]) mismatches++;
      if(!Same(a,a2)||!Same(r,r2)||!Same(h,h2)||!Same(l,l2)||d!=d2) mismatches++;
      if(d!=0) signals++;
   }
   Check(mismatches==0,"incremental equals batch and checkpoint-resume equals uninterrupted ("+IntegerToString(n)+" bars)");
   Check(ok && signals>0,"checkpoint restored and future signals present");
   B1IndState reseed; B1IndReset(reseed);
   double a=0,r=0,h,l; int d;
   for(int i=n-120;i<n;i++) B1IndUpdate(reseed,bars[i],a,r,h,l,d);
   Check(MathAbs(a-atr[n-1])>1e-8 || MathAbs(r-rsi[n-1])>1e-8,"rolling 120-bar reseed is not equivalent");
   MqlRates bad=bars[n-1]; bad.time+=60;
   B1IndState t=s;
   Check(!B1IndUpdate(t,bad,a,r,h,l,d),"misaligned bar rejected");
   bad=bars[n-1]; bad.time+=900; bad.high=bad.low-1;
   Check(!B1IndUpdate(t,bad,a,r,h,l,d),"invalid OHLC rejected");
}

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER)) { Print("NO_GO: tester-only test harness"); return INIT_FAILED; }
   g_out=FileOpen(ResultFile,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   FileWrite(g_out,"test","check","result");
   TestBuyFromBarsToTakeProfit();
   TestSellFromBarsToStopLoss();
   TestSignalTimingAndDuplicates();
   TestAdmissionRejections();
   TestRejectedAndAmbiguousSends();
   TestRestartRecovery();
   TestStateIntegrity();
   TestDrawdownTiers();
   TestIncidents();
   TestCostCoveringStop();
   TestIndicatorCheckpoint();
   FileWrite(g_out,"SUMMARY",IntegerToString(g_pass)+" passed",IntegerToString(g_fail)+" failed");
   FileClose(g_out);
   Print("B1 engine tests: ",g_pass," passed, ",g_fail," failed");
   return INIT_SUCCEEDED;
}

void OnTick() {}
