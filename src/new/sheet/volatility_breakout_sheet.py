from src.new.sheet.sheet import Sheet
from src.new.strategy.parameter.volatility_breakout_params import VolatilityBreakoutParams
class VolatilityBreakoutSheet(Sheet):
    def __init__(self, document_version: int):
        self.document_version = document_version
        super().__init__()
        
    def get_sheet_name(self) -> str:
        return f"Volatility Breakout {self.document_version}"
    
    def get_headers(self) -> list[str]:
        return ["document_version", "version", "limit_candles", "ema_short_period", "ema_long_period", "bb_period", "bb_multiplier", "volume_period", "volume_multiplier"]

    def append(self, data: VolatilityBreakoutParams):
        self.trading_logger.append_values(self.get_sheet_name(), [data.to_str_list()])