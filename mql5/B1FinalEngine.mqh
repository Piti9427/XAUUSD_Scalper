// B1-FINAL execution engine. Broker, event sink and storage are injected so the
// same code runs against MT5 or deterministic fakes. Broker state is the source
// of truth for exposure; persisted state is the source of truth for HWM/halts.
#ifndef B1_FINAL_ENGINE
#define B1_FINAL_ENGINE
#include "B1FinalState.mqh"

enum B1SendResult { B1_SEND_DONE=0, B1_SEND_PARTIAL=1, B1_SEND_REJECTED=2, B1_SEND_UNKNOWN=3 };
enum B1ExitMode { B1_EXIT_FIXED=0, B1_EXIT_ENTRY_BE=1, B1_EXIT_COST_BE=2 };
enum B1ReqStatus { B1_REQ_NONE=0, B1_REQ_PENDING=1, B1_REQ_FILLED=2 };
enum B1ExitState { B1_EX_NONE=0, B1_EX_ARMED=1, B1_EX_REQUESTED=2, B1_EX_CONFIRMED=3,
                   B1_EX_REJECTED=4, B1_EX_SKIPPED=5 };

#define B1_SL_ATR 2.5
#define B1_TARGET_R 3.5
#define B1_TRIGGER_R 2.0

struct B1Spec
{
   double vol_min,vol_step,vol_max,tick_size,point;
   int    stops_level,freeze_level;
   bool   trade_full;
};

struct B1Position
{
   ulong  ticket;
   ulong  identifier;
   int    direction;
   double volume,price_open,sl,tp,swap;
   string comment;
};

struct B1CloseDeal
{
   double price,profit,commission,swap,volume;
   long   time_msc;
   string reason;
};

class CB1Broker
{
public:
   virtual bool   Quote(double &bid,double &ask,long &time_msc)=0;
   virtual double Equity()=0;
   virtual double MarginFree()=0;
   virtual bool   Spec(B1Spec &spec)=0;
   virtual bool   CalcProfit(const int dir,const double volume,const double open,const double close,double &profit)=0;
   virtual bool   CalcMargin(const int dir,const double volume,const double price,double &margin)=0;
   virtual bool   CheckOrder(const int dir,const double volume,const double price,const double sl,const double tp,string &reason)=0;
   virtual int    OwnedPositions(B1Position &out[])=0;
   virtual int    ForeignExposure()=0;
   virtual int    OwnedPendingOrders(const string comment)=0;   // "" counts every owned order
   virtual int    CancelOwnedOrders(const string comment)=0;
   // Entry deal values (price, volume, SL/TP) of a request found in history, by order ticket or comment.
   virtual bool   FindFilledPosition(const string comment,const ulong order,B1Position &filled)=0;
   virtual bool   EntryCommission(const ulong position,double &cost)=0;
   virtual bool   CloseDeal(const ulong position,B1CloseDeal &deal)=0;
   virtual int    SendMarket(const int dir,const double volume,const double price,const double sl,const double tp,const string comment,ulong &order)=0;
   virtual int    ModifyStops(const ulong ticket,const double sl,const double tp)=0;
   virtual int    ClosePosition(const ulong ticket,const double volume)=0;
   virtual bool   OwnerLock()=0;
};

class CB1Sink
{
public:
   // `confirmed` marks broker-confirmed execution; everything else is diagnostic.
   virtual bool Emit(const string event_id,const string type,const bool confirmed,
                     const long utc_msc,CB1Doc &fields)=0;
};

struct B1PendingEvent
{
   string id,type,fields;
   long utc_msc;
};

struct B1Config
{
   string version;
   string code;
   string symbol;
   long   magic;
   int    exit_mode;
   double commission_per_lot;
   double exit_fee_per_lot;
   double admission_reserve_r;
   int    modify_delay_ms;
   int    reconcile_timeout_sec;
   int    utc_offset_sec;
   int    close_retry_sec;
   bool   bootstrap_state;
   string acknowledge_incident;
};

string B1F(const double value) { return DoubleToString(value,10); }

class CB1Engine
{
public:
   CB1Broker *broker;
   CB1Sink   *sink;
   CB1Store  *store;
   B1Config   cfg;
   // durable state
   bool       trusted;
   string     block_reason;
   double     hwm,saved_hwm,max_dd;
   bool       dd_stop;
   bool       incident;
   string     incident_id;
   bool       close_required;
   long       close_attempt_msc;
   B1IndState ind;
   long       sig_bar;          // pending signal bar open (server epoch), 0 none
   int        sig_dir;
   double     sig_atr;
   int        req_status;
   string     req_id;
   int        req_dir;
   double     req_volume,req_quote,req_sl,req_tp,req_budget;
   long       req_msc;
   ulong      req_order;
   ulong      pos_ticket;
   ulong      pos_identifier;
   int        pos_dir;
   double     pos_volume,pos_entry,pos_sl,pos_tp,pos_r,pos_intended_r,pos_commission;
   int        exit_state;
   double     exit_sl;
   long       exit_armed_msc,exit_request_msc;
   long       day,remainder_open;
   double     day_r;
   B1PendingEvent pending_events[];
   // runtime
   double     last_bid,last_ask;
   long       last_msc;

