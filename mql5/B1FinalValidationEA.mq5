#property strict
#property version "1.000"
#property description "B1-FINAL-v1 offline parity probe. No orders. Tester only."
#include "B1FinalCore.mqh"

input string ReferenceBars="B1_FINAL_parity_input.csv";
input string IndicatorOutput="B1_FINAL_mql_indicators.csv";
input string RiskOutput="B1_FINAL_mql_risk.csv";

string Number(const double value)
{
   return value==EMPTY_VALUE ? "" : DoubleToString(value,16);
}

int OnInit()
{
   // Refuse attachment to a live/demo chart. This probe is not a trading EA.
   if(!MQLInfoInteger(MQL_TESTER))
   { Print("NO_GO: tester-only parity probe");return INIT_FAILED; }
   int source=FileOpen(ReferenceBars,FILE_READ|FILE_CSV|FILE_ANSI,',');
   if(source==INVALID_HANDLE) { Print("Missing reference CSV: ",GetLastError());return INIT_FAILED; }
   string expected[]={"bar_open_epoch","open","high","low","close"};
   for(int col=0;col<5;col++)
      if(FileReadString(source)!=expected[col]) { FileClose(source);return INIT_FAILED; }
   MqlRates bars[];
   int n=0;
   while(!FileIsEnding(source))
   {
      string stamp=FileReadString(source);
      if(stamp=="" && FileIsEnding(source)) break;
      MqlRates bar={};
      bar.time=(datetime)StringToInteger(stamp);
      bar.open=StringToDouble(FileReadString(source));
      bar.high=StringToDouble(FileReadString(source));
      bar.low=StringToDouble(FileReadString(source));
      bar.close=StringToDouble(FileReadString(source));
      if(bar.time<=0 || ((long)bar.time)%900!=0 ||
         (n>0 && bar.time<=bars[n-1].time) ||
         bar.open<=0 || bar.low<=0 || bar.close<=0 ||
         bar.high<MathMax(bar.open,bar.close) || bar.low>MathMin(bar.open,bar.close))
      { FileClose(source);Print("Invalid reference bar");return INIT_FAILED; }
      ArrayResize(bars,n+1);bars[n]=bar;n++;
   }
   FileClose(source);
   double atr[],rsi[],hh[],ll[];int direction[];
   if(!B1Indicators(bars,atr,rsi,hh,ll,direction)) return INIT_FAILED;
   int output=FileOpen(IndicatorOutput,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(output==INVALID_HANDLE) return INIT_FAILED;
   FileWrite(output,"bar_open_epoch","atr","rsi","hh30","ll30","direction");
   for(int i=0;i<n;i++)
      FileWrite(output,(long)bars[i].time,Number(atr[i]),Number(rsi[i]),Number(hh[i]),Number(ll[i]),direction[i]);
   FileFlush(output);FileClose(output);
   output=FileOpen(RiskOutput,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(output==INVALID_HANDLE) return INIT_FAILED;
   FileWrite(output,"dd_pct","risk_pct");
   double boundaries[]={2.9999,3.0,5.9999,6.0,8.9999,9.0,11.9999,12.0};
   for(int i=0;i<ArraySize(boundaries);i++)
      FileWrite(output,Number(boundaries[i]),Number(B1Risk(10000.0,10000.0*(1-boundaries[i]/100.0),false)));
   FileFlush(output);FileClose(output);
   Print("B1-FINAL-v1 parity export: ",n," bars. NO ORDER API.");
   return INIT_SUCCEEDED;
}

void OnTick() {}
