import pandas as pd

from scripts.insight_formatter import format_backtest_summary


class XAUUSDSniperBacktester:
    def __init__(self, strategy):
        self.strategy = strategy
        self.trades = []

    def run(self, df_m15, df_h1, df_h4):
        """Simulates trading on historical dataframes with MTF support."""
        if len(df_m15) < 50 or df_h1 is None or df_h4 is None:
            print("Not enough data for backtesting.")
            return []

        # Calculate indicators for the whole df
        df_m15 = self.strategy.calculate_indicators(df_m15)
        
        # H1 and H4 trends are calculated at each point for simulation accuracy
        for i in range(50, len(df_m15) - 1):
            current_time = df_m15.iloc[i]['time']
            
            # Align H1 and H4 data to the current simulation time
            sub_h1 = df_h1[df_h1['time'] <= current_time]
            sub_h4 = df_h4[df_h4['time'] <= current_time]
            sub_m15 = df_m15.iloc[:i+1]
            
            signal = self.strategy.check_signals(sub_m15, sub_h1, sub_h4, current_spread=0) 
            
            if signal in ["BUY", "SELL"]:
                entry_price = df_m15.iloc[i]['close']
                atr_val = df_m15.iloc[i].get('atr')
                tp, sl = self.strategy.get_tp_sl(entry_price, signal, atr_value=atr_val)
                
                # Scan subsequent bars for TP/SL
                result = "OPEN"
                for j in range(i+1, len(df_m15)):
                    high = df_m15.iloc[j]['high']
                    low = df_m15.iloc[j]['low']
                    
                    if signal == "BUY":
                        if high >= tp:
                            result = "TP"
                            break
                        if low <= sl:
                            result = "SL"
                            break
                    else: # SELL
                        if low <= tp:
                            result = "TP"
                            break
                        if high >= sl:
                            result = "SL"
                            break
                
                self.trades.append({
                    "time": str(current_time),
                    "type": signal,
                    "entry": entry_price,
                    "tp": tp,
                    "sl": sl,
                    "result": result,
                    "atr": round(atr_val, 2) if atr_val else 0
                })
        
        return self.trades

    def summary(self):
        """Prints backtest results summary."""
        if not self.trades:
            print(format_backtest_summary([]))
            return
            
        trades_df = pd.DataFrame(self.trades)
        print(format_backtest_summary(self.trades))
        
        return trades_df
