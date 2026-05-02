//+------------------------------------------------------------------+
//|  PortfolioEA_SMC.mq5                                             |
//|  SMC/ICT — BOS → Sweep → OB+FVG retest trong Discount Zone      |
//|                                                                  |
//|  Entry logic (khác Wyckoff hoàn toàn):                          |
//|  1. H4 BOS_UP xác nhận BULL bias                                |
//|  2. H1 Liquidity Sweep (equal highs bị sweep, close quay lại)   |
//|  3. H1 OB + FVG zone xác định                                   |
//|  4. Bid phải trong Discount Zone (< 50% của impulse)            |
//|  5. M15 trigger: bullish engulf/pin bar trong OB zone           |
//|                                                                  |
//|  Exit logic (đặc thù SMC):                                      |
//|  - Partial close 50% tại 1R, SL → Breakeven                    |
//|  - Exit full khi CHoCH_DOWN trên H1 (buffer 0 == -1.0)         |
//|  - Exit full khi OB violated (close H1 < ob_low)                |
//|  - Không dùng TF1 bias flip để exit (quá chậm)                 |
//+------------------------------------------------------------------+
#property copyright "MT5 Quant Lab"
#property version   "1.10"
#property strict

#include <core/RiskManager.mqh>
#include <core/TradeManager.mqh>
#include <core/Logger.mqh>
#include <ui/Dashboard.mqh>
#include <ui/ChartSetup.mqh>
#include <ui/AlertManager.mqh>

//=== Inputs =========================================================

input group "=== General ==="
input bool   InpEnableTrading    = true;
input int    InpMagicNumber      = 20260702;
input string InpStrategyName     = "SMC_ICT";
input string InpVersion          = "1.10";

input group "=== Timeframes ==="
input ENUM_TIMEFRAMES InpTF1     = PERIOD_H4;
input ENUM_TIMEFRAMES InpTF2     = PERIOD_H1;
input ENUM_TIMEFRAMES InpTF3     = PERIOD_M15;

input group "=== SMC Parameters ==="
input int    InpSwingLookback    = 10;
input double InpOB_MinBodyPct    = 0.6;
input double InpFVG_MinGapATR    = 0.3;
input double InpEqualHL_ATRTol   = 0.1;   // tolerance để detect equal highs
input double InpSweepATRBuffer   = 0.1;   // giá sweep qua equal highs ít nhất N×ATR
input int    InpOB_MaxAgeBars    = 50;
input double InpSL_OB_Buffer     = 0.1;
input double InpTP_RR            = 2.5;
input double InpPartialClose_R   = 1.0;   // đóng 50% khi đạt N×R
input int    InpSignalExpiryBars = 6;     // M15 bars trước khi awaiting_entry timeout

input group "=== Risk ==="
input double InpBaseRiskPct      = 0.10;
input double InpMaxSpreadPoints  = 20;

input group "=== UI ==="
input bool   InpShowDashboard    = true;

//=== Constants ======================================================
#define CHOCH_DOWN  -1.0
#define BOS_UP       2.0

//=== Objects ========================================================
CRiskManager  g_risk;
CTradeManager g_trade;
CLogger       g_logger;
CDashboard    g_dash;
CChartSetup   g_chart;

//--- Indicator handles (SMC_Structure_Indicator trên TF1, TF2)
int g_ind_tf1 = INVALID_HANDLE;
int g_ind_tf2 = INVALID_HANDLE;

//--- Indicator buffers
double g_str_tf1[];   // Structure_Signal trên H4
double g_str_tf2[];   // Structure_Signal trên H1
double g_ob_hi[];     // OB_High trên H1
double g_ob_lo[];     // OB_Low  trên H1
double g_fvg_hi[];    // FVG_High trên H1
double g_fvg_lo[];    // FVG_Low  trên H1

