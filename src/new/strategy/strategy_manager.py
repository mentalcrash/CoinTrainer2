import json
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.strategy.volatility_breakout_signal import VolatilityBreakoutSignal
from src.trading_logger import TradingLogger
from src.new.sheet.volatility_breakout_sheet import VolatilityBreakoutSheet
from src.new.strategy.parameter.volatility_breakout_params import VolatilityBreakoutParams
from src.new.strategy.strategy_params import StrategyParams
from src.new.sheet.strategy_score_sheet import StrategyScoreSheet, StrategyScoreSheetData
from src.new.scalping_analyzer import Result
from typing import Optional

class StrategyManager:
    def __init__(self, config_path: str = 'src/new/config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        self.trading_logger = TradingLogger()
        
    def load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)
        
    def get_strategy(self, market: str) -> SignalStrategy:
        strategy_config = self.config.get(market, None)
        if not strategy_config:
            strategy_config = self.config.get('Other')
            
        strategy_name = strategy_config.get('strategy')
        default_params = strategy_config.get('params')
        
        # TODO 나중에 베스트 로직 추가
        best_strategy_score = self.find_strategy_score(market, strategy_name)
        
        if best_strategy_score:
            params = self.find_strategy_params(strategy_name, best_strategy_score.document_version, best_strategy_score.version)
            if not params:
                raise ValueError(f"지원하지 않는 전략입니다: {strategy_name}")
            return VolatilityBreakoutSignal(market, params)
        else:
            params = self.find_strategy_params(strategy_name, default_params['document_version'])
            if not params:
                params = self.get_strategy_params_from_dict(strategy_name, default_params)
                self.create_strategy_params(market, strategy_name, params)
            self.create_strategy_score(market, strategy_name, params.document_version, params.version)
            return VolatilityBreakoutSignal(market, params)

    def get_strategy_params_from_dict(self, strategy: str, default_params: dict) -> StrategyParams:
        if strategy == 'VolatilityBreakoutSignal':
            return VolatilityBreakoutParams.from_dict(default_params)
        else:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
        
    def accumulate_strategy_score(self, market: str, strategy: SignalStrategy, result: Result):
        if strategy.get_name() == 'VolatilityBreakoutSignal':
            sheet = StrategyScoreSheet()
            sheet.update_data(conditions={"market": market, 
                                          "strategy": strategy.get_name(),
                                          "document_version": strategy.params.document_version,
                                          "version": strategy.params.version},
                            updates={"pnl": result.acc_pnl,
                                    "profit_rate": result.acc_profit_rate,
                                    "trade_count": result.trade_count,
                                    "win_count": result.win_count,
                                    "loss_count": result.loss_count,
                                    "win_rate": result.win_rate,
                                    "loss_rate": result.loss_rate,
                                    "entry_total_price": result.entry_total_price,
                                    "exit_total_price": result.exit_total_price,
                                    "elapsed_seconds": result.acc_elapsed_seconds,
                                    })
            
        else:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
        
    def find_strategy_score(self, market: str, strategy: str, document_version: Optional[int] = None, version: Optional[int] = None) -> StrategyScoreSheetData:
        if strategy == 'VolatilityBreakoutSignal':
            sheet = StrategyScoreSheet()
            conditions = {"market": market, "strategy": strategy}
            if document_version:
                conditions["document_version"] = document_version
            if version:
                conditions["version"] = version
            data_list = sheet.get_data_many(conditions=conditions)
            if data_list:
                return StrategyScoreSheetData.from_dict(data_list[-1])
            else:
                return None
        else:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
    
    def create_strategy_score(self, market: str, strategy: str, document_version: int, version: int):
        if strategy == 'VolatilityBreakoutSignal':
            sheet = StrategyScoreSheet()
            sheet.append(StrategyScoreSheetData(market=market, 
                                                strategy=strategy, 
                                                document_version=document_version, 
                                                version=version, 
                                                pnl=0, 
                                                profit_rate=0, 
                                                trade_count=0, 
                                                win_count=0, 
                                                loss_count=0, 
                                                win_rate=0, 
                                                loss_rate=0, 
                                                entry_total_price=0, 
                                                exit_total_price=0,
                                                elapsed_seconds=0))
        else:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
    
    def find_strategy_params(self, strategy: str, document_version: int, version: Optional[int] = None) -> StrategyParams:
        if strategy == 'VolatilityBreakoutSignal':
            sheet = VolatilityBreakoutSheet(document_version)
            conditions = {"document_version": document_version}
            if version:
                conditions["version"] = version
            data_list = sheet.get_data_many(conditions=conditions)
            if data_list:
                data = data_list[-1]
                if data:
                    return VolatilityBreakoutParams.from_dict(data)
                else:
                    return None
            else:
                return None
        else:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
        return None
    
    def create_strategy_params(self, market: str, strategy: str, params: StrategyParams):
        if strategy == 'VolatilityBreakoutSignal':
            sheet = VolatilityBreakoutSheet(params.document_version)
            sheet.append(params)
        else:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
