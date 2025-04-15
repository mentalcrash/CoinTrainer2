
from src.round.manager import RoundManager
from src.utils.log_manager import LogManager

def main():
    symbol = "AERGO"
    
    log_manager: LogManager = LogManager(base_dir="logs/round", console_format="detailed")
    log_manager.start_new_trading_session(symbol)
    
    round_manager = RoundManager(log_manager=log_manager)
    round_manager.run(symbol)

if __name__ == "__main__":
    main() 