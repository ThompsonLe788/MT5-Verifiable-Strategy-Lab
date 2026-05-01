//+------------------------------------------------------------------+
//| Wyckoff_Phase_Indicator.mq5                                     |
//| Detect: Trading Range, Spring, BOS                               |
//| Non-repaint: signals only on closed bars (shift >= 1)           |
//+------------------------------------------------------------------+
#property copyright "MT5 Quant Lab"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 5
#property indicator_plots   2

//--- Plot: Phase signal (hidden — read by EA via iCustom)
#property indicator_label1  "Phase"
#property indicator_type1   DRAW_NONE
#property indicator_color1  clrNONE

//--- Plot: BOS signal (hidden)
#property indicator_label2  "BOS"
#property indicator_type2   DRAW_NONE
#property indicator_color2  clrNONE

//--- Inputs
input int    InpRangeLookback   = 20;    // Bars tìm range (H4)
input double InpRangeMinATR     = 1.0;   // Range height tối thiểu × ATR(14)
input double InpSpringATRBuf    = 0.2;   // ATR buffer dưới Spring cho SL
input int    InpBOS_SwingBars   = 10;    // Bars H1 tìm swing high cho BOS
input double InpVolumeRatio     = 1.2;   // Volume ratio xác nhận BOS
input bool   InpUseVolumeFilter = true;  // false = bỏ volume filter

//--- Indicator buffers
double BufPhase[];    // 1=BULL, -1=BEAR, 0=RANGE
double BufSpring[];   // Spring price level
double BufAR[];       // Trading Range High
double BufSC[];       // Trading Range Low
double BufBOS[];      // 1=BOS_LONG confirmed, 0=none

//--- ATR handle
int    g_atrHandle = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, BufPhase,  INDICATOR_DATA);
   SetIndexBuffer(1, BufSpring, INDICATOR_DATA);
   SetIndexBuffer(2, BufAR,     INDICATOR_DATA);
   SetIndexBuffer(3, BufSC,     INDICATOR_DATA);
   SetIndexBuffer(4, BufBOS,    INDICATOR_DATA);

   ArraySetAsSeries(BufPhase,  true);
   ArraySetAsSeries(BufSpring, true);
   ArraySetAsSeries(BufAR,     true);
   ArraySetAsSeries(BufSC,     true);
   ArraySetAsSeries(BufBOS,    true);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0.0);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, 0.0);

   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(g_atrHandle == INVALID_HANDLE)
   {
      Print("ATR handle failed");
      return INIT_FAILED;
   }

   IndicatorSetString(INDICATOR_SHORTNAME,
      "Wyckoff[" + (string)InpRangeLookback + "]");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   ObjectsDeleteAll(0, "WYK_");
   ChartRedraw();
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   if(rates_total < InpRangeLookback * 2 + 14) return 0;

   double atr[];
   ArraySetAsSeries(atr, true);
   if(CopyBuffer(g_atrHandle, 0, 0, rates_total, atr) <= 0) return 0;

   // Non-repaint: start from shift=1 (last confirmed bar)
   int startBar = (prev_calculated <= 0) ? rates_total - InpRangeLookback - 2 : 1;
   startBar = MathMax(startBar, InpRangeLookback + 2);

   for(int i = startBar; i >= 1; i--)
   {
      BufPhase[i]  = 0.0;
      BufSpring[i] = 0.0;
      BufAR[i]     = 0.0;
      BufSC[i]     = 0.0;
      BufBOS[i]    = 0.0;

      int lookback = MathMin(InpRangeLookback, rates_total - i - 1);
      if(lookback < 5) continue;

      // --- Find SC (lowest low in lookback) ---
      int   scIdx = i;
      double sc   = low[i];
      for(int k = i; k <= i + lookback && k < rates_total; k++)
         if(low[k] < sc) { sc = low[k]; scIdx = k; }

      // --- Find AR (highest high after SC) ---
      double ar = 0.0;
      for(int k = i; k <= scIdx && k >= 1; k--)
         ar = MathMax(ar, high[k]);
      if(ar <= sc) continue;

      double rangeHeight = ar - sc;
      double atrVal = (atr[i] > 0) ? atr[i] : 1e-10;

      if(rangeHeight < InpRangeMinATR * atrVal) continue;

      // --- Check no close above AR (still in range) ---
      bool breakoutOccurred = false;
      for(int k = i; k <= scIdx; k++)
         if(close[k] > ar) { breakoutOccurred = true; break; }
      if(breakoutOccurred) continue;

      // --- Find Spring (Low < SC but Close > SC) ---
      bool   springFound = false;
      double springLevel = sc;
      for(int k = i; k <= scIdx; k++)
      {
         if(low[k] < sc && close[k] > sc)
         {
            springFound  = true;
            springLevel  = low[k];
            break;
         }
      }
      if(!springFound) continue;

      // --- BULL bias confirmed ---
      BufPhase[i]  = 1.0;
      BufSC[i]     = sc;
      BufAR[i]     = ar;
      BufSpring[i] = springLevel;

      // --- BOS check (breakout above AR with close) ---
      // BOS = close[i] > ar, and this bar is closed (i >= 1)
      if(close[i] > ar)
      {
         bool volOk = true;
         if(InpUseVolumeFilter && rates_total > 20)
         {
            double volMA = 0;
            for(int v = i + 1; v <= i + 20 && v < rates_total; v++)
               volMA += (double)tick_volume[v];
            volMA /= 20.0;
            volOk = ((double)tick_volume[i] >= InpVolumeRatio * volMA);
         }
         if(volOk) BufBOS[i] = 1.0;
      }
   }

   // --- Draw objects on chart ---
   DrawZones(time, high, low, rates_total);

   return rates_total;
}

