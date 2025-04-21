from src.new.sheet.ai_generated_strategy_sheet import AiGeneratedStrategySheet, AiGeneratedStrategySheetData
from openai import OpenAI
import os
from typing import Tuple
from datetime import datetime
import re

from typing import Tuple, List
from src.new.strategy.parameter.signal_strategy import SignalStrategy
from src.new.strategy.strategy_params import StrategyParams
from src.new.models.bithumb.response import Candle, Orderbook, Trade, OrderbookUnit

class StrategyGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def create_prompt(self) -> Tuple[str, str]:
        template_code = open('src/new/strategy/template_signal.py', 'r').read()
        system_prompt = """
이 클래스는 코인 스캘핑 매매 시그널을 위한 클래스입니다.
당신은 최고의 소프트웨어 엔지니어로서, 최고의 수익률을 목표로 합니다.
정형화된 방법이 아닌 다양하고 창의적인 방법으로 매매 시그널을 구현해야 합니다.
코드는 즉시 실전에 투입할 수 있는 수준이어야 하며, 효율성과 가독성, 유지보수성이 높아야 합니다.
응답은 반드시 코드 형식으로 반환해주세요.
```python 태그는 사용하지 말고 순수 코딩만 반환해주세요.
exec() 실행 시 오류가 발생하지 않도록 주의해주세요.
"""
        
        user_prompt = f"""
이 클래스는 코인 스캘핑 매매 시그널을 위한 클래스입니다.
당신은 최고의 소프트웨어 엔지니어로서, 최고의 수익률을 목표로 합니다.
정형화된 방법이 아닌 다양하고 창의적인 방법으로 매매 시그널을 구현해야 합니다.
코드는 즉시 실전에 투입할 수 있는 수준이어야 하며, 효율성과 가독성, 유지보수성이 높아야 합니다.
응답은 반드시 코드 형식으로 반환해주세요.
```python 태그는 사용하지 말고 순수 코딩만 반환해주세요.
exec() 실행 시 오류가 발생하지 않도록 주의해주세요.

{template_code}
"""
        return  system_prompt, user_prompt
    
    def create_from_gpt(self, system_prompt: str, user_prompt: str, model: str = "gpt-4.1-mini-2025-04-14"):
        response = self.client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8
        )
        
        return response.output_text
    
    def generate_auto(self):
        system_prompt, user_prompt = self.create_prompt()
        code = self.create_from_gpt(system_prompt, user_prompt)
        return code

    def generate_latest(self, model: str = "gpt-4.1-mini-2025-04-14"):
        next_version = 1
        sheet = AiGeneratedStrategySheet()
        data_list = sheet.get_data_many(conditions={})
        if data_list:
            max_version = max(data.version for data in data_list)
            next_version = max_version + 1
        
        system_prompt, user_prompt = self.create_prompt()
        code = self.create_from_gpt(system_prompt, user_prompt, model)
        
        
        # 클래스 이름 찾기
        pattern = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*SignalStrategy\s*\)\s*:")
        match = pattern.search(code)
        
        # 결과 확인
        if match:
            class_name = match.group(1)
            print(f"SignalStrategy를 상속하는 클래스 이름 발견: {class_name}") # 출력: VolumeRsiEmaScalper
        else:
            raise Exception("SignalStrategy를 상속하는 클래스를 찾지 못했습니다.")
        
        try:
            execute_namespace = {'SignalStrategy': SignalStrategy, 
                                 'StrategyParams': StrategyParams,
                                 'Candle': Candle,
                                 'Orderbook': Orderbook,
                                 'Trade': Trade,
                                 'OrderbookUnit': OrderbookUnit}
                
            exec(code, execute_namespace)
            generated_class = execute_namespace.get(class_name)
            instance = generated_class('KRW-BTC', {'version': next_version, 'document_version': 1})
        except Exception as e:
            raise Exception(f"exec 실행 중 오류 발생: {e}")
            
        sheet_data = AiGeneratedStrategySheetData(
            version=next_version,
            creator=model,
            name=instance.get_name(),
            description=instance.get_description(),
            code=code,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            active=True
        )
        
        sheet.append(sheet_data)
        