   CB1Engine() { broker=NULL; sink=NULL; store=NULL; Reset(); }

   void Reset()
   {
      trusted=false; block_reason="NOT_INITIALIZED";
      hwm=0.0; saved_hwm=0.0; max_dd=0.0; dd_stop=false;
      incident=false; incident_id=""; close_required=false; close_attempt_msc=0;
      B1IndReset(ind);
      sig_bar=0; sig_dir=0; sig_atr=0.0;
      ClearRequest(); ClearPosition();
      day=0; day_r=0.0; remainder_open=0;
      ArrayResize(pending_events,0);
      last_bid=0.0; last_ask=0.0; last_msc=0;
   }

   void ClearRequest()
   { req_status=B1_REQ_NONE; req_id=""; req_dir=0; req_volume=0; req_quote=0; req_sl=0; req_tp=0; req_budget=0; req_msc=0; req_order=0; }

   bool IsRequestPosition(const B1Position &p) const
   { return req_id!="" && (p.comment==req_id || (req_order!=0 && (p.ticket==req_order || p.identifier==req_order))); }

   void ClearPosition()
   {
      pos_ticket=0; pos_identifier=0; pos_dir=0; pos_volume=0; pos_entry=0; pos_sl=0; pos_tp=0; pos_r=0; pos_intended_r=0;
      pos_commission=0; exit_state=B1_EX_NONE; exit_sl=0; exit_armed_msc=0; exit_request_msc=0;
   }

   long UtcMsc(const long server_msc) const { return server_msc-(long)cfg.utc_offset_sec*1000; }

   string EventId(const string type,const string ref) const
   { return cfg.version+"|"+cfg.symbol+"|"+IntegerToString(cfg.magic)+"|"+type+"|"+ref; }

   void Emit(const string type,const bool confirmed,const string ref,CB1Doc &f)
   {
      if(sink==NULL) return;
      if(!confirmed) { sink.Emit(EventId(type,ref),type,false,UtcMsc(last_msc),f); return; }
      string id=EventId(type,ref);
      for(int i=0;i<ArraySize(pending_events);i++) if(pending_events[i].id==id) return;
      int n=ArraySize(pending_events); ArrayResize(pending_events,n+1);
      pending_events[n].id=id; pending_events[n].type=type;
      pending_events[n].fields=f.Serialize(); pending_events[n].utc_msc=UtcMsc(last_msc);
      // Execution transition and event intent are saved together before append.
      if(Save()) FlushConfirmed();
   }

   void FlushConfirmed()
   {
      if(!trusted || sink==NULL) return;
      while(ArraySize(pending_events)>0)
      {
         CB1Doc f;
         if(!f.Parse(pending_events[0].fields)) { Untrust("PENDING_EVENT_CORRUPT"); return; }
         if(!sink.Emit(pending_events[0].id,pending_events[0].type,true,pending_events[0].utc_msc,f)) return;
         int n=ArraySize(pending_events);
         for(int i=1;i<n;i++) pending_events[i-1]=pending_events[i];
         ArrayResize(pending_events,n-1);
         // Sink must deduplicate IDs if append succeeds but this checkpoint fails.
         if(!Save()) return;
      }
   }

   void Diag(const string type,const string ref,const string reason)
   {
      CB1Doc f; f.Set("reason",reason);
      Emit(type,false,ref,f);
   }

   //--- persistence
   string Serialize()
   {
      CB1Doc d;
      d.SetL("schema",B1_STATE_SCHEMA); d.Set("version",cfg.version); d.Set("symbol",cfg.symbol);
      d.SetL("magic",cfg.magic);
      d.SetD("hwm",saved_hwm); d.SetD("max_dd",max_dd); d.SetL("dd_stop",dd_stop);
      d.SetL("incident",incident); d.Set("incident_id",incident_id); d.SetL("close_required",close_required);
      d.SetL("sig_bar",sig_bar); d.SetL("sig_dir",sig_dir); d.SetD("sig_atr",sig_atr);
      d.SetL("req_status",req_status); d.Set("req_id",req_id); d.SetL("req_dir",req_dir);
      d.SetD("req_volume",req_volume); d.SetD("req_quote",req_quote); d.SetD("req_sl",req_sl);
      d.SetD("req_tp",req_tp); d.SetD("req_budget",req_budget); d.SetL("req_msc",req_msc);
      d.SetL("req_order",(long)req_order);
      d.SetL("pos_ticket",(long)pos_ticket); d.SetL("pos_dir",pos_dir); d.SetD("pos_volume",pos_volume);
      d.SetL("pos_identifier",(long)pos_identifier);
      d.SetD("pos_entry",pos_entry); d.SetD("pos_sl",pos_sl); d.SetD("pos_tp",pos_tp); d.SetD("pos_r",pos_r);
      d.SetD("pos_intended_r",pos_intended_r); d.SetD("pos_commission",pos_commission);
      d.SetL("exit_state",exit_state); d.SetD("exit_sl",exit_sl); d.SetL("exit_armed_msc",exit_armed_msc);
      d.SetL("exit_request_msc",exit_request_msc);
      d.SetL("day",day); d.SetD("day_r",day_r);
      d.SetL("pending_count",ArraySize(pending_events));
      for(int i=0;i<ArraySize(pending_events);i++)
      {
         CB1Doc event;
         event.Set("id",pending_events[i].id); event.Set("type",pending_events[i].type);
         event.Set("fields",B1Hex(pending_events[i].fields)); event.SetL("utc_msc",pending_events[i].utc_msc);
         d.Set("pending_"+IntegerToString(i),B1Hex(event.Serialize()));
      }
      B1IndSave(ind,d);
      return d.Serialize();
   }

