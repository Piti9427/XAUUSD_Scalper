// Native frequency research v1: deterministic public decision boundaries.
#ifndef FREQUENCY_RESEARCH_CORE
#define FREQUENCY_RESEARCH_CORE

enum FRBlock { FR_OK=0, FR_INVALID, FR_VOLUME, FR_RISK, FR_DAILY, FR_BUSY };

bool FRTesterAllowed(const bool tester,const bool usd,const bool costs,const bool utc)
{ return tester && usd && costs && utc; }

int FRAdmit(const double loss,const double equity,const double volume,
            const double minimum,const double step,const double maximum,
            const double day_equity,const int losses,const int loss_limit,const bool busy)
{
   if(!MathIsValidNumber(loss) || loss<=0 || !MathIsValidNumber(equity) || equity<=0 ||
      !MathIsValidNumber(day_equity) || day_equity<=0 || !MathIsValidNumber(volume) ||
      !MathIsValidNumber(minimum) || !MathIsValidNumber(step) || !MathIsValidNumber(maximum) ||
      minimum<=0 || step<=0 || maximum<minimum) return FR_INVALID;
   if(volume!=0.01 || volume<minimum || volume>maximum ||
      MathAbs(volume/step-MathFloor(volume/step+0.5))>1e-8) return FR_VOLUME;
   if(busy) return FR_BUSY;
   if(equity<=day_equity*0.9 || (loss_limit>0 && losses>=loss_limit)) return FR_DAILY;
   if(loss>equity*0.1) return FR_RISK;
   return FR_OK;
}

struct FRBar { long utc; double open,high,low,close; };
struct FRSignal { int direction; double stop_anchor,atr; long decision; };

bool FRBarValid(const FRBar &b)
{
   return b.utc>=0 && MathIsValidNumber(b.open) && MathIsValidNumber(b.high) &&
      MathIsValidNumber(b.low) && MathIsValidNumber(b.close) && b.low>0 &&
      b.high>=MathMax(b.open,b.close) && b.low<=MathMin(b.open,b.close) && b.high>=b.low;
}

// Complete constituents only; no interpolation or current-bar peeking.
class FRAssembler
{
public:
   int duration,step,count;
   long bucket,last;
   bool valid;
   FRBar value;
   void Reset(const int seconds,const int constituent)
   { duration=seconds;step=constituent;count=0;bucket=-1;last=-1;valid=false; }
   bool Push(const FRBar &b,FRBar &sealed)
   {
      if(!FRBarValid(b) || b.utc%step!=0 || b.utc<=last) return false;
      long start=b.utc-b.utc%duration;
      if(start!=bucket)
      { bucket=start;count=0;valid=(b.utc==start);value=b;value.utc=start; }
      else
      {
         if(b.utc!=last+step) valid=false;
         value.high=MathMax(value.high,b.high);value.low=MathMin(value.low,b.low);
         value.close=b.close;
      }
      last=b.utc;count++;
      if(valid && count==duration/step && b.utc+step==bucket+duration)
      { sealed=value;return true; }
      return false;
   }
};

class FRSeries
{
public:
   FRBar bars[100];
   double ema20[100],ema50[100],tr[100],gain[100],loss[100];
   int count;
   double atr,rsi,previous_rsi;
   bool rsi_ready,previous_rsi_ready;
   void Reset() { count=0;atr=0;rsi=50;previous_rsi=50;rsi_ready=false;previous_rsi_ready=false; }
   bool Push(const FRBar &b)
   {
      if(!FRBarValid(b) || (count>0 && b.utc<=bars[0].utc)) return false;
      int n=(int)MathMin(count,99);
      for(int i=n;i>0;i--)
      { bars[i]=bars[i-1];ema20[i]=ema20[i-1];ema50[i]=ema50[i-1];
        tr[i]=tr[i-1];gain[i]=gain[i-1];loss[i]=loss[i-1]; }
      double delta=count>0 ? b.close-bars[1].close : 0;
      tr[0]=b.high-b.low;
      if(count>0) tr[0]=MathMax(tr[0],MathMax(MathAbs(b.high-bars[1].close),MathAbs(b.low-bars[1].close)));
      gain[0]=MathMax(delta,0);loss[0]=MathMax(-delta,0);bars[0]=b;
      ema20[0]=count>0 ? b.close*2.0/21.0+ema20[1]*19.0/21.0 : b.close;
      ema50[0]=count>0 ? b.close*2.0/51.0+ema50[1]*49.0/51.0 : b.close;
      count++;atr=0;
      if(count>=14) { for(int i=0;i<14;i++) atr+=tr[i];atr/=14; }
      previous_rsi=rsi;previous_rsi_ready=rsi_ready;rsi_ready=count>=8;
      if(rsi_ready)
      {
         double up=0,down=0;for(int i=0;i<7;i++) { up+=gain[i];down+=loss[i]; }
         rsi=down==0 ? (up==0 ? 50 : 100) : 100-100/(1+up/down);
      }
      return true;
   }
};