//+------------------------------------------------------------------+
void DrawZones(const datetime &time[], const double &high[],
               const double &low[], int total)
{
   // Remove old objects
   ObjectsDeleteAll(0, "WYK_");

   int zonesDrawn = 0;
   for(int i = 1; i < total && zonesDrawn < 3; i++)
   {
      if(BufPhase[i] != 1.0) continue;
      if(BufAR[i] <= 0 || BufSC[i] <= 0) continue;

      string tag = "WYK_" + (string)i;

      // Range rectangle
      string rectName = tag + "_rect";
      ObjectCreate(0, rectName, OBJ_RECTANGLE, 0,
                   time[i + InpRangeLookback], BufSC[i],
                   time[MathMax(i-1, 0)], BufAR[i]);
      ObjectSetInteger(0, rectName, OBJPROP_COLOR,   clrForestGreen);
      ObjectSetInteger(0, rectName, OBJPROP_STYLE,   STYLE_DOT);
      ObjectSetInteger(0, rectName, OBJPROP_WIDTH,   1);
      ObjectSetInteger(0, rectName, OBJPROP_FILL,    true);
      ObjectSetInteger(0, rectName, OBJPROP_BACK,    true);
      ObjectSetInteger(0, rectName, OBJPROP_SELECTABLE, false);

      // Spring arrow
      if(BufSpring[i] > 0)
      {
         string sprName = tag + "_spring";
         ObjectCreate(0, sprName, OBJ_ARROW, 0, time[i], BufSpring[i]);
         ObjectSetInteger(0, sprName, OBJPROP_ARROWCODE, 234);
         ObjectSetInteger(0, sprName, OBJPROP_COLOR,     clrOrangeRed);
         ObjectSetInteger(0, sprName, OBJPROP_WIDTH,     2);
         ObjectSetInteger(0, sprName, OBJPROP_SELECTABLE, false);
      }

      // BOS label
      if(BufBOS[i] == 1.0)
      {
         string bosName = tag + "_bos";
         ObjectCreate(0, bosName, OBJ_TEXT, 0, time[i], BufAR[i]);
         ObjectSetString (0, bosName, OBJPROP_TEXT,     "BOS");
         ObjectSetInteger(0, bosName, OBJPROP_COLOR,    clrDodgerBlue);
         ObjectSetString (0, bosName, OBJPROP_FONT,     "Consolas");
         ObjectSetInteger(0, bosName, OBJPROP_FONTSIZE, 9);
         ObjectSetInteger(0, bosName, OBJPROP_SELECTABLE, false);
      }

      zonesDrawn++;
   }

   // --- Indicator info label (top-left) ---
   string lblName = "WYK_INFO";
   if(ObjectFind(0, lblName) < 0)
      ObjectCreate(0, lblName, OBJ_LABEL, 0, 0, 0);

   string phase = "RANGE";
   double atr14  = 0;
   double atrbuf[];
   ArraySetAsSeries(atrbuf, true);
   if(CopyBuffer(g_atrHandle, 0, 0, 2, atrbuf) > 0) atr14 = atrbuf[1];

   if(BufPhase[1] == 1.0)  phase = "BULL";
   if(BufPhase[1] == -1.0) phase = "BEAR";

   string infoText = StringFormat(
      "[Wyckoff]  Phase:%s  Spring:%s  BOS:%s  ATR:%.2f",
      phase,
      (BufSpring[1] > 0 ? DoubleToString(BufSpring[1], _Digits) : "—"),
      (BufBOS[1]   == 1.0 ? "YES" : "—"),
      atr14);

   ObjectSetString (0, lblName, OBJPROP_TEXT,      infoText);
   ObjectSetInteger(0, lblName, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
   ObjectSetInteger(0, lblName, OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(0, lblName, OBJPROP_YDISTANCE, 20);
   ObjectSetInteger(0, lblName, OBJPROP_COLOR,     clrWhiteSmoke);
   ObjectSetString (0, lblName, OBJPROP_FONT,      "Consolas");
   ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE,  9);
   ObjectSetInteger(0, lblName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, lblName, OBJPROP_HIDDEN,    true);

   ChartRedraw();
}
