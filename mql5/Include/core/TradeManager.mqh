//+------------------------------------------------------------------+
//| TradeManager.mqh — Order execution with SL mandatory policy     |
//+------------------------------------------------------------------+
#ifndef TRADEMANAGER_MQH
#define TRADEMANAGER_MQH
#include "Logger.mqh"
#include "RiskManager.mqh"

#define MAX_RETRY     3
#define RETRY_DELAY   500   // ms

//+------------------------------------------------------------------+
class CTradeManager
{
private:
   string         m_symbol;
   long           m_magic;
   CLogger*       m_logger;
   CRiskManager*  m_risk;
   string         m_comment;

   bool IsRetryable(int code)
   {
      return code == TRADE_RETCODE_REQUOTE      ||
             code == TRADE_RETCODE_PRICE_CHANGED ||
             code == TRADE_RETCODE_TRADE_DISABLED;
   }

   bool IsHardFail(int code)
   {
      return code == TRADE_RETCODE_INVALID_STOPS  ||
             code == TRADE_RETCODE_NO_MONEY       ||
             code == TRADE_RETCODE_MARKET_CLOSED;
   }

public:
   ulong   LastTicket;

   CTradeManager() : LastTicket(0) {}

   void Init(const string symbol, long magic,
             CLogger* logger, CRiskManager* risk,
             const string comment = "QT_PORTFOLIO")
   {
      m_symbol  = symbol;
      m_magic   = magic;
      m_logger  = logger;
      m_risk    = risk;
      m_comment = comment;
   }

   // ------------------------------------------------------------------
   // Open position — SL must be set before calling
   // ------------------------------------------------------------------
   bool OpenPosition(ENUM_ORDER_TYPE type, double lot,
                     double slPrice, double tpPrice)
   {
      // Guard: SL bắt buộc
      if(slPrice <= 0.0)
      {
         m_logger.LogError("OpenPosition", 0, "BLOCKED_NO_SL");
         return false;
      }

      double entryPrice = (type == ORDER_TYPE_BUY)
                        ? SymbolInfoDouble(m_symbol, SYMBOL_ASK)
                        : SymbolInfoDouble(m_symbol, SYMBOL_BID);

      // Guard: SL validation
      if(!m_risk.ValidateSL(entryPrice, slPrice, type))
      {
         m_logger.LogError("OpenPosition", 0, "BLOCKED_INVALID_STOPS");
         return false;
      }

      // Guard: portfolio risk
      if(m_risk.IsPortfolioRiskBreached())
      {
         m_logger.LogDecision("ENTRY", "BLOCKED", "BLOCKED_PORTFOLIO_RISK",
            m_risk.GetRiskPct(), 0, "", "", "", "");
         return false;
      }

      MqlTradeRequest req = {};
      MqlTradeResult  res = {};

      req.action   = TRADE_ACTION_DEAL;
      req.symbol   = m_symbol;
      req.volume   = lot;
      req.type     = type;
      req.price    = entryPrice;
      req.sl       = slPrice;
      req.tp       = tpPrice;
      req.magic    = m_magic;
      req.comment  = m_comment;
      req.deviation= 10;
      req.type_filling = ORDER_FILLING_IOC;

      for(int attempt = 0; attempt < MAX_RETRY; attempt++)
      {
         bool sent = OrderSend(req, res);
         if(sent && res.retcode == TRADE_RETCODE_DONE)
         {
            LastTicket = res.deal;
            m_logger.Info(StringFormat("Order opened: ticket=%d lot=%.2f sl=%.5f tp=%.5f",
               LastTicket, lot, slPrice, tpPrice));
            return true;
         }

         if(IsHardFail(res.retcode))
         {
            m_logger.LogError("OpenPosition", res.retcode,
               StringFormat("Hard fail: %d", res.retcode));
            return false;
         }

         if(attempt < MAX_RETRY - 1 && IsRetryable(res.retcode))
         {
            Sleep(RETRY_DELAY);
            // Refresh price
            req.price = (type == ORDER_TYPE_BUY)
                      ? SymbolInfoDouble(m_symbol, SYMBOL_ASK)
                      : SymbolInfoDouble(m_symbol, SYMBOL_BID);
         }
      }

      m_logger.LogError("OpenPosition", res.retcode,
         StringFormat("Failed after %d retries: %d", MAX_RETRY, res.retcode));
      return false;
   }