//--- State machine
bool     g_awaiting_entry  = false;
int      g_signal_bars_left= 0;
bool     g_partial_done    = false;
double   g_entry_price     = 0;
double   g_sl_price        = 0;
double   g_tp_price        = 0;
double   g_ob_lo_at_entry  = 0;
double   g_swing_lo_after_entry = 0;  // theo dõi CHoCH: LL dưới mức này = CHoCH

datetime g_last_bar_tf2    = 0;
datetime g_last_bar_tf3    = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   if(InpBaseRiskPct <= 0 || InpTP_RR < 1.0)
      return INIT_PARAMETERS_INCORRECT;

   g_chart.Init(ChartID());
   g_logger.Init(_Symbol, InpStrategyName);
   g_risk.Init(_Symbol, InpMagicNumber, &g_logger, InpBaseRiskPct);
   g_trade.Init(_Symbol, InpMagicNumber, &g_logger, &g_risk);

   string ind = "SMC_Structure_Indicator";
   g_ind_tf1 = iCustom(_Symbol, InpTF1, ind,
                        InpSwingLookback, InpOB_MinBodyPct, InpFVG_MinGapATR,
                        InpOB_MaxAgeBars, InpEqualHL_ATRTol,
                        false, false, false);
   g_ind_tf2 = iCustom(_Symbol, InpTF2, ind,
                        InpSwingLookback, InpOB_MinBodyPct, InpFVG_MinGapATR,
                        InpOB_MaxAgeBars, InpEqualHL_ATRTol,
                        false, false, false);

   if(g_ind_tf1 == INVALID_HANDLE || g_ind_tf2 == INVALID_HANDLE)
   {
      Alert("SMC_Structure_Indicator load failed");
      return INIT_FAILED;
   }

   Print(InpStrategyName, " v", InpVersion, " | Magic=", InpMagicNumber);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   g_dash.Remove();
   IndicatorRelease(g_ind_tf1);
   IndicatorRelease(g_ind_tf2);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(g_risk.IsKillSwitchActive())
   {
      UpdateDash(false, "KILL switch");
      return;
   }
   string block;
   if(!TradeAllowed(block)) { UpdateDash(false, block); return; }

   //--- Frekuensi: manajemen posisi di setiap H1 bar baru
   datetime tf2_bar = iTime(_Symbol, InpTF2, 1);
   if(tf2_bar != g_last_bar_tf2)
   {
      g_last_bar_tf2 = tf2_bar;
      if(g_trade.HasOpenPosition())
         CheckSMCExits();    // CHoCH dan OB violation check
   }

   //--- Entry check di setiap M15 bar baru
   datetime tf3_bar = iTime(_Symbol, InpTF3, 1);
   if(tf3_bar != g_last_bar_tf3)
   {
      g_last_bar_tf3 = tf3_bar;
      if(g_trade.HasOpenPosition())
         CheckPartialClose();
      else
         CheckEntrySetup();  // 2 tahap: setup (H1) dan trigger (M15)
   }

   UpdateDash(true, "");
}

