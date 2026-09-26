// B1-FINAL-v1 deterministic core. No order submission or alpha inputs.
#ifndef B1_FINAL_CORE
#define B1_FINAL_CORE

int B1Direction(const double close,const double hh,const double ll,
                const double rsi,const bool ready)
{
   if(!ready) return 0;
   if(close>hh && rsi<=75.0) return 1;
   if(close<ll && rsi>=25.0) return -1;
   return 0;
}

double B1Risk(const double hwm,const double equity,const bool stopped)
{
   if(stopped || hwm<=0.0) return 0.0;
   if(equity>hwm*0.97) return 0.01;
   if(equity>hwm*0.94) return 0.0075;
   if(equity>hwm*0.91) return 0.005;
   if(equity>hwm*0.88) return 0.0025;
   return 0.0;
}

void B1Observe(const double equity,double &hwm,bool &stopped)
{
   hwm=MathMax(hwm,equity);
   if(equity<=hwm*0.88) stopped=true;
}

double B1Price(const double value,const double tick_size)
{
   return MathFloor(value/tick_size+0.5)*tick_size;
}

// Pure batch recursion with a fixed oldest-bar seed, same as Python oracle.
bool B1Indicators(const MqlRates &bars[],double &atr[],double &rsi[],
                  double &hh[],double &ll[],int &direction[])
{
   int n=ArraySize(bars);
   if(n<1) return false;
   ArrayResize(atr,n);ArrayResize(rsi,n);ArrayResize(hh,n);
   ArrayResize(ll,n);ArrayResize(direction,n);
   double sum_tr=0.0,sum_gain=0.0,sum_loss=0.0,gain=0.0,loss=0.0;
   for(int i=0;i<n;i++)
   {
      atr[i]=EMPTY_VALUE;rsi[i]=EMPTY_VALUE;
      hh[i]=EMPTY_VALUE;ll[i]=EMPTY_VALUE;direction[i]=0;
      double tr=bars[i].high-bars[i].low;
      double delta=0.0;
      if(i>0)
      {
         tr=MathMax(tr,MathMax(MathAbs(bars[i].high-bars[i-1].close),
                             MathAbs(bars[i].low-bars[i-1].close)));
         delta=bars[i].close-bars[i-1].close;
      }
      if(i<14)
      {
         sum_tr+=tr;sum_gain+=MathMax(delta,0.0);sum_loss+=MathMax(-delta,0.0);
         if(i==13) { atr[i]=sum_tr/14.0;gain=sum_gain/14.0;loss=sum_loss/14.0; }
      }
      else
      {
         atr[i]=(atr[i-1]*13.0+tr)/14.0;
         gain=(gain*13.0+MathMax(delta,0.0))/14.0;
         loss=(loss*13.0+MathMax(-delta,0.0))/14.0;
      }
      if(i>=13)
         rsi[i]=(loss==0.0 ? (gain==0.0 ? 50.0 : 100.0) : 100.0-100.0/(1.0+gain/loss));
      if(i>=30)
      {
         hh[i]=bars[i-30].high;ll[i]=bars[i-30].low;
         for(int j=i-29;j<i;j++)
         { hh[i]=MathMax(hh[i],bars[j].high);ll[i]=MathMin(ll[i],bars[j].low); }
      }
      direction[i]=B1Direction(bars[i].close,hh[i],ll[i],rsi[i],i>=99);
   }
   return true;
}

// Broker-dependent sizing/preflight helper; no OrderSend call.
bool B1Volume(const string symbol,const ENUM_ORDER_TYPE side,const double entry,
              const double stop,const double equity,const double risk,
              double &raw,double &volume,string &reason)
{
   double minimum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   double maximum=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double unit_loss=0.0;
   if(risk<=0.0 || equity<=0.0 || minimum<=0.0 || step<=0.0 || maximum<minimum ||
      !OrderCalcProfit(side,symbol,1.0,entry,stop,unit_loss) || unit_loss>=0.0)
   { reason="INVALID_SIZING_INPUT";return false; }
   double budget=equity*risk;
   raw=budget/MathAbs(unit_loss);
   volume=MathFloor(MathMin(raw,maximum)/step)*step;
   if(volume<minimum) { reason="RISK_BELOW_MINIMUM_LOT";return false; }
   double actual_loss=0.0;
   if(!OrderCalcProfit(side,symbol,volume,entry,stop,actual_loss) ||
      actual_loss>=0.0 || MathAbs(actual_loss)>budget)
   { reason="RISK_BUDGET_EXCEEDED";return false; }
   double margin=0.0;
   if(!OrderCalcMargin(side,symbol,volume,entry,margin) ||
      margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE))
   { reason="INSUFFICIENT_MARGIN";return false; }
   reason="SIZING_ONLY_NOT_ORDER_APPROVAL";
   return true;
}

#endif