   // Untrusted state is never written: the stored evidence stays for manual review.
   bool Save()
   {
      if(store==NULL || !trusted) return false;
      double previous=saved_hwm;
      if(hwm>saved_hwm) saved_hwm=hwm;
      if(store.Save(Serialize())) return true;
      saved_hwm=previous;
      Untrust("STATE_WRITE_FAILED");
      return false;
   }

   void Untrust(const string reason)
   {
      if(trusted || block_reason!=reason) Diag("STATE_BLOCKED",reason,reason);
      trusted=false; block_reason=reason;
   }

   bool Restore(const string text)
   {
      CB1Doc d;
      if(!d.Parse(text)) return false;
      if(d.L("schema")!=B1_STATE_SCHEMA || d.S("version")!=cfg.version || d.S("symbol")!=cfg.symbol ||
         d.L("magic")!=cfg.magic) return false;
      double h=d.D("hwm");
      if(!MathIsValidNumber(h) || h<=0.0) return false;
      // Exact bits preserve tier boundaries and hard-stop behavior across restart.
      hwm=h; saved_hwm=h; max_dd=d.D("max_dd"); dd_stop=d.L("dd_stop")!=0;
      incident=d.L("incident")!=0; incident_id=d.S("incident_id"); close_required=d.L("close_required")!=0;
      sig_bar=d.L("sig_bar"); sig_dir=(int)d.L("sig_dir"); sig_atr=d.D("sig_atr");
      req_status=(int)d.L("req_status"); req_id=d.S("req_id"); req_dir=(int)d.L("req_dir");
      req_volume=d.D("req_volume"); req_quote=d.D("req_quote"); req_sl=d.D("req_sl"); req_tp=d.D("req_tp");
      req_budget=d.D("req_budget"); req_msc=d.L("req_msc"); req_order=(ulong)d.L("req_order");
      pos_ticket=(ulong)d.L("pos_ticket"); pos_dir=(int)d.L("pos_dir"); pos_volume=d.D("pos_volume");
      pos_identifier=(ulong)d.L("pos_identifier");
      if(pos_ticket!=0 && pos_identifier==0) return false;
      pos_entry=d.D("pos_entry"); pos_sl=d.D("pos_sl"); pos_tp=d.D("pos_tp"); pos_r=d.D("pos_r");
      pos_intended_r=d.D("pos_intended_r"); pos_commission=d.D("pos_commission");
      exit_state=(int)d.L("exit_state"); exit_sl=d.D("exit_sl"); exit_armed_msc=d.L("exit_armed_msc");
      exit_request_msc=d.L("exit_request_msc");
      day=d.L("day"); day_r=d.D("day_r");
      if(!d.Has("pending_count")) return false;
      int count=(int)d.L("pending_count");
      if(count<0 || count>100000) return false;
      ArrayResize(pending_events,count);
      for(int i=0;i<count;i++)
      {
         string text,fields; CB1Doc event,body;
         if(!B1Unhex(d.S("pending_"+IntegerToString(i)),text) || !event.Parse(text) ||
            !B1Unhex(event.S("fields"),fields) || !body.Parse(fields)) return false;
         string type=event.S("type");
         if(type!="FILL_CONFIRMED" && type!="SL_MODIFIED_CONFIRMED" && type!="CLOSE_CONFIRMED") return false;
         if(event.S("id")=="" || event.L("utc_msc")<=0) return false;
         pending_events[i].id=event.S("id"); pending_events[i].type=type;
         pending_events[i].fields=fields; pending_events[i].utc_msc=event.L("utc_msc");
      }
      return B1IndLoad(ind,d);
   }

