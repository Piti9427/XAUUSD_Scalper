#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <string>
using string = std::string;
using datetime = std::int64_t;
inline double MathAbs(double x) { return std::abs(x); }
inline double MathMin(double a,double b) { return std::min(a,b); }
inline double MathMax(double a,double b) { return std::max(a,b); }
inline double MathFloor(double x) { return std::floor(x); }
inline double MathCeil(double x) { return std::ceil(x); }
inline bool MathIsValidNumber(double x) { return std::isfinite(x); }
#include "FrequencyResearchCases.mqh"
void FRCheck(bool ok,const string &name) {
    std::cout << (ok ? "PASS " : "FAIL ") << name << '\n';
    if(!ok) ++fr_failures;
}
int main() { FRRunCases(); return fr_failures ? 1 : 0; }