   // ------------------------------------------------------------------
   // Close position by ticket
   // ------------------------------------------------------------------
   bool ClosePosition(ulong ticket)
   {
      if(!PositionSelectByTicket(ticket)) return false;

      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)
         PositionGetInteger(POSITION_TYPE);
      double volume = PositionGetDouble(POSITION_VOLUME);

      MqlTradeRequest req = {};
      MqlTradeResult  res = {};

      req.action   = TRADE_ACTION_DEAL;
      req.symbol   = m_symbol;
      req.volume   = volume;
      req.type     = (posType == POSITION_TYPE_BUY)
                   ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      req.price    = (posType == POSITION_TYPE_BUY)
                   ? SymbolInfoDouble(m_symbol, SYMBOL_BID)
                   : SymbolInfoDouble(m_symbol, SYMBOL_ASK);
      req.position = ticket;
      req.magic    = m_magic;
      req.deviation= 10;
      req.type_filling = ORDER_FILLING_IOC;

      bool sent = OrderSend(req, res);
      if(sent && res.retcode == TRADE_RETCODE_DONE)
      {
         m_logger.Info(StringFormat("Position closed: ticket=%d", ticket));
         return true;
      }

      m_logger.LogError("ClosePosition", res.retcode);
      return false;
   }

   // ------------------------------------------------------------------
   // Close partial volume
   // ------------------------------------------------------------------
   bool ClosePartial(ulong ticket, double lots)
   {
      if(!PositionSelectByTicket(ticket)) return false;
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      MqlTradeRequest req = {};
      MqlTradeResult  res = {};
      req.action   = TRADE_ACTION_DEAL;
      req.symbol   = m_symbol;
      req.volume   = lots;
      req.type     = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      req.price    = (posType == POSITION_TYPE_BUY)
                   ? SymbolInfoDouble(m_symbol, SYMBOL_BID)
                   : SymbolInfoDouble(m_symbol, SYMBOL_ASK);
      req.position = ticket;
      req.magic    = m_magic;
      req.deviation= 10;
      req.type_filling = ORDER_FILLING_IOC;
      bool sent = OrderSend(req, res);
      if(sent && res.retcode == TRADE_RETCODE_DONE)
      {
         m_logger.Info(StringFormat("Partial close: ticket=%d lots=%.2f", ticket, lots));
         return true;
      }
      m_logger.LogError("ClosePartial", res.retcode);
      return false;
   }

   // ------------------------------------------------------------------
   // Move SL (only to breakeven or tighter — never widen)
   // ------------------------------------------------------------------
   bool ModifySL(ulong ticket, double newSL)
   {
      if(!PositionSelectByTicket(ticket)) return false;

      double currentSL = PositionGetDouble(POSITION_SL);
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)
         PositionGetInteger(POSITION_TYPE);

      // Hard rule: không nới SL
      if(posType == POSITION_TYPE_BUY  && newSL < currentSL) return false;
      if(posType == POSITION_TYPE_SELL && newSL > currentSL) return false;

      MqlTradeRequest req = {};
      MqlTradeResult  res = {};
      req.action   = TRADE_ACTION_SLTP;
      req.symbol   = m_symbol;
      req.position = ticket;
      req.sl       = newSL;
      req.tp       = PositionGetDouble(POSITION_TP);

      bool sent = OrderSend(req, res);
      if(!sent || res.retcode != TRADE_RETCODE_DONE)
         m_logger.LogError("ModifySL", res.retcode);

      return sent && (res.retcode == TRADE_RETCODE_DONE);
   }

   // ------------------------------------------------------------------
   // Check open position for this EA
   // ------------------------------------------------------------------
   bool HasOpenPosition()
   {
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == m_symbol &&
            PositionGetInteger(POSITION_MAGIC) == m_magic)
            return true;
      }
      return false;
   }

   ulong GetOpenTicket()
   {
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionGetSymbol(i) == m_symbol &&
            PositionGetInteger(POSITION_MAGIC) == m_magic)
            return PositionGetInteger(POSITION_TICKET);
      }
      return 0;
   }
};
#endif // TRADEMANAGER_MQH
