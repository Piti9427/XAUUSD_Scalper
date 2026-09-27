// B1-FINAL incremental indicators, durable state and integrity-checked storage.
// No order submission.
#ifndef B1_FINAL_STATE
#define B1_FINAL_STATE
#include "B1FinalCore.mqh"

#define B1_STATE_SCHEMA 1

union B1Bits { double d; long l; };

string B1DoubleBits(const double value) { B1Bits b; b.d=value; return IntegerToString(b.l); }
double B1BitsDouble(const string text) { B1Bits b; b.l=StringToInteger(text); return b.d; }

ulong B1Fnv(const string text)
{
   ulong h=0xcbf29ce484222325;
   int n=StringLen(text);
   for(int i=0;i<n;i++) { h^=(ulong)StringGetCharacter(text,i); h*=0x100000001b3; }
   return h;
}

//--- key=value document with exact double encoding
class CB1Doc
{
public:
   string keys[];
   string values[];
   void Clear() { ArrayResize(keys,0); ArrayResize(values,0); }
   void Set(const string key,const string value)
   {
      int i=Find(key);
      if(i<0) { i=ArraySize(keys); ArrayResize(keys,i+1); ArrayResize(values,i+1); keys[i]=key; }
      values[i]=value;
   }
   void SetL(const string key,const long value) { Set(key,IntegerToString(value)); }
   void SetD(const string key,const double value) { Set(key,B1DoubleBits(value)); }
   int Find(const string key) const
   {
      for(int i=0;i<ArraySize(keys);i++) if(keys[i]==key) return i;
      return -1;
   }
   bool Has(const string key) const { return Find(key)>=0; }
   string S(const string key) const { int i=Find(key); return i<0 ? "" : values[i]; }
   long L(const string key) const { return StringToInteger(S(key)); }
   double D(const string key) const { return B1BitsDouble(S(key)); }
   string Body() const
   {
      string out="";
      for(int i=0;i<ArraySize(keys);i++) out+=keys[i]+"="+values[i]+"\n";
      return out;
   }
   string Serialize() const
   {
      string body=Body();
      return body+"checksum="+IntegerToString((long)B1Fnv(body))+"\n";
   }
   // False on any structural or checksum error: caller must fail closed.
   bool Parse(const string text)
   {
      Clear();
      int at=StringFind(text,"checksum=");
      if(at<0) return false;
      string body=StringSubstr(text,0,at);
      string tail=StringSubstr(text,at+9);
      StringTrimRight(tail);
      if(StringFind(tail,"\n")>=0 || tail!=IntegerToString((long)B1Fnv(body))) return false;
      string lines[];
      int n=StringSplit(body,'\n',lines);
      for(int i=0;i<n;i++)
      {
         if(lines[i]=="") continue;
         int eq=StringFind(lines[i],"=");
         if(eq<=0) return false;
         string key=StringSubstr(lines[i],0,eq);
         if(Has(key)) return false;
         Set(key,StringSubstr(lines[i],eq+1));
      }
      return true;
   }
};

//--- incremental indicators equal to B1Indicators batch recursion
#define B1_DONCHIAN 30
#define B1_PERIOD 14
#define B1_WARMUP 100

struct B1IndState
{
   long     count;
   datetime last_time;
   double   last_close;
   double   sum_tr,sum_gain,sum_loss;
   double   atr,gain,loss;
   double   highs[B1_DONCHIAN];
   double   lows[B1_DONCHIAN];
};

void B1IndReset(B1IndState &s)
{
   s.count=0; s.last_time=0; s.last_close=0.0;
   s.sum_tr=0.0; s.sum_gain=0.0; s.sum_loss=0.0;
   s.atr=0.0; s.gain=0.0; s.loss=0.0;
   ArrayInitialize(s.highs,0.0); ArrayInitialize(s.lows,0.0);
}

bool B1BarValid(const MqlRates &bar)
{
   return bar.time>0 && ((long)bar.time)%900==0 && bar.open>0 && bar.low>0 && bar.close>0 &&
          bar.high>=MathMax(bar.open,bar.close) && bar.low<=MathMin(bar.open,bar.close);
}

