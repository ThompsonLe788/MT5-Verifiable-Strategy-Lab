//+------------------------------------------------------------------+
//|  SMC_Structure_Indicator.mq5                                     |
//|  Phát hiện BOS, Order Block, FVG cho SMC/ICT strategy.           |
//|  Non-repaint: tất cả tín hiệu chỉ tính trên shift >= 1.          |
//+------------------------------------------------------------------+
#property copyright "MT5 Quant Lab"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_plots   0   // Tất cả vẽ qua objects, không dùng plot mặc định

//--- Input parameters
input int    InpSwingLookback  = 10;    // Bars nhìn lại để detect swing
input double InpOB_MinBodyPct  = 0.6;  // Body % tối thiểu của OB candle
input double InpFVG_MinGapATR  = 0.3;  // FVG size tối thiểu (ATR multiplier)
input int    InpOB_MaxAgeBars  = 50;   // OB expire sau N bars
input double InpSweepBuffer    = 0.1;  // ATR multiplier cho sweep
input bool   InpShowZones      = true; // Vẽ OB/FVG zones
input bool   InpShowBOS        = true; // Vẽ BOS lines
input bool   InpShowSwings     = false;// Vẽ swing labels

//--- Indicator buffers
double BOS_Direction[];  // Buffer 0: 1=Bull BOS / -1=Bear BOS / 0=None
double OB_High[];        // Buffer 1: Bullish OB high (valid nhất hiện tại)
double OB_Low[];         // Buffer 2: Bullish OB low
double FVG_High[];       // Buffer 3: Bullish FVG high
double FVG_Low[];        // Buffer 4: Bullish FVG low

//--- ATR handle
int    g_atr_handle;
double g_atr[];

//--- Max objects
#define MAX_OB_ZONES  5
#define MAX_FVG_ZONES 5
#define PREFIX        "SMC_"

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, BOS_Direction, INDICATOR_DATA);
   SetIndexBuffer(1, OB_High,       INDICATOR_DATA);
   SetIndexBuffer(2, OB_Low,        INDICATOR_DATA);
   SetIndexBuffer(3, FVG_High,      INDICATOR_DATA);
   SetIndexBuffer(4, FVG_Low,       INDICATOR_DATA);

   ArraySetAsSeries(BOS_Direction, true);
   ArraySetAsSeries(OB_High,  true);
   ArraySetAsSeries(OB_Low,   true);
   ArraySetAsSeries(FVG_High, true);
   ArraySetAsSeries(FVG_Low,  true);

   g_atr_handle = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(g_atr_handle == INVALID_HANDLE) return(INIT_FAILED);

   ArraySetAsSeries(g_atr, true);
   IndicatorSetString(INDICATOR_SHORTNAME, "SMC Structure");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, PREFIX);
   IndicatorRelease(g_atr_handle);
}

//+------------------------------------------------------------------+
int OnCalculate(const int      rates_total,
                const int      prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   if(rates_total < InpSwingLookback * 3 + 5) return(0);

   CopyBuffer(g_atr_handle, 0, 0, rates_total, g_atr);

   //--- Chỉ tính từ shift >= 1 (non-repaint)
   int limit = (prev_calculated <= 0)
               ? MathMin(rates_total - 1, 300)  // Lần đầu: tính 300 bars
               : rates_total - prev_calculated + 1;

   ArraySetAsSeries(time,  true);
   ArraySetAsSeries(high,  true);
   ArraySetAsSeries(low,   true);
   ArraySetAsSeries(open,  true);
   ArraySetAsSeries(close, true);

   for(int i = limit; i >= 1; i--)   // i >= 1: bỏ qua bar 0 (chưa close)
   {
      BOS_Direction[i] = 0;
      OB_High[i]  = EMPTY_VALUE;
      OB_Low[i]   = EMPTY_VALUE;
      FVG_High[i] = EMPTY_VALUE;
      FVG_Low[i]  = EMPTY_VALUE;

      if(i + InpSwingLookback * 2 + 3 >= rates_total) continue;

      double atr = g_atr[i];
      if(atr <= 0) continue;

      //--- Detect BOS
      double swing_high = SwingHigh(high, i + 1, InpSwingLookback);
      double swing_low  = SwingLow(low,   i + 1, InpSwingLookback);

      bool bos_up   = (swing_high > 0 && close[i] > swing_high);
      bool bos_down = (swing_low  > 0 && close[i] < swing_low);

      if(bos_up)   BOS_Direction[i] = 1.0;
      if(bos_down) BOS_Direction[i] = -1.0;

      //--- Detect Bullish Order Block (nếu BOS_UP)
      if(bos_up)
      {
         int ob_bar = FindBullishOB(open, high, low, close, i, InpOB_MinBodyPct);
         if(ob_bar >= 0)
         {
            OB_High[i] = high[ob_bar];
            OB_Low[i]  = low[ob_bar];
            DrawOBZone(time[ob_bar], time[i], high[ob_bar], low[ob_bar], i, true);
         }
      }

      //--- Detect Bullish FVG
      if(i + 2 < rates_total)
      {
         double fvg_lo = high[i + 2];
         double fvg_hi = low[i];
         if(fvg_hi > fvg_lo && (fvg_hi - fvg_lo) >= InpFVG_MinGapATR * atr)
         {
            FVG_High[i] = fvg_hi;
            FVG_Low[i]  = fvg_lo;
            DrawFVGZone(time[i + 2], time[i], fvg_lo, fvg_hi, i);
         }
      }

      //--- BOS Line
      if(InpShowBOS && (bos_up || bos_down) && swing_high > 0 && swing_low > 0)
      {
         double level = bos_up ? swing_high : swing_low;
         DrawBOSLine(time[i], level, bos_up, i);
      }
   }

   return(rates_total);
}

