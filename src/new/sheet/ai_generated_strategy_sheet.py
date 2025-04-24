from src.new.sheet.sheet import Sheet
from dataclasses import dataclass, fields
from datetime import datetime

@dataclass
class AiGeneratedStrategySheetData:
    version: int
    creator: str
    name: str
    description: str
    code: str
    created_at: datetime
    active: bool
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AiGeneratedStrategySheetData':
        data['created_at'] = datetime.strptime(data['created_at'], '%Y-%m-%d %H:%M:%S') 
        data['active'] = True if data['active'] == 'True' or 'TRUE' else False
        return cls(**data)
    
    def to_str_list(self) -> list[str]:
        return [str(getattr(self, field.name)) for field in fields(self)]   

class AiGeneratedStrategySheet(Sheet):
    def __init__(self):
        super().__init__()
        
    def get_sheet_name(self) -> str:
        return "AI Generated Strategy"
    
    def get_headers(self) -> list[str]:
        return [field.name for field in fields(AiGeneratedStrategySheetData)]
    
    def append(self, data: AiGeneratedStrategySheetData):
        self.trading_logger.append_values(self.get_sheet_name(), [data.to_str_list()])
        
    def get_data_many(self, conditions: dict) -> list[AiGeneratedStrategySheetData]:
        data = super().get_data_many(conditions)
        if data:
            return [AiGeneratedStrategySheetData.from_dict(row) for row in data]
        return []
    