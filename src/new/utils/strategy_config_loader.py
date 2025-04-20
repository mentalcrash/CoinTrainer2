import json
from new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.strategy.volatility_breakout_signal import VolatilityBreakoutSignal

class StrategyManager:
    def __init__(self, config_path: str = 'src/new/config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        
    def load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)
        
    def get_strategy_config(self, market: str) -> SignalStrategy:
        strategy_config = self.config.get(market, None)
        if not strategy_config:
            strategy_config = self.config.get('Other')
            
        strategy = strategy_config.get('strategy')
        params = strategy_config.get('params')
        
        if strategy == 'VolatilityBreakoutSignal':
            return VolatilityBreakoutSignal(market, params)
        
        raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
    