bool FRPullback(const FRBar &previous,const FRBar &current,
                const double prior_fast,const double prior_slow,
                const double fast,const double slow,const double macro,
                const double macro_old,const double macro_close,const double atr,
                FRSignal &signal)
{
   signal.direction=0;
   if(!FRBarValid(previous) || !FRBarValid(current) || current.utc!=previous.utc+300 || atr<=0)
      return false;
   int d=macro_close>macro && macro>macro_old ? 1 :
         (macro_close<macro && macro<macro_old ? -1 : 0);
   bool touched=d==1 ? (previous.low<=prior_fast || previous.low<=prior_slow) :
                           (previous.high>=prior_fast || previous.high>=prior_slow);
   if(d==0 || !touched || d*(previous.close-previous.open)>=0 ||
      d*(current.close-(d==1 ? previous.high : previous.low))<=0 ||
      d*(current.close-fast)<=0 || d*(fast-slow)<=0) return false;
   signal.direction=d;signal.atr=atr;signal.decision=current.utc+300;
   signal.stop_anchor=d==1 ? MathMin(previous.low,current.low)-0.1*atr :
                            MathMax(previous.high,current.high)+0.1*atr;
   return true;
}

class FRSession
{
public:
   int start_minute,count,direction;
   long day,last,break_time;
   double high,low;
   bool valid,used;
   void Reset(const int minute)
   { start_minute=minute;day=-1;last=-1;count=0;direction=0;valid=false;used=false; }
   bool Observe(const FRBar &b,const double atr,const bool eligible,FRSignal &signal)
   {
      signal.direction=0;
      if(!eligible) return false;
      return Push(b,atr,signal);
   }
   bool Push(const FRBar &b,const double atr,FRSignal &signal)
   {
      signal.direction=0;
      long today=b.utc-b.utc%86400;
      if(today!=day)
      { day=today;last=-1;count=0;direction=0;valid=false;used=false;high=0;low=0; }
      long start=day+start_minute*60;
      if(!FRBarValid(b) || b.utc%300!=0 || b.utc<start || b.utc>=start+10800 || used)
         return false;
      if(last<0) valid=(b.utc==start);
      else if(b.utc!=last+300) valid=false;
      last=b.utc;
      if(!valid) return false;
      if(b.utc<start+1800)
      {
         if(count==0) { high=b.high;low=b.low; }
         else { high=MathMax(high,b.high);low=MathMin(low,b.low); }
         count++;return false;
      }
      if(count!=6 || high<=low || atr<=0) return false;
      if(direction==0)
      {
         direction=b.close>high ? 1 : (b.close<low ? -1 : 0);
         if(direction!=0) break_time=b.utc;
         return false;
      }
      if(b.utc>break_time+1800) { used=true;return false; }
      bool retest=direction==1 ? b.low<=high && b.close>high : b.high>=low && b.close<low;
      if(retest && b.utc>break_time)
      {
         used=true;signal.direction=direction;signal.decision=b.utc+300;signal.atr=atr;
         signal.stop_anchor=direction==1 ? b.low-0.1*atr : b.high+0.1*atr;
         return true;
      }
      if((direction==1 && b.close<low) || (direction==-1 && b.close>high)) used=true;
      return false;
   }
};

class FRMacro
{
public:
   int count;
   long end;
   double value;
   void Reset() { count=0;end=-1;value=0; }
   void Push(const FRBar &h4)
   { value=count>0 ? h4.close*2.0/201.0+value*199.0/201.0 : h4.close;count++;end=h4.utc+14400; }
   bool Ready(const long decision) { return count>=200 && decision>=end && decision<end+14400; }
};

