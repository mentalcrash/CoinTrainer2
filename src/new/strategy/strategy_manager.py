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
from src.new.sheet.ai_strategy_score_sheet import AiStrategyScoreSheet, AiStrategyScoreSheetData
from src.new.sheet.ai_generated_strategy_sheet import AiGeneratedStrategySheet, AiGeneratedStrategySheetData
from src.new.strategy.strategy_generator import StrategyGenerator
class StrategyManager:
    def __init__(self, config_path: str = 'src/new/config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        self.trading_logger = TradingLogger()
        self.strategy_generator = StrategyGenerator()
        
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
     
    def get_next_strategy_data(self, verison: int) -> SignalStrategy:
        strategy_sheet = AiGeneratedStrategySheet()
        conditions = {"active": 'TRUE'}
        strategy_data_list = strategy_sheet.get_data_many(conditions=conditions)
        if strategy_data_list:
            # version 보다 큰 버전 중 가장 작은 버전
            strategy_data_list = [data for data in strategy_data_list if data.version > verison]
            if strategy_data_list:
                return min(strategy_data_list, key=lambda x: x.version)
            else:
                sheet_data = self.strategy_generator.generate_latest()
                return sheet_data.version
        else:
            sheet_data = self.strategy_generator.generate_latest()
            return sheet_data.version

    def get_ai_strategy(self, market: str) -> SignalStrategy:
        score_sheet = AiStrategyScoreSheet()
        conditions = {"market": market}
        score_dict_list = score_sheet.get_data_many(conditions=conditions)
        if score_dict_list:
            score_list = [AiStrategyScoreSheetData.from_dict(score) for score in score_dict_list]
            current_version = max([score.version for score in score_list])
            strategy_sheet = AiGeneratedStrategySheet()
            conditions = {"version": current_version, "active": "TRUE"}
            strategy_data_list = strategy_sheet.get_data_many(conditions=conditions)
            if strategy_data_list:
                strategy_data = strategy_data_list[-1]
                return self.strategy_generator.execute_code(market, strategy_data.version, strategy_data.code)
            else:
                strategy_data = self.get_next_strategy_data(current_version)
                score_sheet.append(AiStrategyScoreSheetData(market=market, version=strategy_data.version, pnl=0, trade_count=0, win_count=0, entry_total_price=0, fee=0, elapsed_seconds=0))
                return self.strategy_generator.execute_code(market, strategy_data.version, strategy_data.code)                
        else:
            strategy_sheet = AiGeneratedStrategySheet()
            conditions = {"active": True}
            data_list = strategy_sheet.get_data_many(conditions=conditions)
            if data_list:
                strategy_data = data_list[0]
                score_sheet.append(AiStrategyScoreSheetData(market=market, version=strategy_data.version, pnl=0, trade_count=0, win_count=0, entry_total_price=0, fee=0, elapsed_seconds=0))
                return self.strategy_generator.execute_code(market, strategy_data.version, strategy_data.code)
            else:
                sheet_data = self.strategy_generator.generate_latest()
                score_sheet.append(AiStrategyScoreSheetData(market=market, version=sheet_data.version, pnl=0, trade_count=0, win_count=0, entry_total_price=0, fee=0, elapsed_seconds=0))
                return self.strategy_generator.execute_code(market, sheet_data.version, sheet_data.code)                
            
    def create_next_score_sheet(self, market: str) -> AiStrategyScoreSheet:
        score_sheet = AiStrategyScoreSheet()
        score_dict_list = score_sheet.get_data_many(conditions={"market": market})
        current_version = 0
        if score_dict_list:
            score_list = [AiStrategyScoreSheetData.from_dict(score) for score in score_dict_list]
            current_version = max([score.version for score in score_list])
            
        strategy_data = self.get_next_strategy_data(current_version)
            
        score_sheet.append(AiStrategyScoreSheetData(market=market, version=strategy_data.version, pnl=0, trade_count=0, win_count=0, entry_total_price=0, fee=0, elapsed_seconds=0))

    def get_strategy_params_from_dict(self, strategy: str, default_params: dict) -> StrategyParams:
        if strategy == 'VolatilityBreakoutSignal':
            return VolatilityBreakoutParams.from_dict(default_params)
        else:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
        
    def accumulate_strategy_score(self, market: str, strategy: SignalStrategy, result: Result):
        score_sheet = AiStrategyScoreSheet()
        score_sheet.update_data(
            conditions={
                "market": market,
                "version": strategy.params['version']
            },
            updates={
                "pnl": result.acc_pnl,
                "trade_count": result.trade_count,
                "win_count": result.win_count,
                "entry_total_price": result.entry_total_price,
                "elapsed_seconds": result.acc_elapsed_seconds,
                "fee": result.fee
            }
        )
    
    def find_ai_strategy_score(self, market: str, version: int) -> AiStrategyScoreSheetData:
        score_sheet = AiStrategyScoreSheet()
        conditions = {"market": market,
                      "version": version}
        score_dict_list = score_sheet.get_data_many(conditions=conditions)
        if score_dict_list:
            return AiStrategyScoreSheetData.from_dict(score_dict_list[-1])
        else:
            return None
        
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


        