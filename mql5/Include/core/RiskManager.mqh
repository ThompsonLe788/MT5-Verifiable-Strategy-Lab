//+------------------------------------------------------------------+
//| RiskManager.mqh — Position sizing + Kelly + guard conditions    |
//+------------------------------------------------------------------+
#pragma once
#include "Logger.mqh"

//--- Global Variables prefix for portfolio state
#define GV_PREFIX "QT_"

//+------------------------------------------------------------------+
class CRiskManager
{
private:
   string   m_symbol;
   long     m_magicBase;
   CLogger* m_logger;

   double   m_riskPct;          // base risk %
   double   m_maxRiskPct;       // hard cap %
   double   m_maxDailyLossPct;
   double   m_maxPortfolioRisk;
   double   m_maxSymbolExposure;

   double   m_dailyStartBalance;
   double   m_dailyPL;
   datetime m_lastDayReset;

   // --- Kelly ---
   double   m_kellyFraction;    // current fractional Kelly (0.25–0.5)
   int      m_kellySample;      // number of trades used to compute Kelly
   bool     m_kellyValid;       // enough sample?

   string   GVKey(const string field) { return GV_PREFIX + (string)m_magicBase + "_" + field; }

   void     UpdateDailyReset()
   {
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      MqlDateTime last;
      TimeToStruct(m_lastDayReset, last);
      if(dt.day != last.day)
      {
         m_dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
         m_dailyPL           = 0.0;
         m_lastDayReset      = TimeCurrent();
      }
   }

public:
   CRiskManager() : m_kellyFraction(0.25), m_kellySample(0), m_kellyValid(false),
                    m_dailyPL(0.0), m_lastDayReset(0) {}

   void Init(const string symbol, long magicBase, CLogger* logger,
             double riskPct       = 0.25,
             double maxRiskPct    = 1.00,
             double maxDailyLoss  = 3.00,
             double maxPortfolio  = 3.00,
             double maxSymbolExpo = 1.00)
   {
      m_symbol           = symbol;
      m_magicBase        = magicBase;
      m_logger           = logger;
      m_riskPct          = riskPct;
      m_maxRiskPct       = maxRiskPct;
      m_maxDailyLossPct  = maxDailyLoss;
      m_maxPortfolioRisk = maxPortfolio;
      m_maxSymbolExposure= maxSymbolExpo;
      m_dailyStartBalance= AccountInfoDouble(ACCOUNT_BALANCE);
      m_lastDayReset     = TimeCurrent();
   }

   // ------------------------------------------------------------------
   // Kelly update (call after each closed trade)
   // ------------------------------------------------------------------
   void UpdateKelly(double winrate, double avgWin, double avgLoss, int sampleSize)
   {
      m_kellySample = sampleSize;
      if(sampleSize < 100)
      {
         m_kellyValid    = false;
         m_kellyFraction = 0.0;
         return;
      }
      if(avgLoss <= 0.0 || avgWin <= 0.0) return;

      double b  = avgWin / avgLoss;          // reward:risk ratio
      double p  = winrate;
      double q  = 1.0 - p;
      double f  = (b * p - q) / b;          // full Kelly

      f = MathMax(f, 0.0);                   // không âm
      f = f * 0.25;                          // quarter Kelly mặc định

      // Cap theo DD adjustment
      double dd = GetCurrentDD();
      if     (dd >= 6.0) f = 0.0;
      else if(dd >= 4.0) f *= 0.25;
      else if(dd >= 2.0) f *= 0.50;

      m_kellyFraction = MathMin(f, 0.5);     // hard cap 0.5
      m_kellyValid    = true;
   }

   // ------------------------------------------------------------------
   // Effective risk % (min of base, kelly, max, dd-adjusted)
   // ------------------------------------------------------------------
   double GetEffectiveRisk()
   {
      double risk = m_riskPct;

      if(m_kellyValid && m_kellyFraction > 0.0)
         risk = MathMin(risk, m_kellyFraction * 100.0);   // Kelly → %

      risk = MathMin(risk, m_maxRiskPct);
      return risk;
   }

   // ------------------------------------------------------------------
   // Lot size calculation
   // ------------------------------------------------------------------
   double CalcLotSize(double slDistance)
   {
      if(slDistance <= 0.0)
      {
         m_logger.LogError("CalcLotSize", 0, "SL distance = 0");
         return 0.0;
      }

      double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
      double riskPct    = GetEffectiveRisk() / 100.0;
      double riskAmount = balance * riskPct;

      double tickValue  = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize   = SymbolInfoDouble(m_symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickSize <= 0.0 || tickValue <= 0.0) return 0.0;

      double slTicks    = slDistance / tickSize;
      double lot        = riskAmount / (slTicks * tickValue);

      // Normalize to broker constraints
      double lotMin  = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MIN);
      double lotMax  = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_MAX);
      double lotStep = SymbolInfoDouble(m_symbol, SYMBOL_VOLUME_STEP);

      lot = MathFloor(lot / lotStep) * lotStep;
      lot = MathMax(lot, lotMin);
      lot = MathMin(lot, lotMax);

      return lot;
   }

   // ------------------------------------------------------------------
   // Guard conditions
   // ------------------------------------------------------------------
   bool IsDailyLossBreached()
   {
      UpdateDailyReset();
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      double loss    = (m_dailyStartBalance - balance) / m_dailyStartBalance * 100.0;
      return loss >= m_maxDailyLossPct;
   }

   bool IsPortfolioRiskBreached()
   {
      double totalRisk = GlobalVariableGet(GVKey("TOTAL_RISK"));
      return totalRisk >= m_maxPortfolioRisk;
   }

   bool IsKillSwitchActive()
   {
      return GlobalVariableGet(GVKey("KILL")) >= 1.0;
   }

   double GetCurrentDD()
   {
      double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      if(balance <= 0.0) return 0.0;
      return MathMax((balance - equity) / balance * 100.0, 0.0);
   }

   // ------------------------------------------------------------------
   // Portfolio state update (Global Variables)
   // ------------------------------------------------------------------
   void PublishOpenRisk(double myRiskPct)
   {
      string key = GVKey("TOTAL_RISK");
      // Add this EA's contribution — simplified: EA tracks its own
      GlobalVariableSet(key, myRiskPct);
      GlobalVariableSet(GVKey("TS"), (double)TimeCurrent());
   }

   void PublishDailyPL(double plPct)
   {
      GlobalVariableSet(GVKey("DAILY_PL"), plPct);
   }

   // ------------------------------------------------------------------
   // SL validation
   // ------------------------------------------------------------------
   bool ValidateSL(double entryPrice, double slPrice, ENUM_ORDER_TYPE orderType)
   {
      if(slPrice <= 0.0) return false;

      long stopsLevel = SymbolInfoInteger(m_symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double point    = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
      double minDist  = stopsLevel * point;

      if(orderType == ORDER_TYPE_BUY  && (entryPrice - slPrice) < minDist) return false;
      if(orderType == ORDER_TYPE_SELL && (slPrice - entryPrice) < minDist) return false;
      return true;
   }

   // Getters
   double   GetRiskPct()       { return GetEffectiveRisk(); }
   double   GetKellyFraction() { return m_kellyFraction; }
   bool     IsKellyValid()     { return m_kellyValid; }
   int      GetKellySample()   { return m_kellySample; }
};