bool FRC22(FRSeries &series,const double macro,const bool macro_ready,FRSignal &signal)
{
   signal.direction=0;
   if(series.count<97 || !macro_ready || !MathIsValidNumber(macro) || macro<=0) return false;
   double prior_low=series.bars[1].low;
   for(int i=2;i<=96;i++) prior_low=MathMin(prior_low,series.bars[i].low);
   double close=series.bars[0].close;
   bool sell=close<prior_low && close<series.ema50[0] && series.ema50[0]<series.ema50[4];
   bool buy=series.previous_rsi_ready && series.previous_rsi<25 && series.rsi>=25 &&
      close>series.bars[1].close && close>series.ema50[0] && series.ema50[0]>series.ema50[4];
   int d=sell ? -1 : (buy ? 1 : 0);
   if(d==0 || d*(close-macro)<=0) return false;
   signal.direction=d;signal.atr=series.atr;signal.decision=series.bars[0].utc+900;
   signal.stop_anchor=0;return true;
}

struct FRPlan { int direction; double entry,stop,target; };
double FRGrid(const double price,const double grid,const int direction)
{ return (direction==1 ? MathFloor(price/grid+1e-9) : MathCeil(price/grid-1e-9))*grid; }

bool FRPrepare(const FRSignal &signal,const bool c22,const double bid,const double ask,
               const double grid,FRPlan &plan)
{
   int d=signal.direction;
   if((d!=1 && d!=-1) || !MathIsValidNumber(bid) || !MathIsValidNumber(ask) ||
      bid<=0 || ask<bid || grid<=0 || signal.atr<=0) return false;
   plan.direction=d;plan.entry=d==1 ? ask : bid;
   double raw_stop=c22 ? plan.entry-d*signal.atr*(d==1 ? 1.5 : 2.5) :
                          signal.stop_anchor+(d==-1 ? ask-bid : 0);
   plan.stop=FRGrid(raw_stop,grid,d);
   plan.target=FRGrid(plan.entry+d*2*MathAbs(plan.entry-plan.stop),grid,d);
   return MathIsValidNumber(plan.stop) && plan.stop>0 &&
      d*((d==1 ? bid : ask)-plan.stop)>0 && plan.target>0 && d*(plan.target-plan.entry)>0;
}

enum FRFill { FR_REJECTED=0, FR_PENDING, FR_CONFIRMED, FR_CONTAIN };
int FRFillState(const int retcode,const bool owned,const double volume,const double risk,
                const double budget)
{
   if(owned)
   {
      if(retcode!=10009 || MathAbs(volume-0.01)>1e-8 ||
         !MathIsValidNumber(risk) || risk<=0 || risk>budget) return FR_CONTAIN;
      return FR_CONFIRMED;
   }
   if(retcode==10009 || retcode==10010 || retcode==10008 || retcode==10012 ||
      retcode==10031 || retcode==0) return FR_PENDING;
   return FR_REJECTED;
}

struct FRMonth { int entries,winners; double cash; };
void FRBookCash(FRMonth &month,const double profit,const double commission,
                const double swap,const double fee)
{ month.cash+=profit+commission+swap+fee; }
void FRBookClosed(FRMonth &entry_month,const double complete_net)
{ if(complete_net>0) entry_month.winners++; }

struct FRSummary { int full,positive,entries; double worst,total; };
void FRSummaryReset(FRSummary &s)
{ s.full=0;s.positive=0;s.entries=0;s.worst=0;s.total=0; }
bool FRWindowFull(const long start,const long next,const long from,const long to)
{ return start>=from && next<=to && start<next; }
void FRAccumulate(FRSummary &s,const FRMonth &month,const bool full)
{
   s.total+=month.cash;
   if(!full) return;
   if(s.full==0 || month.cash<s.worst) s.worst=month.cash;
   s.full++;s.entries+=month.entries;if(month.cash>0) s.positive++;
}

bool FRReportReady(const bool pending,const int positions,const int orders)
{ return !pending && positions==0 && orders==0; }

enum FRMonthScope { FR_UNOBSERVED_MONTH=0, FR_PARTIAL_MONTH, FR_FULL_MONTH };
int FRObservedScope(const long start,const long next,const long first,const long last)
{
   if(first<=0 || last<first || last<start || first>=next) return FR_UNOBSERVED_MONTH;
   return first<=start && last>=next ? FR_FULL_MONTH : FR_PARTIAL_MONTH;
}

#endif
