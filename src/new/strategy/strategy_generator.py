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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, 'template_signal.py')
        
        try:
            # 절대 경로와 UTF-8 인코딩으로 파일 열기
            template_code = open(template_path, 'r', encoding='utf-8').read()
        except FileNotFoundError:
            print(f"오류: 템플릿 파일({template_path})을 찾을 수 없습니다.")
            # 적절한 오류 처리 (예: 기본 템플릿 사용, 예외 다시 발생 등)
            raise # 또는 다른 처리
        except Exception as e:
            print(f"오류: 템플릿 파일({template_path})을 읽는 중 오류 발생: {e}")
            raise # 또는 다른 처리
        
        system_prompt = """
이 클래스는 초단기(15초 단위) 암호화폐 스캘핑 매매 시그널 생성을 위한 클래스입니다.
당신은 최고의 소프트웨어 엔지니어로서, **정확한 진입 판단으로 높은 승률을 유지하며 최소 0.1% 이상 목표 수익률과 리스크-리워드 비율(1:1.5 이상)을 확보할 수 있는 초단기 특화 전략을 창의적으로 설계합니다.**

▼ 필수 활용 지표 카테고리 (복합적 Timeframe 필수)
① Trend      : SMA, EMA, WMA, ADX  
② Momentum   : RSI, CCI, Stoch, MACD, TSI  
③ Volatility : BollingerBands, ATR, Keltner, Donchian  
④ Volume     : OBV, VWAP, VolumeSurge, ChaikinAD  
⑤ Orderbook  : Spread, DepthImbalance, VWAPShift, TickRatio  

### 초단기 특화 전략 생성 규칙 (중요!)
1. 서로 다른 카테고리에서 최소 2개, 최대 3개 지표를 선택하며, 반드시 초단기(1분), 단기(3분, 5분)의 서로 다른 Timeframe을 활용하여 전략을 구성합니다.
2. 15초마다 진입 판단이 이루어지므로, 반드시 **실시간 orderbook 데이터(매수/매도 압력, DepthImbalance, Spread)**를 포함하여 시장가 진입의 정확도를 극대화합니다.
3. **초단기(1분봉 기준) ATR을 활용해 목표가와 손절가를 매우 정밀하게 설정하며**, ATR의 0.3배~0.7배 구간 사이에서 좁게 목표가와 손절가를 책정하여 신속한 수익 실현 및 손절이 가능하게 합니다.
4. **잦은 매수 진입을 방지하기 위해 진입 조건의 민감도를 엄격히 설정하고, 단기 모멘텀(예: RSI, MACD 등)과 호가창의 명확한 매수 압력 조건을 모두 만족할 때만 진입합니다.**
5. API 호출은 orderbook 및 최근 trade 데이터만 실시간 호출하고, API 실패 시 매수 판단을 보류합니다.
6. 진입 조건 만족 시점과 ATR 값, 목표가, 손절가 설정 이유 등 모든 과정은 self.logger에 명확히 기록합니다.
7. 코드 실행 시 오류가 없고, 논리적으로 정확한 코드만 반환합니다.
8. 반환 시 코드 외 별도의 태그(```python 등)는 사용하지 않습니다.
"""
        
        user_prompt = f"""
요구사항:
- 클래스와 메서드 이름을 초단기(15초 단위) 전략의 핵심을 명확히 나타내도록 설정하십시오.
  (예: MicroMomentumScalper, OrderbookPressureScalper 등)
- should_buy()의 반환 값은 반드시 Tuple[bool, float, float]이며,
  매매 결정 여부(True/False), 목표가(target_price), 손절가(stop_loss_price)를 순서대로 반환합니다.
  - 예시: `(True, 25000.0, 24950.0)`
- 15초마다 매수 여부를 판단하므로, 진입 결정은 반드시 **실시간 호가창(Orderbook)의 매수 우위 조건과 초단기 모멘텀 지표 조건을 모두 만족할 때만 True를 반환**합니다.
- 진입 직후 목표가 및 손절가는 **1분봉 ATR의 0.3~0.7배 이내에서 좁게 설정**하여 초단기 변동성에 적합하도록 합니다.
- **캔들, orderbook, 최근 체결(trade) 데이터를 포함한 모든 데이터는 반드시 호출 시마다 실시간 API를 사용하여 최신 상태를 유지합니다. 절대로 데이터를 캐싱하지 않습니다.**
  - API 호출 실패 시 즉시 진입 판단을 보류하고 매수를 진행하지 않습니다.
- 진입 조건 평가 과정, ATR 계산, 목표가 및 손절가 설정 등 모든 주요 판단 과정과 결정 이유를 self.logger에 매우 상세히 기록합니다.
- 선택된 지표, timeframe, 조건(예: RSI(1분,14)<30, DepthImbalance(실시간)>120%) 등을 get_description()에 명확히 기술하십시오.
- 함수 시그니처 및 주석은 변경하지 않으며, 모든 주석은 한글로 작성하십시오.

다음은 수정된 함수 템플릿 예시입니다.

다음은 코드 템플릿입니다:

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

    def generate_latest(self, model: str = "o4-mini-2025-04-16") -> AiGeneratedStrategySheetData:
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
        return sheet_data

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