//+------------------------------------------------------------------+
//| BƯỚC 1 — Mỗi H1 bar mới: kiểm tra điều kiện setup              |
//| Nếu đủ điều kiện: set g_awaiting_entry = TRUE                   |
//+------------------------------------------------------------------+
void CheckEntrySetup()
{
   //--- Đọc indicators (shift=1, non-repaint)
   if(CopyBuffer(g_ind_tf1, 0, 1, 5, g_str_tf1) < 5) return;
   if(CopyBuffer(g_ind_tf2, 0, 1, 5, g_str_tf2) < 5) return;
   if(CopyBuffer(g_ind_tf2, 1, 1, 3, g_ob_hi)   < 3) return;
   if(CopyBuffer(g_ind_tf2, 2, 1, 3, g_ob_lo)   < 3) return;
   if(CopyBuffer(g_ind_tf2, 3, 1, 3, g_fvg_hi)  < 3) return;
   if(CopyBuffer(g_ind_tf2, 4, 1, 3, g_fvg_lo)  < 3) return;

   ArraySetAsSeries(g_str_tf1, true);
   ArraySetAsSeries(g_str_tf2, true);
   ArraySetAsSeries(g_ob_hi,   true);
   ArraySetAsSeries(g_ob_lo,   true);
   ArraySetAsSeries(g_fvg_hi,  true);
   ArraySetAsSeries(g_fvg_lo,  true);

   //--- KONDISI 1: TF1 H4 harus BOS_UP (dalam 5 bars terakhir), belum ada CHoCH
   bool tf1_bull = false;
   bool tf1_choch= false;
   for(int k = 0; k < 5; k++)
   {
      if(g_str_tf1[k] == BOS_UP)    tf1_bull  = true;
      if(g_str_tf1[k] == CHOCH_DOWN)tf1_choch = true;
   }
   if(!tf1_bull || tf1_choch) { g_awaiting_entry = false; return; }

   //--- KONDISI 2: TF2 H1 harus punya OB valid
   double ob_hi = g_ob_hi[0];
   double ob_lo = g_ob_lo[0];
   if(ob_hi == EMPTY_VALUE || ob_lo == EMPTY_VALUE || ob_hi <= ob_lo)
   {
      g_awaiting_entry = false;
      return;
   }

   //--- KONDISI 3: TF2 H1 harus punya FVG yang overlap dengan OB
   double fvg_hi = g_fvg_hi[0];
   double fvg_lo = g_fvg_lo[0];
   bool has_fvg  = (fvg_hi != EMPTY_VALUE && fvg_lo != EMPTY_VALUE
                    && fvg_lo < ob_hi && fvg_hi > ob_lo);
   if(!has_fvg) { g_awaiting_entry = false; return; }

   //--- KONDISI 4: Liquidity Sweep đã xảy ra trên H1
   //    Detect: giá vượt equal highs (gần nhất trong SwingLookback bars) rồi đóng cửa về trong
   if(!DetectLiquiditySweep()) { g_awaiting_entry = false; return; }

   //--- Setup thoả mãn → chờ M15 trigger
   if(!g_awaiting_entry)
   {
      g_awaiting_entry   = true;
      g_signal_bars_left = InpSignalExpiryBars;
      g_ob_lo_at_entry   = ob_lo;
      g_logger.LogDecision("ENTRY_SETUP", "AWAITING_ENTRY",
                           StringFormat("OB[%.5f-%.5f] FVG[%.5f-%.5f]", ob_lo, ob_hi, fvg_lo, fvg_hi),
                           g_risk.GetRiskPct(), 0, "", "H4", "H1", "M15");
   }

   //--- M15 trigger (cùng hàm, chạy khi g_awaiting_entry = true)
   CheckM15Trigger(ob_hi, ob_lo);
}