// Consumes one completed bar. Outputs EMPTY_VALUE when not yet defined.
bool B1IndUpdate(B1IndState &s,const MqlRates &bar,double &atr,double &rsi,
                 double &hh,double &ll,int &direction)
{
   atr=EMPTY_VALUE; rsi=EMPTY_VALUE; hh=EMPTY_VALUE; ll=EMPTY_VALUE; direction=0;
   if(!B1BarValid(bar) || (s.count>0 && bar.time<=s.last_time)) return false;
   long i=s.count;
   double tr=bar.high-bar.low, delta=0.0;
   if(i>0)
   {
      tr=MathMax(tr,MathMax(MathAbs(bar.high-s.last_close),MathAbs(bar.low-s.last_close)));
      delta=bar.close-s.last_close;
   }
   if(i<B1_PERIOD)
   {
      s.sum_tr+=tr; s.sum_gain+=MathMax(delta,0.0); s.sum_loss+=MathMax(-delta,0.0);
      if(i==B1_PERIOD-1) { s.atr=s.sum_tr/14.0; s.gain=s.sum_gain/14.0; s.loss=s.sum_loss/14.0; }
   }
   else
   {
      s.atr=(s.atr*13.0+tr)/14.0;
      s.gain=(s.gain*13.0+MathMax(delta,0.0))/14.0;
      s.loss=(s.loss*13.0+MathMax(-delta,0.0))/14.0;
   }
   if(i>=B1_PERIOD-1)
   {
      atr=s.atr;
      rsi=(s.loss==0.0 ? (s.gain==0.0 ? 50.0 : 100.0) : 100.0-100.0/(1.0+s.gain/s.loss));
   }
   if(i>=B1_DONCHIAN)
   {
      // Ring holds the previous 30 completed bars; the signal bar is excluded.
      hh=s.highs[0]; ll=s.lows[0];
      for(int j=1;j<B1_DONCHIAN;j++) { hh=MathMax(hh,s.highs[j]); ll=MathMin(ll,s.lows[j]); }
   }
   direction=B1Direction(bar.close,hh,ll,rsi,i>=B1_WARMUP-1);
   int slot=(int)(i%B1_DONCHIAN);
   s.highs[slot]=bar.high; s.lows[slot]=bar.low;
   s.last_close=bar.close; s.last_time=bar.time; s.count=i+1;
   return true;
}

void B1IndSave(const B1IndState &s,CB1Doc &doc)
{
   doc.SetL("ind_count",s.count); doc.SetL("ind_last_time",(long)s.last_time);
   doc.SetD("ind_last_close",s.last_close);
   doc.SetD("ind_sum_tr",s.sum_tr); doc.SetD("ind_sum_gain",s.sum_gain); doc.SetD("ind_sum_loss",s.sum_loss);
   doc.SetD("ind_atr",s.atr); doc.SetD("ind_gain",s.gain); doc.SetD("ind_loss",s.loss);
   for(int j=0;j<B1_DONCHIAN;j++)
   { doc.SetD("ind_h"+IntegerToString(j),s.highs[j]); doc.SetD("ind_l"+IntegerToString(j),s.lows[j]); }
}

bool B1IndLoad(B1IndState &s,const CB1Doc &doc)
{
   if(!doc.Has("ind_count") || !doc.Has("ind_l29")) return false;
   s.count=doc.L("ind_count"); s.last_time=(datetime)doc.L("ind_last_time");
   s.last_close=doc.D("ind_last_close");
   s.sum_tr=doc.D("ind_sum_tr"); s.sum_gain=doc.D("ind_sum_gain"); s.sum_loss=doc.D("ind_sum_loss");
   s.atr=doc.D("ind_atr"); s.gain=doc.D("ind_gain"); s.loss=doc.D("ind_loss");
   for(int j=0;j<B1_DONCHIAN;j++)
   { s.highs[j]=doc.D("ind_h"+IntegerToString(j)); s.lows[j]=doc.D("ind_l"+IntegerToString(j)); }
   return s.count>=0 && (s.count==0 || s.last_time>0);
}

//--- storage seam
class CB1Store
{
public:
   virtual bool Load(string &text)=0;   // false when absent
   virtual bool Save(const string text)=0;
};

class CB1FileStore : public CB1Store
{
   string m_name;
public:
   CB1FileStore(const string name) { m_name=name; }
   virtual bool Load(string &text)
   {
      if(!FileIsExist(m_name)) return false;
      int h=FileOpen(m_name,FILE_READ|FILE_BIN);
      if(h==INVALID_HANDLE) return false;
      uchar raw[];
      FileReadArray(h,raw,0,(int)FileSize(h));
      FileClose(h);
      text=CharArrayToString(raw,0,WHOLE_ARRAY,CP_UTF8);
      return true;
   }
   // Write temp then rename so a crash leaves either the old or the new file.
   virtual bool Save(const string text)
   {
      string temp=m_name+".tmp";
      int h=FileOpen(temp,FILE_WRITE|FILE_BIN);
      if(h==INVALID_HANDLE) return false;
      uchar raw[];
      int n=StringToCharArray(text,raw,0,WHOLE_ARRAY,CP_UTF8);
      uint written=FileWriteArray(h,raw,0,n>0 ? n-1 : 0);
      FileFlush(h); FileClose(h);
      if((int)written!=(n>0 ? n-1 : 0)) return false;
      return FileMove(temp,0,m_name,FILE_REWRITE);
   }
};

class CB1MemoryStore : public CB1Store
{
public:
   string text;
   bool   present;
   int    saves;
   bool   fail_save;
   CB1MemoryStore() { present=false; saves=0; fail_save=false; text=""; }
   virtual bool Load(string &out) { if(!present) return false; out=text; return true; }
   virtual bool Save(const string value)
   { if(fail_save) return false; text=value; present=true; saves++; return true; }
};

#endif
