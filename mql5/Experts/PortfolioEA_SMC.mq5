//+------------------------------------------------------------------+
//|  PortfolioEA_SMC.mq5                                             |
//|  SMC/ICT Structure EA — BOS + Order Block + FVG entry            |
//|  Architecture: SOLID — EA orchestrates, delegates to modules.    |
//+------------------------------------------------------------------+
#property copyright "MT5 Quant Lab"
#property version   "1.10"
#property strict

#include <core/IStrategy.mqh>
#include <core/RiskManager.mqh>
#include <core/TradeManager.mqh>
#include <core/Logger.mqh>
#include <ui/Dashboard.mqh>
#include <ui/ChartSetup.mqh>
#include <ui/AlertManager.mqh>

//=== Input Groups ===================================================

//--- General
input group  "=== General ==="
input bool   InpEnableTrading   = true;
input int    InpMagicNumber     = 20260701;  // magic_base + offset + symbol_suffix
input string InpStrategyName    = "SMC_ICT";
input string InpVersion         = "1.10";

//--- Timeframes
input group  "=== Timeframes ==="
input ENUM_TIMEFRAMES InpTF1    = PERIOD_H4;   // Bias / BOS
input ENUM_TIMEFRAMES InpTF2    = PERIOD_H1;   // Order Block / FVG
input ENUM_TIMEFRAMES InpTF3    = PERIOD_M15;  // Entry trigger

//--- Strategy parameters
input group  "=== SMC Parameters ==="
input int    InpSwingLookback   = 10;
input double InpOB_MinBodyPct   = 0.6;
input double InpFVG_MinGapATR   = 0.3;
input double InpSweepBuffer     = 0.1;
input int    InpOB_MaxAgeBars   = 50;
input double InpSL_OB_Buffer    = 0.1;
input double InpTP_RR           = 2.5;
input int    InpSignalExpiryBars= 6;
input bool   InpRequireFVG      = true;   // OB harus diikuti FVG

//--- Risk
input group  "=== Risk ==="
input double InpBaseRiskPct     = 0.10;   // Research demo tier
input double InpKellyFraction   = 0.0;    // 0 = Kelly disabled
input double InpMaxSpreadPoints = 20;     // Max spread in points (EURUSD)

//--- UI
input group  "=== UI ==="
input bool   InpShowDashboard   = true;
input bool   InpShowIndicator   = true;

//=== Global objects =================================================

CRiskManager   g_risk;
CTradeManager  g_trade;
CLogger        g_logger;
CDashboard     g_dash;
CChartSetup    g_chart;
CAlertManager  g_alert;

//--- Indicator handles
int g_ind_tf1 = INVALID_HANDLE;  // SMC_Structure_Indicator on H4
int g_ind_tf2 = INVALID_HANDLE;  // SMC_Structure_Indicator on H1
int g_ind_tf3 = INVALID_HANDLE;  // SMC_Structure_Indicator on M15 (entry)

//--- Buffers: BOS_Direction(0), OB_High(1), OB_Low(2), FVG_High(3), FVG_Low(4)
double g_bos_tf1[], g_ob_high_tf2[], g_ob_low_tf2[], g_fvg_hi[], g_fvg_lo[];
double g_bos_tf3[];

datetime g_last_bar_tf3 = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   //--- Validate
   if(InpBaseRiskPct <= 0 || InpBaseRiskPct > 2.0) { Alert("BaseRiskPct invalid"); return(INIT_PARAMETERS_INCORRECT); }
   if(InpTP_RR < 1.0)                              { Alert("TP_RR < 1.0");        return(INIT_PARAMETERS_INCORRECT); }

   //--- Chart
   g_chart.Setup(InpTF1, InpTF2, InpTF3);

   //--- Logger
   if(!g_logger.Init(InpMagicNumber, InpStrategyName))
      Print("Logger init warning — CSV log disabled");

   //--- Risk & Trade managers
   g_risk.Init(InpBaseRiskPct, InpKellyFraction, InpMagicNumber);
   g_trade.Init(InpMagicNumber, InpStrategyName);

   //--- Load SMC indicator on each TF
   string ind_name = "SMC_Structure_Indicator";
   g_ind_tf1 = iCustom(_Symbol, InpTF1, ind_name,
                        InpSwingLookback, InpOB_MinBodyPct, InpFVG_MinGapATR,
                        InpOB_MaxAgeBars, InpSweepBuffer, false, false, false);
   g_ind_tf2 = iCustom(_Symbol, InpTF2, ind_name,
                        InpSwingLookback, InpOB_MinBodyPct, InpFVG_MinGapATR,
                        InpOB_MaxAgeBars, InpSweepBuffer, false, false, false);

   if(g_ind_tf1 == INVALID_HANDLE || g_ind_tf2 == INVALID_HANDLE)
   {
      Alert("Cannot load SMC_Structure_Indicator — check Indicators folder");
      return(INIT_FAILED);
   }

   //--- Dashboard
   if(InpShowDashboard)
   {
      SDashboardState st;
      st.ea_enabled      = InpEnableTrading;
      st.strategy_name   = InpStrategyName;
      st.trade_allowed   = false;
      st.block_reason    = "Initializing";
      g_dash.Render(st);
   }

   Print(InpStrategyName, " v", InpVersion, " initialized | Magic=", InpMagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   g_dash.Remove();
   if(g_ind_tf1 != INVALID_HANDLE) IndicatorRelease(g_ind_tf1);
   if(g_ind_tf2 != INVALID_HANDLE) IndicatorRelease(g_ind_tf2);
}