   // Never throws away evidence: absent/corrupt state blocks entries but keeps protection running.
   void Init()
   {
      string text="";
      bool present=store!=NULL && store.Load(text);
      if(present)
      {
         if(Restore(text)) { trusted=true; block_reason=""; }
         else
         {
            Reset();
            Untrust("STATE_CORRUPT_OR_MISMATCH");
         }
      }
      else
      {
         B1Position owned[];
         double equity=broker.Equity();
         if(!cfg.bootstrap_state) Untrust("STATE_MISSING_NO_BOOTSTRAP");
         else if(broker.OwnedPositions(owned)>0) Untrust("STATE_MISSING_WITH_OWNED_EXPOSURE");
         else if(!(equity>0.0)) Untrust("EQUITY_UNAVAILABLE");
         else
         {
            hwm=equity; saved_hwm=0.0; trusted=true; block_reason="";
            CB1Doc f; f.Set("equity",B1F(equity));
            Emit("STATE_BOOTSTRAPPED",false,"bootstrap",f);
            Save();
         }
      }
      if(incident && cfg.acknowledge_incident!="" && cfg.acknowledge_incident==incident_id && !close_required)
      {
         Diag("INCIDENT_ACKNOWLEDGED",incident_id,incident_id);
         incident=false; incident_id="";
         if(trusted) Save();
      }
      if(req_status==B1_REQ_PENDING) Diag("RECOVERY_PENDING_REQUEST",req_id,"reconcile before any new entry");
      if(exit_state==B1_EX_REQUESTED) Diag("RECOVERY_PENDING_MODIFY",IntegerToString((long)pos_ticket),"reconcile broker stop");
   }

   //--- risk
   double RiskPct(const double equity) const { return B1Risk(hwm,equity,dd_stop); }

   void ObserveEquity(const double equity)
   {
      if(!(equity>0.0) || hwm<=0.0) return;
      if(equity>hwm) hwm=equity;
      double dd=(hwm-equity)/hwm;
      bool dirty=false;
      if(dd>max_dd) max_dd=dd;
      if(!dd_stop && B1Risk(hwm,equity,false)<=0.0)
      {
         dd_stop=true; dirty=true;
         CB1Doc f; f.Set("equity",B1F(equity)); f.Set("hwm",B1F(hwm)); f.Set("dd",B1F(dd));
         Emit("STOP_NEW_ENTRIES",false,IntegerToString(last_msc),f);
      }
      if(hwm>saved_hwm) dirty=true;
      if(dirty && trusted) Save();
   }

   void RaiseIncident(const string reason,const bool close_owned)
   {
      incident=true;
      if(incident_id=="") incident_id=reason+"|"+IntegerToString(UtcMsc(last_msc));
      if(close_owned && pos_ticket!=0) close_required=true;
      CB1Doc f; f.Set("reason",reason); f.Set("incident_id",incident_id); f.SetL("close_required",close_required);
      Emit("INCIDENT",false,incident_id,f);
      if(trusted) Save();
      if(close_required) AttemptIncidentClose();
   }

   //--- bars and signals
   void OnBar(const MqlRates &bar,const bool live)
   {
      double atr,rsi,hh,ll; int dir;
      if(ind.count>0 && bar.time<=ind.last_time)
      {
         if(live) Diag("DUPLICATE_BAR",IntegerToString((long)bar.time),"bar already processed");
         return;
      }
      if(!B1IndUpdate(ind,bar,atr,rsi,hh,ll,dir))
      {
         Untrust("INVALID_BAR");
         return;
      }
      if(live && dir!=0)
      {
         if(sig_bar!=0) Diag("SIGNAL_EXPIRED",IntegerToString(sig_bar),"replaced by newer completed bar");
         sig_bar=(long)bar.time; sig_dir=dir; sig_atr=atr;
         CB1Doc f; f.SetL("bar_open_utc_epoch",(long)bar.time-cfg.utc_offset_sec); f.SetL("direction",dir);
         f.Set("atr",B1F(atr)); f.Set("rsi",B1F(rsi)); f.Set("hh30",B1F(hh)); f.Set("ll30",B1F(ll));
         Emit("SIGNAL",false,IntegerToString(sig_bar),f);
      }
      if(trusted && live) Save();
   }

   //--- ticks
   void OnTick()
   {
      double bid,ask; long msc;
      if(!broker.Quote(bid,ask,msc) || !(bid>0.0) || ask<bid) return;
      last_bid=bid; last_ask=ask; last_msc=msc;
      FlushConfirmed();
      ObserveEquity(broker.Equity());
      RollDay();
      if(req_status==B1_REQ_PENDING) ReconcileRequest(false);
      ManagePosition();
      TryEntry();
   }

   void RollDay()
   {
      long d=UtcMsc(last_msc)/86400000;
      if(d!=day) { day=d; day_r=0.0; }
   }

