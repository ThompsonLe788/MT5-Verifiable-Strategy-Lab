//+------------------------------------------------------------------+
//|  SMC_Structure_Indicator.mq5                                     |
//|  BOS / CHoCH / Order Block / FVG / Equal Highs-Lows             |
//|                                                                  |
//|  Buffer 0: Structure_Signal                                      |
//|    2.0  = BOS_UP   (trend continuation — tìm OB long)           |
//|   -2.0  = BOS_DOWN                                               |
//|    1.0  = CHoCH_UP (reversal từ bear → EA không trade ngay)      |
//|   -1.0  = CHoCH_DOWN → EA EXIT lệnh LONG                        |
//|                                                                  |
//|  Non-repaint: tất cả signal chỉ tính tại shift >= 1.            |
//+------------------------------------------------------------------+
#property copyright "MT5 Quant Lab"
#property version   "1.10"
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_plots   0

//--- Inputs
input int    InpSwingLookback   = 10;
input double InpOB_MinBodyPct   = 0.6;
input double InpFVG_MinGapATR   = 0.3;
input int    InpOB_MaxAgeBars   = 50;
input double InpEqualHL_ATRTol  = 0.1;
input bool   InpShowZones       = true;
input bool   InpShowStructure   = true;
input bool   InpShowLiquidity   = true;

//--- Buffers
double Buf_Structure[];  // 0: BOS/CHoCH signal
double Buf_OB_High[];    // 1: OB high (forward-filled)
double Buf_OB_Low[];     // 2: OB low
double Buf_FVG_High[];   // 3: FVG high
double Buf_FVG_Low[];    // 4: FVG low

//--- Indicators
int g_atr;
double g_atr_val[];

//--- State tracking across bars (bias_state per OnCalculate pass)
#define BIAS_NONE  0
#define BIAS_BULL  1
#define BIAS_BEAR -1

#define BOS_UP      2.0
#define BOS_DOWN   -2.0
#define CHOCH_UP    1.0
#define CHOCH_DOWN -1.0

