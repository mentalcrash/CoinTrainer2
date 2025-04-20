from src.new.strategy.strategy_params import StrategyParams
from dataclasses import dataclass
from typing import List

@dataclass
class VolatilityBreakoutParams(StrategyParams):
    document_version: int = 1
    version: int = 1
    
    # 캔들 수 제한
    limit_candles: int = 30
    
    # EMA (지수이동평균) 관련 파라미터
    ema_short_period: int = 3    # 단기 EMA 기간
    ema_long_period: int = 9     # 장기 EMA 기간

    # Bollinger Bands 관련 파라미터
    bb_period: int = 20          # 볼린저 밴드 기간
    bb_multiplier: float = 2.0   # 볼린저 밴드 승수 (표준편차 배수)

    # 거래량 급증 관련 파라미터
    volume_period: int = 20      # 거래량 이동평균 기간
    volume_multiplier: float = 1.5 # 거래량 급증 판단 기준 승수 

    def to_str_list(self) -> List[str]:
        return [
            str(self.document_version),
            str(self.version),
            str(self.limit_candles),
            str(self.ema_short_period),
            str(self.ema_long_period),
            str(self.bb_period),
            str(self.bb_multiplier),
            str(self.volume_period),
            str(self.volume_multiplier)
        ]
    
    @classmethod
    def from_str_list(cls, str_list: List[str]) -> 'VolatilityBreakoutParams':
        return VolatilityBreakoutParams(
            document_version=int(str_list[0]),
            version=int(str_list[1]),
            limit_candles=int(str_list[2]),
            ema_short_period=int(str_list[3]),
            ema_long_period=int(str_list[4]),
            bb_period=int(str_list[5]),
            bb_multiplier=float(str_list[6]),
            volume_period=int(str_list[7]),
            volume_multiplier=float(str_list[8])
        )
    
    @classmethod
    def from_dict(cls, dict: dict) -> 'VolatilityBreakoutParams':
        return VolatilityBreakoutParams(
            document_version=int(dict['document_version']),
            version=int(dict['version']),
            limit_candles=int(dict['limit_candles']),
            ema_short_period=int(dict['ema_short_period']),
            ema_long_period=int(dict['ema_long_period']),
            bb_period=int(dict['bb_period']),
            bb_multiplier=float(dict['bb_multiplier']),
            volume_period=int(dict['volume_period']),
            volume_multiplier=float(dict['volume_multiplier'])
        )
    
    def get_prompt(self) -> str:
        return f"""
        EMA 기간: {self.ema_short_period} / {self.ema_long_period}
        Bollinger Bands 기간: {self.bb_period}
        거래량 이동평균 기간: {self.volume_period}
        거래량 급증 기준 승수: {self.volume_multiplier}
        """
        