   void ReconcileRequest(const bool immediate)
   {
      B1Position owned[];
      int n=broker.OwnedPositions(owned);
      for(int i=0;i<n;i++)
         if(IsRequestPosition(owned[i])) { Adopt(owned[i]); return; }
      B1Position filled;
      if(broker.FindFilledPosition(req_id,req_order,filled))
      {
         // Filled and closed while unobserved: record the broker's entry deal and close, never resend.
         Adopt(filled);
         return;
      }
      remainder_open=broker.OwnedPendingOrders(req_id);
      if(immediate || last_msc-req_msc<(long)cfg.reconcile_timeout_sec*1000) return;
      if(remainder_open>0) CancelRemainder();
      if(remainder_open>0) return;
      Diag("REQUEST_NO_FILL",req_id,"no broker fill after reconciliation window");
      ClearRequest();
      Save();
   }

   void Adopt(const B1Position &p)
   {
      bool first=pos_identifier!=p.identifier;
      pos_ticket=p.ticket; pos_identifier=p.identifier; pos_dir=p.direction; pos_volume=p.volume; pos_entry=p.price_open;
      pos_sl=p.sl; pos_tp=p.tp;
      pos_r=MathAbs(p.price_open-req_sl); pos_intended_r=MathAbs(req_quote-req_sl);
      double cost=0.0;
      if(broker.EntryCommission(p.identifier,cost)) pos_commission=cost;
      req_status=B1_REQ_FILLED;
      remainder_open=broker.OwnedPendingOrders(req_id);
      if(remainder_open>0) CancelRemainder();
      if(first)
      {
         CB1Doc f; f.Set("request_id",req_id); f.SetL("direction",pos_dir);
         f.Set("volume",B1F(pos_volume)); f.Set("requested_volume",B1F(req_volume));
         f.SetL("partial",pos_volume+1e-12<req_volume); f.Set("fill_price",B1F(pos_entry));
         f.Set("quote_price",B1F(req_quote)); f.Set("sl",B1F(pos_sl)); f.Set("tp",B1F(pos_tp));
         f.Set("position_r_price",B1F(pos_r)); f.Set("intended_r_price",B1F(pos_intended_r));
         f.Set("entry_commission_cost",B1F(pos_commission)); f.Set("risk_budget",B1F(req_budget));
         f.SetL("private_position_ticket",(long)pos_ticket);
         f.SetL("private_position_identifier",(long)pos_identifier);
         Emit("FILL_CONFIRMED",true,req_id,f);
      }
      Save();
      VerifyFillRisk();
   }

   void VerifyFillRisk()
   {
      if(pos_ticket==0 || incident) return;
      if(pos_sl<=0.0) { RaiseIncident("MISSING_PROTECTIVE_SL",true); return; }
      double loss=0.0;
      if(!broker.CalcProfit(pos_dir,pos_volume,pos_entry,pos_sl,loss))
      { RaiseIncident("FILL_RISK_UNVERIFIABLE",true); return; }
      double entry_fee=MathMax(cfg.commission_per_lot*pos_volume,pos_commission);
      double risk=-loss+entry_fee+cfg.exit_fee_per_lot*pos_volume;
      if(risk>req_budget*(1.0+1e-9)+1e-9) RaiseIncident("FILL_RISK_OVER_BUDGET",true);
   }

   // No automatic top-up: an unfilled remainder is cancelled and blocks new risk until gone.
   void CancelRemainder()
   {
      int result=broker.CancelOwnedOrders(req_id);
      CB1Doc f; f.Set("request_id",req_id); f.SetL("orders",remainder_open); f.SetL("result",result);
      Emit("REMAINDER_CANCEL_REQUESTED",false,req_id+"|"+IntegerToString(last_msc),f);
      remainder_open=broker.OwnedPendingOrders(req_id);
   }

   void ManagePosition()
   {
      B1Position owned[];
      int n=broker.OwnedPositions(owned);
      int idx=-1;
      for(int i=0;i<n;i++)
      {
         if(pos_identifier!=0 && owned[i].identifier==pos_identifier) { idx=i; continue; }
         if(req_status==B1_REQ_PENDING && IsRequestPosition(owned[i])) continue;
         if(!incident) RaiseIncident("UNEXPECTED_OWNED_EXPOSURE",false);
      }
      if(pos_ticket!=0 && idx<0) { DetectClose(); return; }
      if(idx<0) return;
      if(pos_ticket!=owned[idx].ticket) { pos_ticket=owned[idx].ticket; Save(); }
      pos_sl=owned[idx].sl; pos_tp=owned[idx].tp;
      if(MathAbs(owned[idx].volume-pos_volume)>1e-9)
      {
         CB1Doc f; f.Set("previous_volume",B1F(pos_volume)); f.Set("volume",B1F(owned[idx].volume));
         Emit("POSITION_VOLUME_CHANGED",false,IntegerToString((long)pos_ticket)+"|"+B1F(owned[idx].volume),f);
         pos_volume=owned[idx].volume;
         pos_entry=owned[idx].price_open;
         pos_r=MathAbs(pos_entry-req_sl);
         double cost=0.0;
         if(!broker.EntryCommission(pos_identifier,cost)) { RaiseIncident("FILL_COST_UNVERIFIABLE",true); }
         else pos_commission=cost;
         Save();
         VerifyFillRisk();
      }
      if(close_required) { AttemptIncidentClose(); return; }
      if(pos_sl<=0.0 && !incident) { RaiseIncident("MISSING_PROTECTIVE_SL",true); return; }
      ManageExit(owned[idx]);
   }

