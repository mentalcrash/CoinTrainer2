import logging
from src.new.scalping_trader import ScalpingTrader
def main():
    symbol = "AERGO"
    
    # log_manager: LogManager = LogManager(base_dir="logs/round", console_format="detailed")
    # log_manager.start_new_trading_session(symbol)
    
    # round_manager = RoundManager(log_manager=log_manager)
    # round_manager.run(symbol)
    logging.basicConfig(level=logging.INFO)
    scalping_trader = ScalpingTrader(market=f"KRW-{symbol}")
    scalping_trader.run_forever()

if __name__ == "__main__":
    main() 