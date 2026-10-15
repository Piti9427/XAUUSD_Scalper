// B1-FINAL confirmed-event JSONL adapter, shared by EA and fault-injection tests.
#ifndef B1_FINAL_OUTBOX
#define B1_FINAL_OUTBOX
#include "B1FinalEngine.mqh"

string JsonEscape(string s)
{
   StringReplace(s,"\\","\\\\"); StringReplace(s,"\"","\\\"");
   StringReplace(s,"\r","\\r"); StringReplace(s,"\n","\\n"); StringReplace(s,"\t","\\t");
   return s;
}

// Engine numbers come from IntegerToString/DoubleToString: optional '-', digits, at most one '.'.
bool IsNumber(const string s)
{
   int n=StringLen(s), digits=0, dots=0;
   for(int i=0;i<n;i++)
   {
      ushort c=StringGetCharacter(s,i);
      if(c>='0' && c<='9') digits++;
      else if(c=='.' && dots==0 && digits>0) dots++;
      else if(!(c=='-' && i==0)) return false;
   }
   return digits>0 && StringGetCharacter(s,n-1)!='.';
}

string IsoUtc(const long utc_msc)
{
   string t=TimeToString((datetime)(utc_msc/1000),TIME_DATE|TIME_SECONDS);
   StringReplace(t,".","-"); StringReplace(t," ","T");
   return t+"."+StringFormat("%03d",(int)(utc_msc%1000))+"Z";
}

// Durable append-only outbox; each line is flushed and closed before returning.
class CB1JsonlSink : public CB1Sink
{
public:
   string file,version,symbol;
   int    failed;
   CB1JsonlSink() { failed=0; }
   virtual uint WriteRecord(const int handle,const string record) { return FileWriteString(handle,record); }
   virtual bool Emit(const string id,const string type,const bool confirmed,const long utc,CB1Doc &f)
   {
      string pub="",prv="";
      for(int i=0;i<ArraySize(f.keys);i++)
      {
         string v=IsNumber(f.values[i]) ? f.values[i] : "\""+JsonEscape(f.values[i])+"\"";
         if(StringFind(f.keys[i],"private_")==0)
            prv+=(prv=="" ? "" : ",")+"\""+StringSubstr(f.keys[i],8)+"\":"+v;
         else pub+=(pub=="" ? "" : ",")+"\""+JsonEscape(f.keys[i])+"\":"+v;
      }
      string line="{\"event_id\":\""+JsonEscape(id)+"\",\"type\":\""+type+"\",\"confirmed\":"+(confirmed ? "true" : "false")+
                  ",\"utc_ms\":"+IntegerToString(utc)+",\"utc\":\""+IsoUtc(utc)+"\",\"strategy\":\"B1-FINAL\",\"version\":\""+version+
                  "\",\"symbol\":\""+symbol+"\",\"fields\":{"+pub+"},\"private\":{"+prv+"}}";
      int h=FileOpen(file,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
      if(h==INVALID_HANDLE)
      {
         // Engine retains confirmed event intent in durable state and retries later.
         failed++;
         Print("OUTBOX_WRITE_FAILED ",GetLastError()," ",line);
         return false;
      }
      // Stable ID makes append-before-state-ack crashes safe to replay.
      string prefix="{\"event_id\":\""+JsonEscape(id)+"\",";
      while(!FileIsEnding(h))
      {
         ulong before=FileTell(h);
         string existing=FileReadString(h);
         if(existing=="") continue;
         // Text reads strip LF/CRLF. No delimiter means consumer cannot see this record.
         if(FileTell(h)-before<=(ulong)StringLen(existing)) { failed++; FileClose(h); return false; }
         if(confirmed && StringFind(existing,prefix)==0)
         {
            bool same=existing==line;
            FileClose(h);
            if(!same) failed++;
            return same;
         }
         // Never append behind a torn record. Preserve evidence and pending event.
         if(StringSubstr(existing,StringLen(existing)-1)!="}") { failed++; FileClose(h); return false; }
      }
      FileSeek(h,0,SEEK_END);
      ResetLastError();
      string record=line+"\r\n"; // Explicit TXT delimiter: byte-count check includes CRLF.
      uint written=WriteRecord(h,record);
      FileFlush(h); FileClose(h);
      if(written!=(uint)StringLen(record) || GetLastError()!=0) { failed++; return false; }
      return true;
   }
};

#endif