   void DetectClose()
   {
      B1CloseDeal deal;
      if(!broker.CloseDeal(pos_identifier,deal)) return;
      double net=deal.profit+deal.swap+deal.commission-pos_commission;
      double risk_money=0.0, loss=0.0;
      if(broker.CalcProfit(pos_dir,pos_volume,pos_entry,pos_entry-pos_dir*pos_r,loss)) risk_money=-loss;
      double r=risk_money>0 ? net/risk_money : 0.0;
      day_r+=r;
      CB1Doc f; f.Set("request_id",req_id); f.SetL("direction",pos_dir); f.Set("volume",B1F(deal.volume));
      f.Set("entry_price",B1F(pos_entry)); f.Set("exit_price",B1F(deal.price)); f.Set("reason",deal.reason);
      f.Set("gross_profit",B1F(deal.profit)); f.Set("swap",B1F(deal.swap));
      f.Set("exit_commission",B1F(deal.commission)); f.Set("entry_commission_cost",B1F(pos_commission));
      f.Set("net_profit",B1F(net)); f.Set("position_risk_money",B1F(risk_money)); f.Set("net_r",B1F(r));
      f.SetL("exit_state",exit_state); f.Set("day_r",B1F(day_r));
      f.SetL("private_position_ticket",(long)pos_ticket);
      f.SetL("private_position_identifier",(long)pos_identifier);
      string ref=IntegerToString((long)pos_identifier);
      if(day_r<=-2.0) Diag("DAILY_R_TELEMETRY",IntegerToString(day)+(day_r<=-3.0 ? "|-3R" : "|-2R"),"informational; daily hard stop disabled");
      if(close_required) close_required=false;
      ClearPosition(); ClearRequest();
      // A restart must not apply day_r twice for the same closed position.
      Emit("CLOSE_CONFIRMED",true,ref,f);
   }

   void AttemptIncidentClose()
   {
      if(close_attempt_msc!=0 && last_msc-close_attempt_msc<(long)cfg.close_retry_sec*1000) return;
      close_attempt_msc=last_msc;
      int result=broker.ClosePosition(pos_ticket,pos_volume);
      if(result==B1_SEND_DONE) return;
      CB1Doc f; f.Set("incident_id",incident_id); f.SetL("result",result);
      f.SetL("private_position_ticket",(long)pos_ticket);
      Emit("CLOSE_FAILED_CRITICAL",false,incident_id+"|"+IntegerToString(last_msc),f);
   }

   //--- one-shot stop adjustment after +2R (v1.1 only)
   bool TargetStop(const B1Position &p,const B1Spec &spec,double &stop)
   {
      if(cfg.exit_mode==B1_EXIT_ENTRY_BE) { stop=B1Price(pos_entry,spec.tick_size); return true; }
      double unit=0.0;
      if(!broker.CalcProfit(pos_dir,pos_volume,pos_entry,pos_entry+pos_dir*1.0,unit) || unit<=0.0) return false;
      // Spread is already paid through Bid/Ask; only fees and signed swap are covered.
      double need=pos_commission+cfg.exit_fee_per_lot*pos_volume-p.swap;
      double raw=pos_entry+pos_dir*MathMax(need,0.0)/unit;
      double ticks=raw/spec.tick_size;
      stop=(pos_dir>0 ? MathCeil(ticks-1e-7) : MathFloor(ticks+1e-7))*spec.tick_size;
      double covered=0.0;
      for(int k=0;k<3;k++)
      {
         if(!broker.CalcProfit(pos_dir,pos_volume,pos_entry,stop,covered)) return false;
         if(covered>=need-1e-9) return true;
         stop+=pos_dir*spec.tick_size;
      }
      return false;
   }