//+------------------------------------------------------------------+
//| Helpers                                                           |
//+------------------------------------------------------------------+

double SwingHigh(const double &high[], int from, int bars)
{
   double result = high[from];
   for(int k = from; k < from + bars; k++)
      if(k < ArraySize(high) && high[k] > result) result = high[k];
   return result;
}

double SwingLow(const double &low[], int from, int bars)
{
   double result = low[from];
   for(int k = from; k < from + bars; k++)
      if(k < ArraySize(low) && low[k] < result) result = low[k];
   return result;
}

int FindBullishOB(const double &open[], const double &high[],
                  const double &low[],  const double &close[],
                  int bos_bar, double min_body_pct)
{
   // Tìm candle bearish (đỏ) gần nhất trước bos_bar
   for(int k = bos_bar + 1; k < bos_bar + InpOB_MaxAgeBars && k < ArraySize(close); k++)
   {
      if(close[k] >= open[k]) continue;   // chỉ lấy candle đỏ
      double body  = MathAbs(close[k] - open[k]);
      double range = high[k] - low[k];
      if(range > 0 && body / range >= min_body_pct)
         return k;
   }
   return -1;
}

//+------------------------------------------------------------------+
//| Drawing                                                           |
//+------------------------------------------------------------------+

void DrawOBZone(datetime t1, datetime t2,
                double price_hi, double price_lo,
                int bar_idx, bool bullish)
{
   if(!InpShowZones) return;
   string name = PREFIX + "OB_" + IntegerToString(bar_idx);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, price_hi, t2, price_lo);
   color clr = bullish ? C'0,128,128' : C'205,92,92';
   ObjectSetInteger(0, name, OBJPROP_COLOR,     clr);
   ObjectSetInteger(0, name, OBJPROP_FILL,      true);
   ObjectSetInteger(0, name, OBJPROP_BACK,      true);
   ObjectSetInteger(0, name, OBJPROP_STYLE,     STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,     1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
}

void DrawFVGZone(datetime t1, datetime t2,
                 double price_lo, double price_hi,
                 int bar_idx)
{
   if(!InpShowZones) return;
   string name = PREFIX + "FVG_" + IntegerToString(bar_idx);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, price_hi, t2, price_lo);
   ObjectSetInteger(0, name, OBJPROP_COLOR,     C'255,215,0');
   ObjectSetInteger(0, name, OBJPROP_FILL,      true);
   ObjectSetInteger(0, name, OBJPROP_BACK,      true);
   ObjectSetInteger(0, name, OBJPROP_STYLE,     STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
}

void DrawBOSLine(datetime t, double level, bool bullish, int bar_idx)
{
   if(!InpShowBOS) return;
   string name = PREFIX + "BOS_" + IntegerToString(bar_idx);
   ObjectCreate(0, name, OBJ_HLINE, 0, t, level);
   ObjectSetInteger(0, name, OBJPROP_COLOR, bullish ? clrLime : clrRed);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}
//+------------------------------------------------------------------+