//+------------------------------------------------------------------+
//| BƯỚC 2 — Kiểm tra M15 trigger khi g_awaiting_entry = TRUE       |
//+------------------------------------------------------------------+
void CheckM15Trigger(double ob_hi, double ob_lo)
{
   if(!g_awaiting_entry) return;

   g_signal_bars_left--;
   if(g_signal_bars_left <= 0)
   {
      g_awaiting_entry = false;
      g_logger.LogDecision("ENTRY", "SIGNAL_EXPIRED", "timeout", 0, 0, "", "", "", "");
      return;
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   //--- Invalidation: OB violated sebelum entry
   if(bid < g_ob_lo_at_entry)
   {
      g_awaiting_entry = false;
      g_logger.LogDecision("ENTRY", "OB_VIOLATED", StringFormat("bid=%.5f ob_lo=%.5f", bid, g_ob_lo_at_entry), 0, 0, "", "", "", "");
      return;
   }

   //--- CHoCH trên H1 trong khi chờ → cancel
   if(g_str_tf2[0] == CHOCH_DOWN)
   {
      g_awaiting_entry = false;
      g_logger.LogDecision("ENTRY", "CHOCH_CANCEL", "", 0, 0, "", "", "", "");
      return;
   }

   //--- Bid phải trong OB zone
   if(bid < ob_lo || bid > ob_hi) return;

   //--- KONDISI 5: Discount Zone — bid < 50% impulse H1
   double atr_tf2 = GetATR(g_atr_h1, InpTF2);
   if(atr_tf2 <= 0) return;
   double impulse_mid = ob_lo + (ob_hi - ob_lo) * 3.0;  // OB ~ bắt đầu của swing
   //--- Cách tính đơn giản: bid < ob_lo + (ob_hi - ob_lo) * 0.5 ≡ dưới giữa OB
   //    (trong thực tế: discount = bên dưới 50% của toàn bộ leg, đây là proxy dùng OB midpoint)
   double ob_mid = (ob_lo + ob_hi) / 2.0;
   if(bid > ob_mid) return;   // không trong discount zone

   //--- KONDISI 6: M15 bar[1] bullish engulfing atau pin bar
   double m15_o = iOpen(_Symbol,  InpTF3, 1);
   double m15_c = iClose(_Symbol, InpTF3, 1);
   double m15_h = iHigh(_Symbol,  InpTF3, 1);
   double m15_l = iLow(_Symbol,   InpTF3, 1);

   double body  = m15_c - m15_o;
   double range = m15_h - m15_l;
   bool bull_candle = (body > 0 && range > 0 && body / range >= InpOB_MinBodyPct);
   if(!bull_candle)  return;
   if(m15_c < ob_mid) return;  // close di bawah tengah OB → lemah

   //--- Hitung SL/TP
   double atr_tf3 = GetATR(g_atr_h3, InpTF3);
   if(atr_tf3 <= 0) return;

   double sl = ob_lo - InpSL_OB_Buffer * atr_tf3;
   double sl_dist = bid - sl;
   if(sl_dist < _Point * 10) return;
   if(sl_dist > atr_tf3 * 3)  return;

   double tp   = bid + InpTP_RR * sl_dist;
   double lots = g_risk.CalcLotSize(sl_dist);
   if(lots <= 0) return;

   bool ok = g_trade.OpenPosition(ORDER_TYPE_BUY, lots, sl, tp);
   if(ok)
   {
      ulong ticket = g_trade.LastTicket;
      g_entry_price         = bid;
      g_sl_price            = sl;
      g_tp_price            = tp;
      g_ob_lo_at_entry      = ob_lo;
      g_partial_done        = false;
      g_awaiting_entry      = false;
      g_swing_lo_after_entry = iLow(_Symbol, InpTF2, 1);
      g_logger.LogTrade("LONG", bid, sl, tp, 0, 0, 0, 0, 0, 0);
   }
}

//+------------------------------------------------------------------+
//| Partial Close tại 1R — đặc thù SMC                              |
//+------------------------------------------------------------------+
void CheckPartialClose()
{
   if(g_partial_done || !g_trade.HasOpenPosition()) return;

   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double risk   = g_entry_price - g_sl_price;
   if(risk <= 0) return;

   double profit_r = (bid - g_entry_price) / risk;
   if(profit_r < InpPartialClose_R) return;

   //--- Đóng 50% lot
   ulong ticket = g_trade.GetOpenTicket();
   if(ticket == 0) return;

   double pos_lots = PositionGetDouble(POSITION_VOLUME);
   int vol_digits = (int)MathRound(-MathLog10(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)));
   double close_lots = NormalizeDouble(pos_lots * 0.5, vol_digits);
   if(close_lots < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      close_lots = pos_lots;

   if(g_trade.ClosePartial(ticket, close_lots))
   {
      g_trade.ModifySL(ticket, g_entry_price);
      g_sl_price     = g_entry_price;
      g_partial_done = true;
      g_logger.LogDecision("POSITION", "PARTIAL_CLOSE_1R",
                           StringFormat("lots=%.2f SL→BE=%.5f", close_lots, g_entry_price),
                           g_risk.GetRiskPct(), 0, "", "", "", "");
   }
}

//+------------------------------------------------------------------+
//| Exit checks — CHoCH và OB Violation (đặc thù SMC)               |
//+------------------------------------------------------------------+
void CheckSMCExits()
{
   if(!g_trade.HasOpenPosition()) return;

   //--- Đọc indicator TF2 (H1)
   if(CopyBuffer(g_ind_tf2, 0, 1, 3, g_str_tf2) < 3) return;
   if(CopyBuffer(g_ind_tf2, 2, 1, 3, g_ob_lo)   < 3) return;
   ArraySetAsSeries(g_str_tf2, true);
   ArraySetAsSeries(g_ob_lo,   true);

   double close_h1 = iClose(_Symbol, InpTF2, 1);
   ulong ticket    = g_trade.GetOpenTicket();

   //--- EXIT (a): CHoCH_DOWN trên H1 → trend reversal signal
   if(g_str_tf2[0] == CHOCH_DOWN || g_str_tf2[1] == CHOCH_DOWN)
   {
      g_trade.ClosePosition(ticket);
      g_logger.LogDecision("EXIT", "CHOCH", StringFormat("close_H1=%.5f", close_h1), 0, 0, "", "", "", "");
      ResetState();
      return;
   }

   //--- EXIT (b): OB Violated — close H1 < ob_lo lúc entry
   if(g_ob_lo_at_entry > 0 && close_h1 < g_ob_lo_at_entry)
   {
      g_trade.ClosePosition(ticket);
      g_logger.LogDecision("EXIT", "OB_VIOLATED",
                           StringFormat("close=%.5f ob_lo=%.5f", close_h1, g_ob_lo_at_entry), 0, 0, "", "", "", "");
      ResetState();
      return;
   }

   //--- Update swing low tracker để phát hiện CHoCH tự build
   double cur_low = iLow(_Symbol, InpTF2, 1);
   if(cur_low < g_swing_lo_after_entry)
      g_swing_lo_after_entry = cur_low;
}

//+------------------------------------------------------------------+
//| Detect Liquidity Sweep trên H1                                   |
//| Equal highs bị vượt qua > SweepBuffer×ATR rồi close về trong    |
//+------------------------------------------------------------------+
bool DetectLiquiditySweep()
{
   int bars = InpSwingLookback + 5;
   double h[], l[], c[];
   ArraySetAsSeries(h, true);
   ArraySetAsSeries(l, true);
   ArraySetAsSeries(c, true);
   if(CopyHigh(_Symbol, InpTF2, 1, bars, h) < bars) return false;
   if(CopyLow(_Symbol,  InpTF2, 1, bars, l) < bars) return false;
   if(CopyClose(_Symbol,InpTF2, 1, bars, c) < bars) return false;

   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(g_atr_handle(), 0, 1, bars, atr) < bars) return false;

   //--- Tìm equal highs trong SwingLookback bars
   for(int i = 1; i < InpSwingLookback; i++)
   {
      double eq_high = h[i];
      for(int j = i + 1; j < bars; j++)
      {
         if(MathAbs(h[j] - eq_high) <= InpEqualHL_ATRTol * atr[i])
         {
            //--- Equal highs tìm thấy tại i và j
            //--- Kiểm tra: có bar nào sau j vượt eq_high rồi close lại về dưới không?
            for(int k = i - 1; k >= 0; k--)
            {
               if(h[k] > eq_high + InpSweepATRBuffer * atr[k]  // sweep vượt
                  && c[k] < eq_high)                             // close về trong
                  return true;
            }
         }
      }
   }
   return false;
}

