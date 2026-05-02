//+------------------------------------------------------------------+
//| Theme.mqh — Color palette and font constants                    |
//+------------------------------------------------------------------+
#ifndef THEME_MQH
#define THEME_MQH

//--- Dashboard colors
#define CLR_OK        clrLimeGreen
#define CLR_BLOCKED   clrTomato
#define CLR_WARNING   clrGold
#define CLR_RISK      clrOrange
#define CLR_CRITICAL  clrRed
#define CLR_NEUTRAL   clrSilver
#define CLR_TEXT      clrWhiteSmoke
#define CLR_BG        (color)0x1A1A1A    // dark background

//--- Chart object colors
#define CLR_ENTRY_LINE   clrDodgerBlue
#define CLR_SL_LINE      clrTomato
#define CLR_TP_LINE      clrLimeGreen
#define CLR_RANGE_BOX    (color)0x1A3A1A  // dark green tint
#define CLR_SPRING       clrOrangeRed
#define CLR_BOS_LABEL    clrDodgerBlue

//--- Font
#define FONT_NAME     "Consolas"
#define FONT_SIZE_SM  8
#define FONT_SIZE_MD  10
#define FONT_SIZE_LG  12

//--- Dashboard layout
#define DASH_X_OFFSET  15
#define DASH_Y_OFFSET  20
#define DASH_LINE_H    16
#define DASH_WIDTH     220
#endif // THEME_MQH
