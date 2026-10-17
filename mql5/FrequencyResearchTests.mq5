#property strict
#property version "1.000"
#property description "Frequency research public-boundary tests. Tester only; no order APIs."
#include "FrequencyResearchCases.mqh"

void FRCheck(bool ok,const string &name)
{
   Print(ok ? "PASS " : "FAIL ",name);
   if(!ok) fr_failures++;
}

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER)) return INIT_FAILED;
   FRRunCases();
   Print("FR_TEST_RESULT failures=",fr_failures);
   return fr_failures==0 ? INIT_SUCCEEDED : INIT_FAILED;
}
void OnTick() {}
double OnTester() { return fr_failures==0 ? 1.0 : -1.0; }