//--- ATR handles (lazy-init)
int g_atr_h1 = INVALID_HANDLE;   // TF2 = H1
int g_atr_h3 = INVALID_HANDLE;   // TF3 = M15

int g_atr_handle()
{
   if(g_atr_h1 == INVALID_HANDLE)
      g_atr_h1 = iATR(_Symbol, InpTF2, 14);
   return g_atr_h1;
}

double GetATR(int &handle, ENUM_TIMEFRAMES tf)
{
   if(handle == INVALID_HANDLE)
      handle = iATR(_Symbol, tf, 14);
   double buf[1];
   if(CopyBuffer(handle, 0, 1, 1, buf) < 1) return 0;
   return buf[0];
}

//+------------------------------------------------------------------+
//| Helpers                                                           |
//+------------------------------------------------------------------+

void ResetState()
{
   g_partial_done         = false;
   g_entry_price          = 0;
   g_sl_price             = 0;
   g_tp_price             = 0;
   g_ob_lo_at_entry       = 0;
   g_swing_lo_after_entry = 0;
   g_awaiting_entry       = false;
}

bool TradeAllowed(string &reason)
{
   if(!InpEnableTrading)                                    { reason = "EA disabled";      return false; }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))         { reason = "AutoTrading OFF";  return false; }
   if(g_risk.IsDailyLossBreached())          { reason = "Daily loss limit"; return false; }
   double dd = g_risk.GetCurrentDD();
   if(dd > 6.0)                                            { reason = StringFormat("DD %.1f%%>6%%", dd); return false; }
   double sp = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(sp > InpMaxSpreadPoints)                             { reason = StringFormat("Spread %d>%d", (int)sp, (int)InpMaxSpreadPoints); return false; }
   reason = "";
   return true;
}

