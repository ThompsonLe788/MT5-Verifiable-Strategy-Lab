//+------------------------------------------------------------------+
//| PortfolioEA_Wyckoff.mq5                                         |
//| SOLID architecture: EA là orchestrator, không chứa logic trực tiếp|
//+------------------------------------------------------------------+
#property copyright "MT5 Quant Lab"
#property version   "1.00"

#include <core\IStrategy.mqh>
#include <core\Logger.mqh>
#include <core\RiskManager.mqh>
#include <core\TradeManager.mqh>
#include <ui\ChartSetup.mqh>
#include <ui\Dashboard.mqh>
#include <ui\AlertManager.mqh>

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+

// --- General ---
input bool   InpEnableTrading   = true;
input long   InpMagicBase       = 20260501;
input string InpCommentPrefix   = "QT_WYK";

// --- Timeframes ---
input ENUM_TIMEFRAMES InpTF1 = PERIOD_H4;
input ENUM_TIMEFRAMES InpTF2 = PERIOD_H1;
input ENUM_TIMEFRAMES InpTF3 = PERIOD_M15;

// --- Strategy parameters ---
input int    InpRangeLookback   = 20;
input double InpRangeMinATR     = 1.0;
input double InpSpringATRBuf    = 0.2;
input int    InpEMA_Period      = 21;
input double InpPullbackATRTol  = 0.3;
input double InpSL_MaxATR       = 3.0;
input double InpTP_RR           = 2.0;
input int    InpSignalExpiryBars = 8;

// --- Risk ---
input double InpRiskPct         = 0.25;
input double InpMaxDailyLoss    = 3.0;
input double InpMaxPortfolioRisk= 3.0;
input double InpMaxSymbolExpo   = 1.0;

// --- Filters ---
input bool   InpSpreadFilter    = true;
input int    InpMaxSpread       = 300;
input bool   InpSessionFilter   = true;
input bool   InpNewsFilter      = true;

// --- UI ---
input bool   InpShowDashboard   = true;
input int    InpFontSize        = 10;
input bool   InpAutoSetupChart  = true;
input bool   InpAutoLoadInd     = true;

//+------------------------------------------------------------------+
//| Global objects                                                   |
//+------------------------------------------------------------------+
CLogger        g_logger;
CRiskManager   g_risk;
CTradeManager  g_trade;
CChartSetup    g_chart;
CDashboard     g_dash;
CAlertManager  g_alert;

// --- Indicator handles ---
int  g_indHandle  = INVALID_HANDLE;
int  g_atrHandle  = INVALID_HANDLE;
int  g_emaHandle  = INVALID_HANDLE;

// --- State ---
bool   g_tradingBlocked = false;
string g_blockReason    = "";
string g_lastSignal     = "NONE";
string g_lastError      = "";

long   g_magic;

