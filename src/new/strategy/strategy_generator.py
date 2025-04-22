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
당신은 최고의 소프트웨어 엔지니어로서, **다양한 조합**으로 최고 수익률을 노립니다.

▼ 지표 카테고리
① Trend      : SMA, EMA, WMA, ADX
② Momentum   : RSI, CCI, Stoch, MACD, TSI
③ Volatility : BollingerBands, ATR, Keltner, Donchian
④ Volume     : OBV, VWAP, VolumeSurge, ChaikinAD
⑤ Orderbook  : Spread, DepthImbalance, VWAPShift, TickRatio

규칙
1. 코드 생성 시 다른 카테고리에서 **3~4개 지표를 무작위 선택**하여 조합한다.  
2. **직전 응답과 지표가 2개 이상 겹치면 안 된다.**  
   (필요 시 `previous_indicators` 변수를 참고)  
3. 지표의 디테일한 값도 코드 생성 시 마다 다른게 되도록 한다.
4. 코드만 반환(``` 태그 금지)ㆍexec 오류 없어야 한다.
"""
        
        user_prompt = f"""
요구사항
- 'Template' 이라는 단어를 전략 핵심을 드러내는 이름으로 교체하십시오.
- 반드시 should_buy() 를 구현하고, 선택한 3~4개 지표만 사용하십시오.
- 중복 API 호출을 피하고 예외를 처리해 연속성을 보장하십시오.
- 수치 기준(예: RSI < 25, EMA 5 > EMA 20)을 get_description()에 명시하십시오.
- 지표를 로그에 출력하세요
- **지난 응답에 사용된 지표 목록은 previous_indicators 변수로 전달됩니다.**  
  새 전략은 이 목록과 2개 이상 겹치면 안 됩니다.
- 함수 시그니처·매개변수·반환값은 변경 불가, 주석은 한글로 작성하십시오.

아래 템플릿 외에는 참고 자료가 없습니다.

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
    
    def generate_auto(self, model: str = "gpt-4.1-mini-2025-04-14"):
        system_prompt, user_prompt = self.create_prompt()
        code = self.create_from_gpt(system_prompt, user_prompt, model)
        return code

    def generate_latest(self, model: str = "gpt-4.1-mini-2025-04-14") -> Tuple[int, str]:
        next_version = 1
        sheet = AiGeneratedStrategySheet()
        data_list = sheet.get_data_many(conditions={})
        if data_list:
            max_version = max(data.version for data in data_list)
            next_version = max_version + 1
        
        system_prompt, user_prompt = self.create_prompt()
        code = self.create_from_gpt(system_prompt, user_prompt, model)
        
        instance = self.execute_code('KRW-BTC', next_version, code)
            
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
        return next_version, code

    def execute_code(self, market: str, version: int, code: str) -> SignalStrategy:
        execute_namespace = {'SignalStrategy': SignalStrategy, 
                             'StrategyParams': StrategyParams,
                             'Candle': Candle,
                             'Orderbook': Orderbook,
                             'Trade': Trade,
                             'OrderbookUnit': OrderbookUnit}
        
        # 클래스 이름 찾기
        pattern = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*SignalStrategy\s*\)\s*:")
        match = pattern.search(code)
        
        # 결과 확인
        if match:
            class_name = match.group(1)
            print(f"SignalStrategy를 상속하는 클래스 이름 발견: {class_name}") # 출력: VolumeRsiEmaScalper
        else:
            raise Exception("SignalStrategy를 상속하는 클래스를 찾지 못했습니다.")

        exec(code, execute_namespace)
        generated_class = execute_namespace.get(class_name)
        instance = generated_class(market, {'version': version, 'document_version': 1})
        return instance