void UpdateDash(bool ok, string reason)
{
   if(!InpShowDashboard) return;
   SDashboardState st;
   st.eaOn          = InpEnableTrading;
   st.strategy      = InpStrategyName + (g_awaiting_entry ? " [WAIT]" : "");
   st.tradingAllowed= ok;
   st.blockedReason = reason;
   st.ddPct         = g_risk.GetCurrentDD();
   st.spreadPoints  = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   g_dash.Render(st);
}

//+------------------------------------------------------------------+
//| OnTester — export trade log cho Python pipeline                   |
//+------------------------------------------------------------------+
double OnTester()
{
   HistorySelect(0, TimeCurrent());
   int total = HistoryDealsTotal();
   if(total == 0) return 0.0;

   string fn = InpStrategyName + "_trade_log.csv";
   int fh = FileOpen(fn, FILE_WRITE | FILE_CSV | FILE_ANSI);
   if(fh == INVALID_HANDLE) return 0.0;

   FileWrite(fh, "timestamp,symbol,strategy,direction,entry,sl,tp,exit,profit,commission,swap");
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(tk, DEAL_MAGIC)  != InpMagicNumber) continue;
      if(HistoryDealGetInteger(tk, DEAL_ENTRY)  != DEAL_ENTRY_OUT)  continue;
      datetime dt = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      string   dir= (HistoryDealGetInteger(tk, DEAL_TYPE) == DEAL_TYPE_BUY) ? "LONG" : "SHORT";
      FileWrite(fh,
         TimeToString(dt, TIME_DATE|TIME_MINUTES),
         _Symbol, InpStrategyName, dir,
         DoubleToString(HistoryDealGetDouble(tk, DEAL_PRICE),    _Digits),
         "0", "0",
         DoubleToString(HistoryDealGetDouble(tk, DEAL_PRICE),    _Digits),
         DoubleToString(HistoryDealGetDouble(tk, DEAL_PROFIT),   2),
         DoubleToString(HistoryDealGetDouble(tk, DEAL_COMMISSION),2),
         DoubleToString(HistoryDealGetDouble(tk, DEAL_SWAP),     2));
   }
   FileClose(fh);
   return 0.0;
}
//+------------------------------------------------------------------+