#define PREFIX "SMC_"

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, Buf_Structure, INDICATOR_DATA);
   SetIndexBuffer(1, Buf_OB_High,   INDICATOR_DATA);
   SetIndexBuffer(2, Buf_OB_Low,    INDICATOR_DATA);
   SetIndexBuffer(3, Buf_FVG_High,  INDICATOR_DATA);
   SetIndexBuffer(4, Buf_FVG_Low,   INDICATOR_DATA);

   for(int b = 0; b < 5; b++)
      PlotIndexSetDouble(b, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   ArraySetAsSeries(Buf_Structure, true);
   ArraySetAsSeries(Buf_OB_High,   true);
   ArraySetAsSeries(Buf_OB_Low,    true);
   ArraySetAsSeries(Buf_FVG_High,  true);
   ArraySetAsSeries(Buf_FVG_Low,   true);

   g_atr = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(g_atr == INVALID_HANDLE) return INIT_FAILED;
   ArraySetAsSeries(g_atr_val, true);

   IndicatorSetString(INDICATOR_SHORTNAME, "SMC Structure");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, PREFIX);
   IndicatorRelease(g_atr);
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
   int min_bars = InpSwingLookback * 2 + InpOB_MaxAgeBars + 10;
   if(rates_total < min_bars) return 0;

   CopyBuffer(g_atr, 0, 0, rates_total, g_atr_val);

   ArraySetAsSeries(time,  true);
   ArraySetAsSeries(high,  true);
   ArraySetAsSeries(low,   true);
   ArraySetAsSeries(open,  true);
   ArraySetAsSeries(close, true);

   //--- Tính từ cũ về mới để bias_state tích lũy đúng thứ tự lịch sử
   int limit = (prev_calculated <= 0)
               ? MathMin(rates_total - 1, 250)
               : rates_total - prev_calculated + 1;

   //--- Reset buffers trong vùng cần tính
   for(int i = limit; i >= 1; i--)
   {
      Buf_Structure[i] = 0;
      Buf_OB_High[i]   = EMPTY_VALUE;
      Buf_OB_Low[i]    = EMPTY_VALUE;
      Buf_FVG_High[i]  = EMPTY_VALUE;
      Buf_FVG_Low[i]   = EMPTY_VALUE;
   }

   //--- State: tracking bias và OB hiện tại đang forward-fill
   int    bias_state = BIAS_NONE;
   double ob_high    = EMPTY_VALUE;
   double ob_low     = EMPTY_VALUE;
   double fvg_high   = EMPTY_VALUE;
   double fvg_low    = EMPTY_VALUE;
   int    ob_age     = 0;

   //--- Quét từ cũ nhất đến bar gần nhất (i từ cao đến thấp, nhưng i=0 bị bỏ qua)
   for(int i = limit; i >= 1; i--)
   {
      if(i + InpSwingLookback + 3 >= rates_total) continue;

      double atr = g_atr_val[i];
      if(atr <= 0) continue;

      double sh = SwingHigh(high, i + 1, InpSwingLookback, rates_total);
      double sl = SwingLow(low,   i + 1, InpSwingLookback, rates_total);

      bool crossed_up   = (sh > 0 && close[i] > sh);
      bool crossed_down = (sl > 0 && close[i] < sl);

      //--- Phân loại BOS vs CHoCH theo bias_state
      if(crossed_up)
      {
         if(bias_state == BIAS_BULL)
         {
            //--- BOS_UP: trend bull tiếp tục
            Buf_Structure[i] = BOS_UP;
            //--- Tìm OB mới trước impulse này
            int ob_bar = FindBullishOB(open, high, low, close, i, atr, rates_total);
            if(ob_bar >= 0)
            {
               ob_high = high[ob_bar];
               ob_low  = low[ob_bar];
               ob_age  = 0;
               DrawOBZone(time[ob_bar], time[i], ob_high, ob_low, i, true);
            }
         }
         else
         {
            //--- CHoCH_UP: bias chuyển từ BEAR/NONE → BULL
            Buf_Structure[i] = CHOCH_UP;
            bias_state = BIAS_BULL;
            int ob_bar = FindBullishOB(open, high, low, close, i, atr, rates_total);
            if(ob_bar >= 0)
            {
               ob_high = high[ob_bar];
               ob_low  = low[ob_bar];
               ob_age  = 0;
            }
         }
         if(InpShowStructure) DrawStructureLabel(time[i], sh, Buf_Structure[i], i);
      }
      else if(crossed_down)
      {
         if(bias_state == BIAS_BEAR)
         {
            Buf_Structure[i] = BOS_DOWN;
         }
         else
         {
            //--- CHoCH_DOWN: bias flip BULL → BEAR → EA EXIT LONG
            Buf_Structure[i] = CHOCH_DOWN;
            bias_state = BIAS_BEAR;
            ob_high = EMPTY_VALUE;  // invalidate OB khi CHoCH
            ob_low  = EMPTY_VALUE;
         }
         if(InpShowStructure) DrawStructureLabel(time[i], sl, Buf_Structure[i], i);
      }

      //--- OB violated?
      if(ob_low != EMPTY_VALUE && close[i] < ob_low)
      {
         ob_high = EMPTY_VALUE;
         ob_low  = EMPTY_VALUE;
      }

      //--- OB expired?
      ob_age++;
      if(ob_age > InpOB_MaxAgeBars)
      {
         ob_high = EMPTY_VALUE;
         ob_low  = EMPTY_VALUE;
      }

      //--- Forward-fill OB
      if(ob_high != EMPTY_VALUE)
      {
         Buf_OB_High[i] = ob_high;
         Buf_OB_Low[i]  = ob_low;
      }

      //--- Detect Bullish FVG (i cần i+2 < rates_total)
      if(i + 2 < rates_total && bias_state == BIAS_BULL)
      {
         double gap_lo = high[i + 2];
         double gap_hi = low[i];
         if(gap_hi > gap_lo && (gap_hi - gap_lo) >= InpFVG_MinGapATR * atr)
         {
            //--- Chỉ lưu nếu overlap với OB
            bool overlaps = (ob_high != EMPTY_VALUE
                             && gap_lo < ob_high && gap_hi > ob_low);
            if(overlaps)
            {
               fvg_high = gap_hi;
               fvg_low  = gap_lo;
               DrawFVGZone(time[i + 2], time[i], fvg_low, fvg_high, i);
            }
         }
      }

      //--- Forward-fill FVG
      if(fvg_high != EMPTY_VALUE)
      {
         Buf_FVG_High[i] = fvg_high;
         Buf_FVG_Low[i]  = fvg_low;
      }

      //--- Equal Highs/Lows (Liquidity Pools)
      if(InpShowLiquidity && i + InpSwingLookback + 1 < rates_total)
         CheckLiquidityPool(high, low, time, i, atr, rates_total);
   }

   return rates_total;
}

