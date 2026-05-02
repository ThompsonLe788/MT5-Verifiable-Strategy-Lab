//+------------------------------------------------------------------+
//| ChartSetup.mqh — Auto chart configuration on EA attach          |
//+------------------------------------------------------------------+
#ifndef CHARTSETUP_MQH
#define CHARTSETUP_MQH
#include "Theme.mqh"

//+------------------------------------------------------------------+
class CChartSetup
{
private:
   long m_chartId;

public:
   CChartSetup() : m_chartId(0) {}

   void Init(long chartId = 0) { m_chartId = chartId; }

   // ------------------------------------------------------------------
   // Apply minimal professional theme
   // ------------------------------------------------------------------
   void ApplyMinimalTheme()
   {
      long id = m_chartId;

      // Grid off
      ChartSetInteger(id, CHART_SHOW_GRID,        false);
      // Chart shift (space on right for dashboard)
      ChartSetInteger(id, CHART_SHIFT,             true);
      // Auto scroll
      ChartSetInteger(id, CHART_AUTOSCROLL,        true);
      // Candlestick mode
      ChartSetInteger(id, CHART_MODE,              CHART_CANDLES);
      // Scale
      ChartSetInteger(id, CHART_SCALE,             3);
      // No volume by default
      ChartSetInteger(id, CHART_SHOW_VOLUMES,      CHART_VOLUME_HIDE);
      // No OHLC on top
      ChartSetInteger(id, CHART_SHOW_OHLC,         false);
      // No bid line
      ChartSetInteger(id, CHART_SHOW_BID_LINE,     false);
      // No ask line
      ChartSetInteger(id, CHART_SHOW_ASK_LINE,     false);
      // No period separators
      ChartSetInteger(id, CHART_SHOW_PERIOD_SEP,   false);

      // Dark background
      ChartSetInteger(id, CHART_COLOR_BACKGROUND,  CLR_BG);
      ChartSetInteger(id, CHART_COLOR_FOREGROUND,  CLR_TEXT);
      ChartSetInteger(id, CHART_COLOR_GRID,        clrDimGray);
      ChartSetInteger(id, CHART_COLOR_CANDLE_BULL, clrLimeGreen);
      ChartSetInteger(id, CHART_COLOR_CANDLE_BEAR, clrTomato);
      ChartSetInteger(id, CHART_COLOR_CHART_UP,    clrLimeGreen);
      ChartSetInteger(id, CHART_COLOR_CHART_DOWN,  clrTomato);

      ChartRedraw(id);
   }

   // ------------------------------------------------------------------
   // Set timeframe
   // ------------------------------------------------------------------
   void SetTimeframe(ENUM_TIMEFRAMES tf)
   {
      ChartSetSymbolPeriod(m_chartId, ChartSymbol(m_chartId), tf);
   }

   // ------------------------------------------------------------------
   // Load indicator onto chart
   // ------------------------------------------------------------------
   bool LoadIndicator(const string indicatorPath, int subwindow = 0)
   {
      // iCustom-style load via ChartIndicatorAdd is available in MQL5
      // indicatorPath: relative to MQL5/Indicators, e.g. "Wyckoff_Phase_Indicator"
      int handle = iCustom(NULL, 0, indicatorPath);
      if(handle == INVALID_HANDLE)
      {
         Print("[ChartSetup] Indicator load failed: ", indicatorPath);
         return false;
      }
      // Note: ChartIndicatorAdd requires indicator handle
      bool ok = ChartIndicatorAdd(m_chartId, subwindow, handle);
      if(!ok)
         Print("[ChartSetup] ChartIndicatorAdd failed: ", indicatorPath);
      return ok;
   }
};
#endif // CHARTSETUP_MQH