//+------------------------------------------------------------------+
//| Validate inputs                                                  |
//+------------------------------------------------------------------+
bool ValidateInputs()
{
   if(InpRiskPct <= 0 || InpRiskPct > 2.0)
   { g_blockReason = "BLOCKED_INVALID_INPUT: RiskPct"; return false; }
   if(InpMaxDailyLoss <= 0 || InpMaxDailyLoss > 10.0)
   { g_blockReason = "BLOCKED_INVALID_INPUT: MaxDailyLoss"; return false; }
   if(InpTF1 <= InpTF2)
   { g_blockReason = "BLOCKED_INVALID_INPUT: TF1 <= TF2"; return false; }
   if(InpTF2 <= InpTF3)
   { g_blockReason = "BLOCKED_INVALID_INPUT: TF2 <= TF3"; return false; }
   return true;
}

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_magic = InpMagicBase + 100 +
             (long)StringLen(_Symbol);   // simple symbol suffix

   // Logger
   g_logger.Init(_Symbol, "WyckoffBreakout");

   // Validate
   if(!ValidateInputs())
   {
      g_tradingBlocked = true;
      g_logger.Warning("Init blocked: " + g_blockReason);
   }

   // Chart setup
   if(InpAutoSetupChart)
   {
      g_chart.Init(ChartID());
      g_chart.ApplyMinimalTheme();
      g_chart.SetTimeframe(InpTF3);
   }

   // Load indicator
   if(InpAutoLoadInd)
   {
      g_indHandle = iCustom(_Symbol, InpTF1,
                            "Wyckoff_Phase_Indicator",
                            InpRangeLookback, InpRangeMinATR,
                            InpSpringATRBuf, 10,
                            1.2, true);
      if(g_indHandle == INVALID_HANDLE)
      {
         g_tradingBlocked = true;
         g_blockReason    = "BLOCKED_INDICATOR_LOAD_FAILED";
         g_logger.LogError("OnInit", 0, g_blockReason);
      }
   }

   // ATR + EMA for entry logic
   g_atrHandle = iATR(_Symbol, InpTF3, 14);
   g_emaHandle = iMA (_Symbol, InpTF3, InpEMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   if(g_atrHandle == INVALID_HANDLE || g_emaHandle == INVALID_HANDLE)
   {
      g_tradingBlocked = true;
      g_blockReason    = "BLOCKED_INDICATOR_LOAD_FAILED";
   }

   // Risk / Trade managers
   g_risk.Init(_Symbol, InpMagicBase, &g_logger,
               InpRiskPct, 1.0, InpMaxDailyLoss,
               InpMaxPortfolioRisk, InpMaxSymbolExpo);
   g_trade.Init(_Symbol, g_magic, &g_logger, &g_risk, InpCommentPrefix);

   // Dashboard
   g_dash.Init(ChartID(), (string)g_magic, CORNER_RIGHT_UPPER, InpFontSize);

   // Alert
   g_alert.Init(60);

   // Log init
   g_logger.LogDecision("INIT", g_tradingBlocked ? "BLOCKED" : "OK",
      g_blockReason, InpRiskPct, 0, "", "—", "—", "—");

   RenderDashboard();
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   g_dash.Remove();
   if(g_indHandle != INVALID_HANDLE) IndicatorRelease(g_indHandle);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_emaHandle != INVALID_HANDLE) IndicatorRelease(g_emaHandle);
   g_risk.PublishOpenRisk(0.0);
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   // Kill switch (set by Python Monitoring Agent)
   if(g_risk.IsKillSwitchActive())
   {
      SetBlocked("BLOCKED_KILL_SWITCH");
      RenderDashboard();
      return;
   }

   // Hard guards
   string blockReason = GetBlockReason();
   if(blockReason != "")
   {
      SetBlocked(blockReason);
      RenderDashboard();
      return;
   }

   // Clear block
   g_tradingBlocked = false;
   g_blockReason    = "";

   // Only act on new confirmed bar (non-repaint)
   static datetime s_lastBar = 0;
   datetime        curBar    = iTime(_Symbol, InpTF3, 1);
   if(curBar == s_lastBar && g_trade.HasOpenPosition()) { RenderDashboard(); return; }

   // --- Check existing position management ---
   if(g_trade.HasOpenPosition())
   {
      ManageOpenPosition();
      RenderDashboard();
      return;
   }

   // --- Entry logic ---
   ENUM_SIGNAL_TYPE signal = CheckEntrySignal();
   if(signal == SIGNAL_LONG)
   {
      double slPrice = CalcSL(signal);
      double tpPrice = CalcTP(signal, slPrice);

      if(slPrice <= 0.0)
      {
         g_logger.LogDecision("LONG", "BLOCKED", "BLOCKED_INVALID_STOPS",
            g_risk.GetRiskPct(), GetSpread(), GetSession(),
            GetTF1Text(), GetTF2Text(), GetTF3Text());
         RenderDashboard();
         return;
      }

      double lot = g_risk.CalcLotSize(MathAbs(SymbolInfoDouble(_Symbol, SYMBOL_ASK) - slPrice));
      if(lot <= 0.0) { RenderDashboard(); return; }

      bool opened = g_trade.OpenPosition(ORDER_TYPE_BUY, lot, slPrice, tpPrice);
      if(opened)
      {
         g_lastSignal = "BUY EXECUTED";
         s_lastBar    = curBar;
         g_logger.LogDecision("LONG", "EXECUTED", "",
            g_risk.GetRiskPct(), GetSpread(), GetSession(),
            GetTF1Text(), GetTF2Text(), GetTF3Text());
         g_risk.PublishOpenRisk(g_risk.GetRiskPct());
      }
      else
      {
         g_lastError = "OpenPosition failed";
         g_alert.Risk("Order rejected", "ORDER_FAIL");
      }
   }
   else
   {
      g_logger.LogDecision("NONE", "NO_SIGNAL", "",
         g_risk.GetRiskPct(), GetSpread(), GetSession(),
         GetTF1Text(), GetTF2Text(), GetTF3Text());
   }

   RenderDashboard();
}

//+------------------------------------------------------------------+
//| OnTester — export trade log for Python pipeline                 |
//+------------------------------------------------------------------+
double OnTester()
{
   // Called by MT5 at end of backtest
   ExportTradeLogCSV();
   return 0.0;
}