   void ManageExit(const B1Position &p)
   {
      if(cfg.exit_mode==B1_EXIT_FIXED || pos_r<=0.0) return;
      if(exit_state==B1_EX_CONFIRMED || exit_state==B1_EX_REJECTED || exit_state==B1_EX_SKIPPED) return;
      B1Spec spec;
      if(!broker.Spec(spec)) return;
      string ref=IntegerToString((long)pos_identifier);
      if(exit_state==B1_EX_REQUESTED)
      {
         if(MathAbs(p.sl-exit_sl)<=spec.tick_size*0.5) ConfirmExit(ref);
         else if(last_msc-exit_request_msc>=(long)cfg.reconcile_timeout_sec*1000)
         {
            exit_state=B1_EX_REJECTED;
            Diag("MODIFY_NOT_APPLIED",ref,"broker stop unchanged after reconciliation window");
            Save();
         }
         return;
      }
      double price=pos_dir>0 ? last_bid : last_ask;
      if(exit_state==B1_EX_NONE)
      {
         if(pos_dir*(price-pos_entry)<B1_TRIGGER_R*pos_r) return;
         exit_state=B1_EX_ARMED; exit_armed_msc=last_msc;
         CB1Doc f; f.Set("trigger_price",B1F(price)); f.Set("position_r_price",B1F(pos_r));
         Emit("EXIT_ARMED",false,ref,f);
         Save();
      }
      if(last_msc-exit_armed_msc<(long)cfg.modify_delay_ms) return;
      double stop=0.0;
      if(!TargetStop(p,spec,stop)) { exit_state=B1_EX_SKIPPED; Diag("MODIFY_SKIPPED",ref,"COST_INPUT_UNAVAILABLE"); Save(); return; }
      if(pos_dir*(stop-p.sl)<=spec.tick_size*0.5)
      { exit_state=B1_EX_SKIPPED; Diag("MODIFY_SKIPPED",ref,"NOT_IMPROVING_PROTECTION"); Save(); return; }
      // Wait (no request) while broker stop/freeze geometry forbids the change.
      double gap=pos_dir*(price-stop);
      if(gap<MathMax(spec.stops_level,1)*spec.point) return;
      if(pos_dir*(price-p.sl)<=spec.freeze_level*spec.point) return;
      if(p.tp>0.0 && pos_dir*(p.tp-price)<=spec.freeze_level*spec.point) return;
      exit_state=B1_EX_REQUESTED; exit_sl=stop; exit_request_msc=last_msc;
      CB1Doc f; f.Set("requested_sl",B1F(stop)); f.Set("previous_sl",B1F(p.sl)); f.Set("tp",B1F(p.tp));
      Emit("MODIFY_REQUESTED",false,ref,f);
      if(!Save()) return;
      int result=broker.ModifyStops(pos_ticket,stop,p.tp);
      // Broker state decides: a stop already in place counts even if the retcode says otherwise.
      B1Position owned[];
      int n=broker.OwnedPositions(owned);
      for(int i=0;i<n;i++)
         if(owned[i].ticket==pos_ticket && MathAbs(owned[i].sl-stop)<=spec.tick_size*0.5) { ConfirmExit(ref); return; }
      if(result==B1_SEND_DONE) Diag("MODIFY_UNKNOWN",ref,"done retcode but broker stop differs");
      else if(result==B1_SEND_REJECTED)
      {
         exit_state=B1_EX_REJECTED;
         Diag("MODIFY_REJECTED",ref,"definitive rejection; original stop retained; no retry");
         Save();
      }
      else Diag("MODIFY_UNKNOWN",ref,"ambiguous response; reconcile broker stop");
   }

   void ConfirmExit(const string ref)
   {
      exit_state=B1_EX_CONFIRMED; pos_sl=exit_sl;
      CB1Doc f; f.Set("confirmed_sl",B1F(exit_sl)); f.SetL("exit_mode",cfg.exit_mode);
      f.SetL("private_position_ticket",(long)pos_ticket);
      f.SetL("private_position_identifier",(long)pos_identifier);
      Emit("SL_MODIFIED_CONFIRMED",true,ref,f);
      Save();
   }

   //--- entry
   void Reject(const string reason,CB1Doc &f)
   {
      f.Set("outcome","REJECTED"); f.Set("reason",reason);
      Emit("ADMISSION",false,IntegerToString(sig_bar),f);
      sig_bar=0; sig_dir=0; sig_atr=0.0;
      if(trusted) Save();
   }