//+------------------------------------------------------------------+
void OnTick()
{
   //--- Kill switch
   if(g_risk.IsKillSwitchActive(InpMagicNumber))
   {
      UpdateDashboard(false, "KILL switch active");
      return;
   }

   string block_reason;
   if(!IsTradeAllowed(block_reason))
   {
      UpdateDashboard(false, block_reason);
      return;
   }

   //--- New bar on TF3 only
   datetime cur_bar = iTime(_Symbol, InpTF3, 1);
   if(cur_bar == g_last_bar_tf3) return;
   g_last_bar_tf3 = cur_bar;

   //--- Get indicator data (shift >= 1 — non-repaint)
   if(CopyBuffer(g_ind_tf1, 0, 1, 3, g_bos_tf1)    < 3) return;
   if(CopyBuffer(g_ind_tf2, 1, 1, 3, g_ob_high_tf2) < 3) return;
   if(CopyBuffer(g_ind_tf2, 2, 1, 3, g_ob_low_tf2)  < 3) return;
   if(CopyBuffer(g_ind_tf2, 3, 1, 3, g_fvg_hi)      < 3) return;
   if(CopyBuffer(g_ind_tf2, 4, 1, 3, g_fvg_lo)      < 3) return;

   ArraySetAsSeries(g_bos_tf1,     true);
   ArraySetAsSeries(g_ob_high_tf2, true);
   ArraySetAsSeries(g_ob_low_tf2,  true);
   ArraySetAsSeries(g_fvg_hi,      true);
   ArraySetAsSeries(g_fvg_lo,      true);

   if(g_trade.HasOpenPosition())
   {
      ManageOpenPosition();
   }
   else
   {
      CheckEntrySignal();
   }

   UpdateDashboard(true, "");
}

//+------------------------------------------------------------------+
void CheckEntrySignal()
{
   //--- TF1: Bull bias (BOS UP tồn tại trong 3 bars gần nhất)
   bool tf1_bull = false;
   for(int k = 0; k < 3; k++)
      if(g_bos_tf1[k] > 0.5) { tf1_bull = true; break; }
   if(!tf1_bull) return;

   //--- TF2: Bullish OB valid
   double ob_hi = g_ob_high_tf2[0];
   double ob_lo = g_ob_low_tf2[0];
   if(ob_hi == EMPTY_VALUE || ob_lo == EMPTY_VALUE || ob_hi <= ob_lo) return;

   //--- TF2: FVG trong vùng OB (hoặc overlap)
   if(InpRequireFVG)
   {
      double fvg_hi = g_fvg_hi[0];
      double fvg_lo = g_fvg_lo[0];
      bool fvg_in_ob = (fvg_hi != EMPTY_VALUE && fvg_lo != EMPTY_VALUE
                        && fvg_lo < ob_hi && fvg_hi > ob_lo);
      if(!fvg_in_ob) return;
   }

   //--- TF3: Giá đang ở trong OB zone
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(bid < ob_lo || bid > ob_hi) return;

   //--- TF3: Bullish Engulfing hoặc Pin Bar trên bar đã đóng (shift=1)
   double o1 = iOpen(_Symbol,  InpTF3, 1);
   double c1 = iClose(_Symbol, InpTF3, 1);
   double h1 = iHigh(_Symbol,  InpTF3, 1);
   double l1 = iLow(_Symbol,   InpTF3, 1);

   double body  = c1 - o1;
   double range = h1 - l1;
   bool is_bull_candle = (body > 0 && range > 0 && body / range >= InpOB_MinBodyPct);
   if(!is_bull_candle) return;

   //--- Close phải trên giữa OB
   if(c1 < (ob_lo + ob_hi) / 2.0) return;

   //--- Tính SL / TP
   double atr = iATR(_Symbol, InpTF3, 14, 1);
   if(atr <= 0) return;

   double sl = ob_lo - InpSL_OB_Buffer * atr;
   double sl_dist = bid - sl;

   if(sl_dist <= _Point * 10) return;           // SL quá nhỏ
   if(sl_dist > atr * 3)      return;           // SL quá lớn (> 3 ATR)

   double tp = bid + InpTP_RR * sl_dist;

   //--- Lot size
   double lots = g_risk.CalcLotSize(_Symbol, sl_dist, InpBaseRiskPct);
   if(lots <= 0) return;

   //--- Execute
   string comment = StringFormat("%s OB[%.5f-%.5f] sl=%.5f tp=%.5f",
                                 InpStrategyName, ob_lo, ob_hi, sl, tp);
   ulong ticket = g_trade.OpenPosition(_Symbol, ORDER_TYPE_BUY, lots, sl, tp, comment);

   if(ticket > 0)
      g_logger.LogTrade(ticket, ORDER_TYPE_BUY, _Symbol, lots, bid, sl, tp, comment);
   else
      g_logger.LogDecision(_Symbol, "SIGNAL_REJECTED", "OpenPosition failed");
}

