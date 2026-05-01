//+------------------------------------------------------------------+
//| Logger.mqh — Centralized logging to CSV files                   |
//+------------------------------------------------------------------+
#pragma once

//--- Log levels
enum ENUM_LOG_LEVEL { LOG_DEBUG=0, LOG_INFO=1, LOG_WARNING=2, LOG_ERROR=3 };

//+------------------------------------------------------------------+
class CLogger
{
private:
   string   m_symbol;
   string   m_strategy;
   string   m_decision_file;
   string   m_error_file;
   string   m_trade_file;
   bool     m_initialized;

   void     WriteCSV(const string file, const string line)
   {
      int h = FileOpen(file, FILE_WRITE|FILE_READ|FILE_CSV|FILE_COMMON|FILE_ANSI);
      if(h == INVALID_HANDLE) return;
      FileSeek(h, 0, SEEK_END);
      FileWrite(h, line);
      FileClose(h);
   }

   string   Now() { return TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS); }

public:
   CLogger() : m_initialized(false) {}

   void Init(const string symbol, const string strategy,
             const string prefix = "QT")
   {
      m_symbol        = symbol;
      m_strategy      = strategy;
      m_decision_file = prefix + "_decision_log.csv";
      m_error_file    = prefix + "_error_log.csv";
      m_trade_file    = prefix + "_trade_log.csv";
      m_initialized   = true;

      // Write headers if files are new
      if(!FileIsExist(m_decision_file, FILE_COMMON))
         WriteCSV(m_decision_file,
            "ts,symbol,strategy,signal,decision,reason,risk_pct,spread,session,tf1,tf2,tf3");
      if(!FileIsExist(m_error_file, FILE_COMMON))
         WriteCSV(m_error_file,
            "ts,symbol,strategy,action,error_code,error_text");
      if(!FileIsExist(m_trade_file, FILE_COMMON))
         WriteCSV(m_trade_file,
            "timestamp,symbol,strategy,direction,entry,sl,tp,exit,profit,r_multiple,commission,swap,spread");
   }

   //--- Decision log
   void LogDecision(const string signal,
                    const string decision,
                    const string reason,
                    double riskPct,
                    int spread,
                    const string session,
                    const string tf1, const string tf2, const string tf3)
   {
      if(!m_initialized) return;
      string line = StringFormat("%s,%s,%s,%s,%s,%s,%.4f,%d,%s,%s,%s,%s",
         Now(), m_symbol, m_strategy,
         signal, decision, reason,
         riskPct, spread, session, tf1, tf2, tf3);
      WriteCSV(m_decision_file, line);
   }

   //--- Error log
   void LogError(const string action, int code = 0, const string text = "")
   {
      if(!m_initialized) return;
      string errText = (text == "") ? (string)GetLastError() : text;
      string line = StringFormat("%s,%s,%s,%s,%d,%s",
         Now(), m_symbol, m_strategy, action, code, errText);
      WriteCSV(m_error_file, line);
      Print("[ERROR] ", m_strategy, " | ", action, " | code=", code, " | ", errText);
   }

   //--- Trade log (called on close)
   void LogTrade(const string direction,
                 double entry, double sl, double tp,
                 double exitPrice, double profit,
                 double rMultiple,
                 double commission, double swap, double spread)
   {
      if(!m_initialized) return;
      string line = StringFormat(
         "%s,%s,%s,%s,%.5f,%.5f,%.5f,%.5f,%.4f,%.4f,%.4f,%.4f,%.1f",
         Now(), m_symbol, m_strategy, direction,
         entry, sl, tp, exitPrice,
         profit, rMultiple, commission, swap, spread);
      WriteCSV(m_trade_file, line);
   }

   //--- Print with prefix
   void Info   (const string msg) { Print("[INFO]  [", m_strategy, "] ", msg); }
   void Warning(const string msg) { Print("[WARN]  [", m_strategy, "] ", msg); }
   void Error  (const string msg) { Print("[ERROR] [", m_strategy, "] ", msg); }
};
