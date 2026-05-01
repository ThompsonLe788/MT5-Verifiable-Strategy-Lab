//+------------------------------------------------------------------+
//| AlertManager.mqh — Throttled alerts, 3-level severity           |
//+------------------------------------------------------------------+
#pragma once

enum ENUM_ALERT_LEVEL { ALERT_WARNING=0, ALERT_RISK=1, ALERT_CRITICAL=2 };

//+------------------------------------------------------------------+
class CAlertManager
{
private:
   struct AlertRecord
   {
      string  key;
      datetime lastSent;
   };

   AlertRecord m_records[32];
   int         m_count;
   int         m_throttleSec;   // minimum interval between same alerts

   int FindRecord(const string key)
   {
      for(int i = 0; i < m_count; i++)
         if(m_records[i].key == key) return i;
      return -1;
   }

   bool CanSend(const string key)
   {
      int idx = FindRecord(key);
      if(idx < 0)
      {
         if(m_count < 32)
         {
            m_records[m_count].key      = key;
            m_records[m_count].lastSent = 0;
            m_count++;
         }
         return true;
      }
      return (TimeCurrent() - m_records[idx].lastSent) >= m_throttleSec;
   }

   void MarkSent(const string key)
   {
      int idx = FindRecord(key);
      if(idx >= 0) m_records[idx].lastSent = TimeCurrent();
   }

public:
   CAlertManager() : m_count(0), m_throttleSec(60) {}

   void Init(int throttleSeconds = 60) { m_throttleSec = throttleSeconds; }

   void Send(ENUM_ALERT_LEVEL level, const string message, const string key = "")
   {
      string alertKey = (key == "") ? message : key;
      if(!CanSend(alertKey)) return;

      string prefix = "";
      switch(level)
      {
         case ALERT_WARNING:  prefix = "[WARNING] ";  break;
         case ALERT_RISK:     prefix = "[RISK]    ";  break;
         case ALERT_CRITICAL: prefix = "[CRITICAL] "; break;
      }

      Print(prefix, message);
      if(level == ALERT_CRITICAL) Alert(prefix + message);

      MarkSent(alertKey);
   }

   void Warning (const string msg, const string key = "") { Send(ALERT_WARNING,  msg, key); }
   void Risk    (const string msg, const string key = "") { Send(ALERT_RISK,     msg, key); }
   void Critical(const string msg, const string key = "") { Send(ALERT_CRITICAL, msg, key); }

   void ResetKey(const string key)
   {
      int idx = FindRecord(key);
      if(idx >= 0) m_records[idx].lastSent = 0;
   }
};
