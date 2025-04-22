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
이 클래스는 초단기 암호화폐 스캘핑 매매 시그널 생성을 위한 클래스입니다.
당신은 최고의 소프트웨어 엔지니어로서, **안정적인 고수익률(목표 수익률: 최소 0.1% 이상/트레이드)을 달성하고, 리스크-리워드 비율(1:1.5 이상)을 확보하기 위해 최적의 지표와 로직을 창의적으로 조합합니다.**

▼ 사용 가능한 지표 카테고리 (복합적 Timeframe 권장)
① Trend      : SMA, EMA, WMA, ADX  
② Momentum   : RSI, CCI, Stoch, MACD, TSI  
③ Volatility : BollingerBands, ATR, Keltner, Donchian  
④ Volume     : OBV, VWAP, VolumeSurge, ChaikinAD  
⑤ Orderbook  : Spread, DepthImbalance, VWAPShift, TickRatio  

### 코드 생성 규칙 (업그레이드)
1. **서로 다른 카테고리에서 최소 2개, 최대 3개 지표를 선택하며**, 최소 두 가지 다른 timeframe(예: 1분, 3분, 5분)을 혼합하여 활용합니다.
2. 직전 응답(`previous_indicators`)과의 중복을 최대한 피하고, 최소 2개 이상 겹치지 않아야 합니다.
3. 매 생성 시 지표의 파라미터(기간, 임계값)는 반드시 변형하고, 단순 반복을 피하십시오.
4. 매매 진입 조건은 너무 엄격하지 않으면서도 명확한 진입 논리를 제공합니다. **"OR" 조건**을 적극적으로 활용하여 기회를 극대화합니다.
5. **시장 상태 판단(트렌드/횡보 등)을 위한 간단한 지표(예: ADX, Bollinger Band squeeze)를 최소 1개 포함하여 시장 상황을 먼저 평가한 뒤**, 전략의 공격성을 동적으로 조절합니다.
6. API 호출을 최소화하고 API 예외 상황을 철저히 처리하여, 전략 연속성을 반드시 보장하십시오.
7. 지표 계산 값과 상태 판단 과정을 self.logger로 명확히 로그에 출력합니다.
8. 코드 실행 시 반드시 오류가 없어야 하며, 논리적으로 정확한 코드만 반환합니다.
9. 코드만 반환하고, 별도의 태그(```python 등)는 사용하지 않습니다.
10. 창의성을 발휘하여 최고의 전략을 생성하십시오.
"""
        
        user_prompt = f"""
요구사항:
- 클래스와 메서드 이름은 전략 핵심을 간결히 나타내도록 명확하게 변경하십시오.
  (예: VolatilityBreakoutScalper, MultiTimeframeTrend 등)
- **반드시 should_buy()를 구현하고, 선택한 지표만 활용하십시오.**
- **시장 상태 판단을 위한 간단한 로직을 추가하고, 이를 바탕으로 전략의 진입 조건 강도를 동적으로 조절하십시오.**
- 반드시 set_target_and_stop_loss_price()를 구현하고 다음 조건을 충족하십시오.
    - self.target_price와 self.stop_loss_price는 반드시 현재 호가 및 변동성을 기준으로 최소 0.15% 이상 차이를 유지하십시오.
    - 지나치게 작거나 큰 틱 간격을 감지하여 자동 조정하십시오.
- 반드시 should_sell()를 구현하여 다음 조건을 충족하십시오.
    - 반환값은 Tuple[bool, str]로 의사결정과 명확한 사유를 포함합니다.
    - 최대 15분 경과 시 무조건 매도 처리하십시오.
    - 목표가 또는 손절가 터치 시 신속히 매도 처리하십시오.
- API 호출 횟수를 최소화하고 예외처리를 반드시 포함하십시오.
- 지표 계산 값 및 조건 만족 여부를 self.logger에 자세히 로그로 기록하십시오.
- 선택된 지표, timeframe, 사용된 조건(예: RSI 14(1분봉) < 35, EMA 5(3분봉) > EMA 15(3분봉))을 **get_description()에 정확히 기술하십시오.**
- 지난 응답에서 사용된 지표는 previous_indicators 리스트에 전달되며, 반드시 중복을 피하십시오.
- 캔들 및 데이터는 반드시 시간 오름차순 정렬된 것을 확인하십시오.
- 함수 시그니처 및 주석은 변경하지 않으며, 모든 주석은 한글로 작성하십시오.

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
