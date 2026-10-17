#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
using datetime=std::int64_t;
inline double MathAbs(double x) { return std::abs(x); }
inline double MathMin(double a,double b) { return std::min(a,b); }
inline double MathMax(double a,double b) { return std::max(a,b); }
inline double MathFloor(double x) { return std::floor(x); }
inline double MathCeil(double x) { return std::ceil(x); }
inline bool MathIsValidNumber(double x) { return std::isfinite(x); }
#include "FrequencyResearchCore.mqh"
int main() {
    FRSeries series;series.Reset();FRAssembler h4;h4.Reset(14400,900);
    FRMacro macro;macro.Reset();FRBar bar,sealed;FRSignal signal;
    std::cout << std::setprecision(17);
    while(std::cin >> bar.utc >> bar.open >> bar.high >> bar.low >> bar.close) {
        if(!series.Push(bar)) return 2;
        if(h4.Push(bar,sealed)) macro.Push(sealed);
        bool ready=macro.Ready(bar.utc+900);
        FRC22(series,macro.value,ready,signal);
        std::cout << signal.direction << ' ' << series.atr << ' ' << series.rsi << ' '
                  << series.ema50[0] << ' ' << ready << ' ' << macro.value << '\n';
    }
}