   void TryEntry()
   {
      if(sig_bar==0) return;
      long now=last_msc/1000;
      if(now<sig_bar+900) return;
      CB1Doc f;
      f.SetL("signal_bar_open_utc_epoch",sig_bar-cfg.utc_offset_sec); f.SetL("direction",sig_dir);
      f.Set("atr",B1F(sig_atr));
      if(now>=sig_bar+1800) { Reject("SIGNAL_EXPIRED",f); return; }
      double equity=broker.Equity();
      f.Set("equity",B1F(equity)); f.Set("hwm",B1F(hwm));
      if(!trusted) { Reject("STATE_UNTRUSTED:"+block_reason,f); return; }
      if(incident) { Reject("INCIDENT_HALT",f); return; }
      if(dd_stop) { Reject("HARD_DD_STOP",f); return; }
      if(req_status==B1_REQ_PENDING || broker.OwnedPendingOrders("")>0) { Reject("UNRESOLVED_REQUEST",f); return; }
      if(pos_ticket!=0) { Reject("POSITION_OPEN",f); return; }
      B1Position owned[];
      if(broker.OwnedPositions(owned)>0) { Reject("OWNED_EXPOSURE_UNRECONCILED",f); return; }
      if(broker.ForeignExposure()>0) { Reject("FOREIGN_EXPOSURE",f); return; }
      if(!broker.OwnerLock()) { Reject("DUPLICATE_OWNER",f); return; }
      B1Spec spec;
      if(!broker.Spec(spec) || !spec.trade_full || spec.tick_size<=0 || spec.vol_step<=0 || spec.vol_min<=0)
      { Reject("SPEC_UNAVAILABLE",f); return; }
      double risk=RiskPct(equity);
      f.Set("risk_pct",B1F(risk)); f.Set("dd",B1F(hwm>0 ? (hwm-equity)/hwm : 0));
      if(risk<=0.0) { Reject("RISK_TIER_ZERO",f); return; }
      int dir=sig_dir;
      double quote=dir>0 ? last_ask : last_bid;
      double sl=B1Price(quote-dir*sig_atr*B1_SL_ATR,spec.tick_size);
      double dist=MathAbs(quote-sl);
      double tp=B1Price(quote+dir*dist*B1_TARGET_R,spec.tick_size);
      f.Set("quote",B1F(quote)); f.Set("sl",B1F(sl)); f.Set("tp",B1F(tp));
      if(!(dist>0.0) || dir*(quote-sl)<=0) { Reject("INVALID_STOP_DISTANCE",f); return; }
      double unit_loss=0.0;
      if(!broker.CalcProfit(dir,1.0,quote,sl,unit_loss) || unit_loss>=0.0) { Reject("PROFIT_CALC_UNAVAILABLE",f); return; }
      double fee=cfg.commission_per_lot+cfg.exit_fee_per_lot;
      double per_lot=-unit_loss*(1.0+cfg.admission_reserve_r)+fee;
      double budget=equity*risk;
      double raw=budget/per_lot;
      double volume=MathFloor(MathMin(raw,spec.vol_max)/spec.vol_step+1e-10)*spec.vol_step;
      volume=NormalizeDouble(volume,8);
      double min_loss=0.0;
      broker.CalcProfit(dir,spec.vol_min,quote,sl,min_loss);
      f.Set("risk_budget",B1F(budget)); f.Set("raw_volume",B1F(raw)); f.Set("volume",B1F(volume));
      f.Set("minimum_lot_risk",B1F(-min_loss*(1.0+cfg.admission_reserve_r)+fee*spec.vol_min));
      if(volume<spec.vol_min-1e-12) { Reject("RISK_BELOW_MINIMUM_LOT",f); return; }
      double loss=0.0;
      if(!broker.CalcProfit(dir,volume,quote,sl,loss) || -loss*(1.0+cfg.admission_reserve_r)+fee*volume>budget+1e-9)
      { Reject("RISK_BUDGET_EXCEEDED",f); return; }
      double margin=0.0;
      if(!broker.CalcMargin(dir,volume,quote,margin) || margin>broker.MarginFree()) { Reject("INSUFFICIENT_MARGIN",f); return; }
      double bid_side=dir>0 ? last_bid : last_ask;
      if(dir*(bid_side-sl)<spec.stops_level*spec.point || dir*(tp-bid_side)<spec.stops_level*spec.point)
      { Reject("STOP_GEOMETRY",f); return; }
      string check="";
      if(!broker.CheckOrder(dir,volume,quote,sl,tp,check)) { Reject("ORDER_CHECK_FAILED:"+check,f); return; }
      // Durable identity before send: a crash after this line reconciles instead of resending.
      req_status=B1_REQ_PENDING; req_id=cfg.code+"|"+IntegerToString(sig_bar)+"|"+IntegerToString(dir);
      req_dir=dir; req_volume=volume; req_quote=quote; req_sl=sl; req_tp=tp; req_budget=budget; req_msc=last_msc;
      long bar=sig_bar;
      sig_bar=0; sig_dir=0; sig_atr=0.0;
      if(!Save()) { ClearRequest(); f.Set("outcome","REJECTED"); f.Set("reason","STATE_WRITE_FAILED"); Emit("ADMISSION",false,IntegerToString(bar),f); return; }
      f.Set("outcome","SUBMITTED"); f.Set("request_id",req_id);
      Emit("ADMISSION",false,IntegerToString(bar),f);
      ulong order=0;
      int result=broker.SendMarket(dir,volume,quote,sl,tp,req_id,order);
      if(order!=0) { req_order=order; Save(); }
      if(result==B1_SEND_REJECTED)
      {
         Diag("REQUEST_REJECTED",req_id,"definitive broker rejection; no retry for this signal");
         ClearRequest();
         Save();
         return;
      }
      if(result==B1_SEND_UNKNOWN) Diag("REQUEST_UNKNOWN",req_id,"ambiguous response; reconcile before any resubmission");
      ReconcileRequest(true);
   }
};

#endif