//+------------------------------------------------------------------+
//| Internal helpers                                                 |
//+------------------------------------------------------------------+

string GetBlockReason()
{
   if(!InpEnableTrading)      return "BLOCKED_EA_DISABLED";
   if(g_tradingBlocked)       return g_blockReason;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
                              return "BLOCKED_AUTOTRADING_OFF";
   if(g_risk.IsDailyLossBreached())
                              return "BLOCKED_DAILY_LOSS_LIMIT";
   if(g_risk.GetCurrentDD() >= 6.0)
                              return "BLOCKED_MAX_DD_LIMIT";
   if(InpSpreadFilter && GetSpread() > InpMaxSpread)
                              return "BLOCKED_SPREAD_HIGH";
   if(InpSessionFilter && !IsSessionAllowed())
                              return "BLOCKED_SESSION_CLOSED";
   return "";
}

void SetBlocked(const string reason)
{
   if(reason != g_blockReason)
   {
      g_blockReason    = reason;
      g_tradingBlocked = true;
      g_alert.Warning(reason, reason);
      g_logger.LogDecision("—", "BLOCKED", reason,
         g_risk.GetRiskPct(), GetSpread(), GetSession(),
         GetTF1Text(), GetTF2Text(), GetTF3Text());
   }
}

ENUM_SIGNAL_TYPE CheckEntrySignal()
{
   // --- TF1: Wyckoff Phase = BULL ---
   double phaseBuf[];
   ArraySetAsSeries(phaseBuf, true);
   if(g_indHandle == INVALID_HANDLE) return SIGNAL_NONE;
   if(CopyBuffer(g_indHandle, 0, 1, 3, phaseBuf) <= 0) return SIGNAL_NONE;
   if(phaseBuf[0] != 1.0) return SIGNAL_NONE;   // not BULL

   // --- TF2: BOS confirmed ---
   double bosBuf[];
   ArraySetAsSeries(bosBuf, true);
   if(CopyBuffer(g_indHandle, 4, 1, 3, bosBuf) <= 0) return SIGNAL_NONE;
   if(bosBuf[0] != 1.0) return SIGNAL_NONE;   // no BOS

   // --- TF3: Pullback to EMA ---
   double ema[], atr[];
   ArraySetAsSeries(ema, true);
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(g_emaHandle, 0, 1, 2, ema) <= 0) return SIGNAL_NONE;
   if(CopyBuffer(g_atrHandle, 0, 1, 2, atr) <= 0) return SIGNAL_NONE;

   double close1 = iClose(_Symbol, InpTF3, 1);
   double open1  = iOpen (_Symbol, InpTF3, 1);

   bool nearEMA    = MathAbs(close1 - ema[0]) <= InpPullbackATRTol * atr[0];
   bool bullCandle = close1 > open1;

   if(!nearEMA || !bullCandle) return SIGNAL_NONE;

   g_lastSignal = "BUY CONFIRMED";
   return SIGNAL_LONG;
}

double CalcSL(ENUM_SIGNAL_TYPE signal)
{
   // SL = Spring level (buffer 1) - SpringATRBuf * ATR
   double springBuf[], atr[];
   ArraySetAsSeries(springBuf, true);
   ArraySetAsSeries(atr, true);

   if(CopyBuffer(g_indHandle, 1, 1, 3, springBuf) <= 0) return 0.0;
   if(CopyBuffer(g_atrHandle, 0, 1, 2, atr)       <= 0) return 0.0;

   double springLevel = springBuf[0];
   if(springLevel <= 0.0) return 0.0;

   double sl = springLevel - InpSpringATRBuf * atr[0];

   // Validate SL distance
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double dist = ask - sl;
   if(dist > InpSL_MaxATR * atr[0]) return 0.0;   // too far
   if(dist < 1.0 * atr[0]) sl = ask - 1.0 * atr[0];  // enforce minimum

   return sl;
}

double CalcTP(ENUM_SIGNAL_TYPE signal, double slPrice)
{
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double dist = ask - slPrice;
   return ask + InpTP_RR * dist;
}

void ManageOpenPosition()
{
   // Phase 1: no trailing, no partial close
   // Exit if H4 bias flips to RANGE or BEAR
   double phaseBuf[];
   ArraySetAsSeries(phaseBuf, true);
   if(g_indHandle == INVALID_HANDLE) return;
   if(CopyBuffer(g_indHandle, 0, 1, 2, phaseBuf) <= 0) return;

   if(phaseBuf[0] != 1.0)   // bias no longer BULL
   {
      ulong ticket = g_trade.GetOpenTicket();
      if(ticket > 0)
      {
         g_trade.ClosePosition(ticket);
         g_risk.PublishOpenRisk(0.0);
         g_lastSignal = "EXIT: bias flip";
         g_logger.LogDecision("EXIT", "CLOSED", "Bias flip",
            g_risk.GetRiskPct(), GetSpread(), GetSession(),
            GetTF1Text(), "—", "—");
      }
   }
}

