// Execute actual native detector core over immutable completed UTC M1 inputs.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <string>
inline double MathAbs(double x) { return std::abs(x); }
inline double MathMin(double a,double b) { return std::min(a,b); }
inline double MathMax(double a,double b) { return std::max(a,b); }
inline double MathFloor(double x) { return std::floor(x); }
inline double MathCeil(double x) { return std::ceil(x); }
inline bool MathIsValidNumber(double x) { return std::isfinite(x); }
#include "FrequencyResearchCore.mqh"
void output(int id,const FRBar& bar,double atr,const FRSignal& signal,bool found,bool eligible,
            bool c22,double bid,double ask,double grid) {
    FRPlan plan{};bool valid=found && eligible && FRPrepare(signal,c22,bid,ask,grid,plan);
    std::cout << id << ',' << bar.utc << ',' << bar.open << ',' << bar.high << ','
              << bar.low << ',' << bar.close << ',' << atr << ',' << (valid?signal.direction:0)
              << ',' << (found?signal.direction:0) << ',' << (found?signal.stop_anchor:0)
              << ',' << plan.entry << ',' << plan.stop << ',' << plan.target << '\n';
}
int main(int argc,char** argv) {
    if(argc!=4) return 2;
    long from=std::stol(argv[1]),to=std::stol(argv[2]);double grid=std::stod(argv[3]);
    FRAssembler m5,m15,h1,h4;m5.Reset(300,60);m15.Reset(900,60);h1.Reset(3600,60);h4.Reset(14400,900);
    FRSeries fast,hour,c22;fast.Reset();hour.Reset();c22.Reset();FRMacro macro;macro.Reset();
    FRSession sessions[3][2];for(int i=0;i<3;i++) { sessions[i][0].Reset(360+i*60);sessions[i][1].Reset(720+i*60); }
    FRBar minute,a,b,c,d;long quote_ms;double bid,ask;
    std::cout << std::setprecision(17);
    while(std::cin >> minute.utc >> minute.open >> minute.high >> minute.low >> minute.close >> quote_ms >> bid >> ask) {
        if(!FRBarValid(minute)) return 3;
        bool eligible=quote_ms>=from*1000 && quote_ms<to*1000 && quote_ms/60000==(minute.utc+60)/60;
        if(h1.Push(minute,a)) hour.Push(a);
        if(m5.Push(minute,b)) {
            fast.Push(b);FRSignal signal{};bool found=false;
            if(fast.count>=54 && hour.count>=54 && b.utc+300<hour.bars[0].utc+7200)
                found=FRPullback(fast.bars[1],fast.bars[0],fast.ema20[1],fast.ema50[1],fast.ema20[0],fast.ema50[0],
                                 hour.ema50[0],hour.ema50[4],hour.bars[0].close,fast.atr,signal);
            output(0,b,fast.atr,signal,found,eligible,false,bid,ask,grid);
            for(int i=0;i<3;i++) {
                found=false;FRSignal chosen{};
                for(int j=0;j<2;j++) { FRSignal candidate{};if(sessions[i][j].Observe(b,fast.atr,eligible,candidate)) { chosen=candidate;found=true; } }
                output(i+1,b,fast.atr,chosen,found,eligible,false,bid,ask,grid);
            }
        }
        if(m15.Push(minute,c)) {
            c22.Push(c);if(h4.Push(c,d)) macro.Push(d);FRSignal signal{};
            bool found=FRC22(c22,macro.value,macro.Ready(c.utc+900),signal);
            output(4,c,c22.atr,signal,found,eligible,true,bid,ask,grid);
        }
    }
}
