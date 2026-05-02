//+------------------------------------------------------------------+
//| IStrategy.mqh — Strategy interface (abstract base class)        |
//| Mọi strategy phải implement interface này.                       |
//+------------------------------------------------------------------+
#ifndef ISTRATEGY_MQH
#define ISTRATEGY_MQH

enum ENUM_SIGNAL_TYPE
{
   SIGNAL_NONE  = 0,
   SIGNAL_LONG  = 1,
   SIGNAL_SHORT = -1,
};

enum ENUM_TF_STATE
{
   TF_STATE_NONE  = 0,
   TF_STATE_BULL  = 1,
   TF_STATE_BEAR  = -1,
   TF_STATE_RANGE = 2,
   TF_STATE_SETUP = 3,
   TF_STATE_READY = 4,
   TF_STATE_WAIT  = 5,
};

//+------------------------------------------------------------------+
class IStrategy
{
public:
   // --- Core signal interface ---
   virtual bool            CheckSignal(ENUM_SIGNAL_TYPE &signal) = 0;
   virtual double          GetSLPrice(ENUM_SIGNAL_TYPE signal)   = 0;
   virtual double          GetTPPrice(ENUM_SIGNAL_TYPE signal, double slPrice) = 0;

   // --- Validation ---
   virtual bool            IsSignalValid()     = 0;   // candle confirmed, not preview
   virtual bool            IsConflict()        = 0;   // TF alignment conflict

   // --- State reporting (for dashboard) ---
   virtual ENUM_TF_STATE   GetTF1State()       = 0;
   virtual ENUM_TF_STATE   GetTF2State()       = 0;
   virtual ENUM_TF_STATE   GetTF3State()       = 0;
   virtual string          GetTF1StateText()   = 0;
   virtual string          GetTF2StateText()   = 0;
   virtual string          GetTF3StateText()   = 0;
   virtual string          GetLastSignalText() = 0;
   virtual string          GetStrategyName()   = 0;

   // --- Lifecycle ---
   virtual bool            OnInit()   = 0;
   virtual void            OnDeinit() = 0;
   virtual void            OnTick()   = 0;   // update internal state
};
#endif // ISTRATEGY_MQH