//+------------------------------------------------------------------+
void ManageOpenPosition()
{
   //--- Close nếu TF1 bias flip sang BEAR
   bool tf1_bear = false;
   for(int k = 0; k < 3; k++)
      if(g_bos_tf1[k] < -0.5) { tf1_bear = true; break; }

   if(tf1_bear)
   {
      ulong ticket = g_trade.GetOpenTicket();
      if(ticket > 0)
      {
         g_trade.ClosePosition(ticket, "TF1 bias flip to BEAR");
         g_logger.LogDecision(_Symbol, "CLOSE", "TF1 BOS flip Bear");
      }
   }
}

//+------------------------------------------------------------------+
string GetBlockReason()
{
   if(!InpEnableTrading)          return "EA disabled by input";
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return "AutoTrading OFF";
   if(g_risk.IsDailyLossBreached(InpMagicNumber))   return "Daily loss limit hit";
   double dd = g_risk.GetCurrentDD(InpMagicNumber);
   if(dd > 6.0)                   return StringFormat("DD %.1f%% > 6%%", dd);
   double spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPoints)return StringFormat("Spread %d > %d pts", (int)spread, (int)InpMaxSpreadPoints);
   return "";
}

bool IsTradeAllowed(string &reason)
{
   reason = GetBlockReason();
   return reason == "";
}

//+------------------------------------------------------------------+
void UpdateDashboard(bool trade_ok, string reason)
{
   if(!InpShowDashboard) return;
   SDashboardState st;
   st.ea_enabled     = InpEnableTrading;
   st.strategy_name  = InpStrategyName;
   st.trade_allowed  = trade_ok;
   st.block_reason   = reason;
   st.current_dd     = g_risk.GetCurrentDD(InpMagicNumber);
   st.spread_points  = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   g_dash.Render(st);
}

//+------------------------------------------------------------------+
//| OnTester — export trade log cho Python pipeline                   |
//+------------------------------------------------------------------+
double OnTester()
{
   ExportTradeLogCSV();
   return 0.0;
}

void ExportTradeLogCSV()
{
   HistorySelect(0, TimeCurrent());
   int total = HistoryDealsTotal();
   if(total == 0) return;

   string filename = InpStrategyName + "_trade_log.csv";
   int fh = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(fh == INVALID_HANDLE) return;

   FileWrite(fh, "timestamp,symbol,strategy,direction,entry,sl,tp,exit,profit,commission,swap");

   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagicNumber) continue;
      if(HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT)  continue;

      string dir    = (HistoryDealGetInteger(ticket, DEAL_TYPE) == DEAL_TYPE_BUY) ? "LONG" : "SHORT";
      datetime dt   = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double comm   = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      double swap   = HistoryDealGetDouble(ticket, DEAL_SWAP);
      double price  = HistoryDealGetDouble(ticket, DEAL_PRICE);

      FileWrite(fh,
         TimeToString(dt, TIME_DATE | TIME_MINUTES),
         _Symbol, InpStrategyName, dir,
         DoubleToString(price, _Digits),
         "0", "0",
         DoubleToString(price, _Digits),
         DoubleToString(profit, 2),
         DoubleToString(comm, 2),
         DoubleToString(swap, 2)
      );
   }
   FileClose(fh);
}
//+------------------------------------------------------------------+