int GetSpread()
{
   return (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
}

bool IsSessionAllowed()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   int h = dt.hour;
   // London: 07–16 UTC, NewYork: 12–21 UTC
   bool london  = (h >= 7  && h < 16);
   bool newyork = (h >= 12 && h < 21);
   return london || newyork;
}

string GetSession()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   int h = dt.hour;
   if(h >= 12 && h < 16) return "OVERLAP";
   if(h >= 7  && h < 16) return "LONDON";
   if(h >= 12 && h < 21) return "NEWYORK";
   return "OFF";
}

string GetTF1Text()
{
   double phaseBuf[];
   ArraySetAsSeries(phaseBuf, true);
   if(g_indHandle == INVALID_HANDLE) return "—";
   if(CopyBuffer(g_indHandle, 0, 1, 2, phaseBuf) <= 0) return "—";
   if(phaseBuf[0] == 1.0)  return "BULL";
   if(phaseBuf[0] == -1.0) return "BEAR";
   return "RANGE";
}

string GetTF2Text()
{
   double bosBuf[];
   ArraySetAsSeries(bosBuf, true);
   if(g_indHandle == INVALID_HANDLE) return "—";
   if(CopyBuffer(g_indHandle, 4, 1, 2, bosBuf) <= 0) return "—";
   return (bosBuf[0] == 1.0) ? "BOS" : "NONE";
}

string GetTF3Text()
{
   double ema[], atr[];
   ArraySetAsSeries(ema, true);
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(g_emaHandle, 0, 1, 2, ema) <= 0) return "—";
   if(CopyBuffer(g_atrHandle, 0, 1, 2, atr) <= 0) return "—";
   double close1 = iClose(_Symbol, InpTF3, 1);
   bool nearEMA  = MathAbs(close1 - ema[0]) <= InpPullbackATRTol * atr[0];
   return nearEMA ? "READY" : "WAIT";
}

void RenderDashboard()
{
   if(!InpShowDashboard) return;

   SDashboardState s;
   s.eaOn          = InpEnableTrading;
   s.tradingAllowed = !g_tradingBlocked;
   s.blockedReason  = g_blockReason;
   s.symbol         = _Symbol;
   s.strategy       = "Wyckoff";
   s.tf1State       = GetTF1Text();
   s.tf2State       = GetTF2Text();
   s.tf3State       = GetTF3Text();
   s.lastSignal     = g_lastSignal;
   s.riskPct        = g_risk.GetRiskPct();
   s.dailyPL        = 0.0;   // simplified: compute from history if needed
   s.ddPct          = g_risk.GetCurrentDD();
   s.openTrades     = g_trade.HasOpenPosition() ? 1 : 0;
   s.spreadPoints   = GetSpread();
   s.spreadHigh     = (InpSpreadFilter && s.spreadPoints > InpMaxSpread);
   s.lastError      = g_lastError;

   g_dash.Render(s);
}

//+------------------------------------------------------------------+
//| Export trade log CSV for Python pipeline (OnTester)             |
//+------------------------------------------------------------------+
void ExportTradeLogCSV()
{
   string filename = "trade_log.csv";
   int h = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;

   FileWrite(h, "timestamp,symbol,strategy,direction,entry,sl,tp,exit,"
                "profit,r_multiple,commission,swap,spread");

   HistorySelect(0, TimeCurrent());
   for(int i = 0; i < HistoryDealsTotal(); i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != g_magic) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;

      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double comm   = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      double swap_  = HistoryDealGetDouble(ticket, DEAL_SWAP);
      double price  = HistoryDealGetDouble(ticket, DEAL_PRICE);
      datetime t    = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      string   dir  = HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY ? "BUY" : "SELL";

      FileWrite(h,
         TimeToString(t, TIME_DATE|TIME_SECONDS),
         _Symbol, "WyckoffBreakout", dir,
         "0", "0", "0",    // entry/sl/tp simplified — use deal price
         DoubleToString(price, _Digits),
         DoubleToString(profit, 2),
         "0",               // r_multiple (requires matching entry deal)
         DoubleToString(comm, 2),
         DoubleToString(swap_, 2),
         "0"
      );
   }
   FileClose(h);
}