//+------------------------------------------------------------------+
//| Helpers                                                           |
//+------------------------------------------------------------------+

double SwingHigh(const double &high[], int from, int bars, int total)
{
   double r = 0;
   for(int k = from; k < from + bars && k < total; k++)
      if(high[k] > r) r = high[k];
   return r;
}

double SwingLow(const double &low[], int from, int bars, int total)
{
   double r = DBL_MAX;
   for(int k = from; k < from + bars && k < total; k++)
      if(low[k] < r) r = low[k];
   return (r == DBL_MAX) ? 0 : r;
}

int FindBullishOB(const double &open[], const double &high[],
                  const double &low[], const double &close[],
                  int bos_bar, double atr, int total)
{
   //--- Tìm candle đỏ cuối cùng trước bos_bar, impulse phải >= 2 ATR
   for(int k = bos_bar + 1; k < bos_bar + 5 && k < total; k++)
   {
      if(close[k] >= open[k]) continue;
      double body  = open[k] - close[k];
      double range = high[k] - low[k];
      if(range <= 0) continue;
      if(body / range < InpOB_MinBodyPct) continue;
      //--- Kiểm tra impulse sau OB >= 2 ATR
      double impulse = high[bos_bar] - low[k];
      if(impulse >= 2.0 * atr) return k;
   }
   return -1;
}

void CheckLiquidityPool(const double &high[], const double &low[],
                        const datetime &time[], int bar, double atr, int total)
{
   int lookback = InpSwingLookback;
   for(int k = bar + 1; k < bar + lookback && k < total; k++)
   {
      if(MathAbs(high[bar] - high[k]) <= InpEqualHL_ATRTol * atr)
      {
         string name = PREFIX + "EQH_" + IntegerToString(bar) + "_" + IntegerToString(k);
         if(ObjectFind(0, name) < 0)
         {
            ObjectCreate(0, name, OBJ_TREND, 0, time[k], high[k], time[bar], high[bar]);
            ObjectSetInteger(0, name, OBJPROP_COLOR,  clrSilver);
            ObjectSetInteger(0, name, OBJPROP_STYLE,  STYLE_DOT);
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Drawing                                                           |
//+------------------------------------------------------------------+

void DrawOBZone(datetime t1, datetime t2,
                double ph, double pl, int idx, bool bull)
{
   if(!InpShowZones) return;
   string name = PREFIX + "OB_" + IntegerToString(idx);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, ph, t2, pl);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      bull ? C'0,128,128' : C'205,92,92');
   ObjectSetInteger(0, name, OBJPROP_FILL,       true);
   ObjectSetInteger(0, name, OBJPROP_BACK,       true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

void DrawFVGZone(datetime t1, datetime t2,
                 double pl, double ph, int idx)
{
   if(!InpShowZones) return;
   string name = PREFIX + "FVG_" + IntegerToString(idx);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, ph, t2, pl);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      C'255,215,0');
   ObjectSetInteger(0, name, OBJPROP_FILL,       true);
   ObjectSetInteger(0, name, OBJPROP_BACK,       true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

void DrawStructureLabel(datetime t, double price, double sig, int idx)
{
   string lbl, name = PREFIX + "STR_" + IntegerToString(idx);
   color  clr;

   if(sig == BOS_UP)       { lbl = "BOS↑";   clr = clrLimeGreen; }
   else if(sig == BOS_DOWN){ lbl = "BOS↓";   clr = clrTomato;    }
   else if(sig == CHOCH_DOWN){ lbl = "CHoCH↓"; clr = clrOrange;  } // EXIT signal — conspicuous
   else                    { lbl = "CHoCH↑"; clr = clrDodgerBlue; }

   ObjectCreate(0, name, OBJ_TEXT, 0, t, price);
   ObjectSetString(0,  name, OBJPROP_TEXT,      lbl);
   ObjectSetInteger(0, name, OBJPROP_COLOR,     clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,  8);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR,    ANCHOR_UPPER);
}
//+------------------------------------------------------------------+
