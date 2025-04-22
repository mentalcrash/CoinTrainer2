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
당신은 최고의 소프트웨어 엔지니어로서, 시장 진입 기회를 높이고 다양한 지표의 창의적인 조합으로 최고 수익률을 목표로 합니다.

▼ 사용 가능한 지표 카테고리
① Trend      : SMA, EMA, WMA, ADX  
② Momentum   : RSI, CCI, Stoch, MACD, TSI  
③ Volatility : BollingerBands, ATR, Keltner, Donchian  
④ Volume     : OBV, VWAP, VolumeSurge, ChaikinAD  
⑤ Orderbook  : Spread, DepthImbalance, VWAPShift, TickRatio  

### 코드 생성 규칙
1. 코드 생성 시 서로 다른 카테고리에서 **2~3개의 지표를 무작위 선택**하여 조합합니다.
2. 직전 응답(`previous_indicators`)과의 지표 중복을 최소화하고, **2개 이상 겹치지 않게 합니다**.
3. 선택된 지표의 기간, 임계값 등의 세부 파라미터는 매 코드 생성 시마다 **다르게 변형**하십시오.
4. 너무 엄격한 조건(예: RSI < 20, ATR 지나치게 작게 설정)은 피하고, **적절한 수준으로 조건을 완화**하여 시장 진입 기회를 증가시키십시오.
5. 지표 간 조건을 'and' 만 사용하는 대신, 필요 시 'or' 조건을 추가하여 시장 진입 확률을 높일 수 있습니다.
6. 코드는 즉시 실행 가능해야 하며, **반드시 exec() 실행 시 오류가 없어야 합니다**.
7. 지표의 논리적인 계산 오류는 절대 있어선 안됩니다.
8. 코드만 반환(``` 태그 금지)합니다.
"""
        
        user_prompt = f"""
요구사항:
- 클래스와 메서드 이름에서 'Template'을 전략 핵심을 명확히 나타내는 이름으로 변경하십시오.
  예시: VolumeSpikeScalper, MomentumBreakout 등 명확한 전략명을 사용
- **반드시 should_buy()를 구현하고, 선택한 2~3개의 지표만 활용하십시오.**
- API 호출 횟수를 최소화하고, API 실패 시 예외처리하여 전략 연속성을 보장하십시오.
- **지표 조건은 너무 엄격하지 않게 설정하여 자주 시장에 진입할 수 있도록 하십시오.**
- 지표 계산값을 명확히 로그에 출력하고, 반드시 self.logger를 사용하십시오.
- 선택된 지표와 구체적인 조건(예: RSI < 35, EMA 5 > EMA 15 등)을 **get_description()에 명확히 명시하십시오.**
- **지난 응답에서 사용한 지표 목록은 previous_indicators로 전달되며, 새 전략은 이 목록과 2개 이상 겹치지 않아야 합니다.**
- 캔들 및 데이터 사용 시 반드시 시간순 오름차순 정렬을 확인하십시오.
- 함수 시그니처, 매개변수, 반환값은 변경 불가하며, 모든 주석은 한글로 작성하십시오.

아래 템플릿 코드 외에는 참고 자료가 없습니다.

{template_code}
"""
        return  system_prompt, user_prompt
    
    def create_from_gpt(self, system_prompt: str, user_prompt: str, model: str = "gpt-4.1-mini-2025-04-14"):
        response = self.client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        return response.output_text
    
    def generate_auto(self, model: str = "gpt-4.1-mini-2025-04-14"):
        system_prompt, user_prompt = self.create_prompt()
        code = self.create_from_gpt(system_prompt, user_prompt, model)
        return code

    def generate_latest(self, model: str = "o4-mini-2025-04-16") -> Tuple[int, str]:
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
