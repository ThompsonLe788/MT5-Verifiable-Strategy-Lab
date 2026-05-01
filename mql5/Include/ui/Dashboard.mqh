//+------------------------------------------------------------------+
//| Dashboard.mqh — EA status dashboard renderer                    |
//+------------------------------------------------------------------+
#pragma once
#include "Theme.mqh"

//+------------------------------------------------------------------+
struct SDashboardState
{
   bool     eaOn;
   bool     tradingAllowed;
   string   blockedReason;
   string   symbol;
   string   strategy;
   string   tf1State;
   string   tf2State;
   string   tf3State;
   string   lastSignal;
   double   riskPct;
   double   dailyPL;
   double   ddPct;
   int      openTrades;
   int      spreadPoints;
   bool     spreadHigh;
   string   lastError;
};

//+------------------------------------------------------------------+
class CDashboard
{
private:
   long     m_chartId;
   string   m_prefix;     // unique prefix for object names
   int      m_corner;
   int      m_xOff;
   int      m_yOff;
   int      m_fontSize;

   string   ObjName(int row) { return m_prefix + "row_" + (string)row; }

   void     SetLabel(int row, const string text, color clr)
   {
      string name = ObjName(row);
      if(ObjectFind(m_chartId, name) < 0)
      {
         ObjectCreate(m_chartId, name, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(m_chartId, name, OBJPROP_CORNER,    m_corner);
         ObjectSetInteger(m_chartId, name, OBJPROP_XDISTANCE, m_xOff);
         ObjectSetInteger(m_chartId, name, OBJPROP_YDISTANCE, m_yOff + row * DASH_LINE_H);
         ObjectSetInteger(m_chartId, name, OBJPROP_SELECTABLE,false);
         ObjectSetInteger(m_chartId, name, OBJPROP_HIDDEN,    true);
         ObjectSetString (m_chartId, name, OBJPROP_FONT,      FONT_NAME);
         ObjectSetInteger(m_chartId, name, OBJPROP_FONTSIZE,  m_fontSize);
      }
      ObjectSetString (m_chartId, name, OBJPROP_TEXT,  text);
      ObjectSetInteger(m_chartId, name, OBJPROP_COLOR, clr);
   }

public:
   CDashboard() : m_chartId(0), m_corner(CORNER_RIGHT_UPPER),
                  m_xOff(DASH_X_OFFSET), m_yOff(DASH_Y_OFFSET),
                  m_fontSize(FONT_SIZE_MD) {}

   void Init(long chartId, const string magicStr,
             int corner = CORNER_RIGHT_UPPER, int fontSize = FONT_SIZE_MD)
   {
      m_chartId  = chartId;
      m_prefix   = "QT_DASH_" + magicStr + "_";
      m_corner   = corner;
      m_fontSize = fontSize;
   }

   void Render(const SDashboardState &s)
   {
      // Row 0: EA status
      color eaClr = s.eaOn ? CLR_OK : CLR_BLOCKED;
      SetLabel(0, "EA: " + (s.eaOn ? "ON" : "OFF"), eaClr);

      // Row 1: Trading allowed
      color tradClr = s.tradingAllowed ? CLR_OK : CLR_BLOCKED;
      SetLabel(1, "Trade: " + (s.tradingAllowed ? "ALLOWED" : "BLOCKED"), tradClr);

      // Row 2: Blocked reason (empty if allowed)
      color rsnClr = s.tradingAllowed ? CLR_NEUTRAL : CLR_WARNING;
      string rsn = s.tradingAllowed ? "" : s.blockedReason;
      SetLabel(2, rsn, rsnClr);

      // Row 3: Symbol / Strategy
      SetLabel(3, s.symbol + " | " + s.strategy, CLR_TEXT);

      // Row 4: TF states
      SetLabel(4, "TF1:" + s.tf1State + " TF2:" + s.tf2State + " TF3:" + s.tf3State, CLR_NEUTRAL);

      // Row 5: Last signal
      SetLabel(5, "Signal: " + s.lastSignal, CLR_TEXT);

      // Row 6: Risk / P/L
      color plClr = s.dailyPL >= 0 ? CLR_OK : CLR_RISK;
      SetLabel(6, StringFormat("Risk:%.2f%% PL:%.2f%%", s.riskPct, s.dailyPL), plClr);

      // Row 7: DD / Exposure
      color ddClr = s.ddPct < 3.0 ? CLR_OK
                  : s.ddPct < 5.0 ? CLR_WARNING
                  :                  CLR_CRITICAL;
      SetLabel(7, StringFormat("DD:%.2f%% Trades:%d", s.ddPct, s.openTrades), ddClr);

      // Row 8: Spread
      color spClr = s.spreadHigh ? CLR_WARNING : CLR_OK;
      SetLabel(8, "Spread: " + (string)s.spreadPoints + (s.spreadHigh ? " HIGH" : " OK"), spClr);

      // Row 9: Last error (only if non-empty)
      if(s.lastError != "")
         SetLabel(9, "ERR: " + s.lastError, CLR_CRITICAL);
      else
         SetLabel(9, "", CLR_NEUTRAL);

      ChartRedraw(m_chartId);
   }

   void Remove()
   {
      for(int i = 0; i <= 9; i++)
         ObjectDelete(m_chartId, ObjName(i));
      ChartRedraw(m_chartId);
   }
};
