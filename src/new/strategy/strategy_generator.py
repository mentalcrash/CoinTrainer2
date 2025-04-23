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

▼ 사용 가능한 지표 카테고리 (복합적 Timeframe 필수)
① Trend      : SMA, EMA, WMA, ADX  
② Momentum   : RSI, CCI, Stoch, MACD, TSI  
③ Volatility : BollingerBands, ATR, Keltner, Donchian  
④ Volume     : OBV, VWAP, VolumeSurge, ChaikinAD  
⑤ Orderbook  : Spread, DepthImbalance, VWAPShift, TickRatio  

### 전략 생성 규칙
이 클래스는 초단기 암호화폐 스캘핑 매매 시그널 생성을 위한 클래스입니다.  
당신은 최고의 소프트웨어 엔지니어로서, **안정적인 고수익률(목표 수익률: 최소 0.1% 이상/트레이드)을 달성하고, 리스크-리워드 비율(1:1.5 이상)을 확보하기 위해 최적의 지표와 로직을 창의적으로 조합합니다.**

▼ 사용 가능한 지표 카테고리 (복합적 Timeframe 필수)
① Trend      : SMA, EMA, WMA, ADX  
② Momentum   : RSI, CCI, Stoch, MACD, TSI  
③ Volatility : BollingerBands, ATR, Keltner, Donchian  
④ Volume     : OBV, VWAP, VolumeSurge, ChaikinAD  
⑤ Orderbook  : Spread, DepthImbalance, VWAPShift, TickRatio  

### 전략 생성 규칙
1. **서로 다른 카테고리에서 최소 2개, 최대 3개 지표를 선택**하며, 반드시 두 가지 이상의 timeframe(예: 1분, 3분, 5분)을 혼합하여 활용합니다.
2. 직전 응답(`previous_indicators`)과 최소 2개 이상 겹치지 않도록 항상 신선한 지표 조합을 구성합니다.
3. 매 생성 시 지표의 파라미터(기간, 임계값)를 항상 변형하여 전략의 다양성을 유지합니다.
4. **시장 상태 판단을 위한 명확한 지표(예: ADX, Bollinger Band squeeze 등)를 최소 1개 포함하여**,  
   현재 시장 상태를 "횡보", "추세", "변동성 확대" 중 하나로 정확히 분류하고 상태를 평가합니다.
   - 시장 상태에 따라 전략의 진입 조건 강도를 동적으로 조정합니다.
   - 예시: ADX가 25 이상이고 상승 추세라면 적극적인 전략, ADX가 하락하거나 20 미만이면 보수적인 전략
5. **캔들 데이터, orderbook 및 최근 체결(trade) 데이터는 반드시 호출 시마다 실시간 API를 호출하여 최신 데이터를 사용하십시오.**
   - 절대 실시간 마켓 데이터(캔들 데이터, orderbook, trades)를 캐싱하지 마십시오.
   - API 호출 실패 시 진입 판단을 보류하고 매수를 하지 않도록 명시적 예외처리 로직을 구현합니다.
6. 최근 ATR을 기반으로 **목표가 및 손절가 설정 로직을 포함하고**, 진입 시 예상 리스크-리워드 비율(최소 1:1.5)을 충족할 때만 매수 진입을 허용합니다.
7. **모든 지표 계산 값, 시장 상태 평가 결과, 진입 조건 평가 과정 및 이유를 self.logger에 명확하고 세부적으로 로그로 기록합니다.**
8. 코드 실행 시 반드시 오류가 없어야 하며, 논리적이고 정확한 코드만 반환합니다.
9. 반환 시 코드 외 별도의 태그(```python 등)는 사용하지 않습니다.
10. 전략의 창의성과 안정성, 수익률을 동시에 고려한 최적의 전략을 생성합니다.
"""
        
        user_prompt = f"""
요구사항:
- 클래스와 메서드 이름을 전략의 핵심을 명확히 나타내도록 설정하십시오.
  (예: VolatilityBreakoutScalper, AdaptiveTrendMomentum 등)
- **should_buy()의 반환 값을 Tuple[bool, float, float]로 구현하고,**  
  매매 결정 여부(True/False), 목표가(target_price), 손절가(stop_loss_price)를 순서대로 반환하십시오.
  - 예시: `(True, 25000.0, 24750.0)`
- **시장 상태(추세/횡보/변동성 확대)를 판단하는 별도의 명확한 로직을 반드시 포함**하고, 이 평가 결과에 따라 전략의 진입 조건 민감도를 동적으로 조정하십시오.
- 진입 조건 평가 시 **최근 ATR을 계산하여 목표가 및 손절가를 명확히 설정하고, 진입 시 예상 리스크-리워드 비율(최소 1:1.5)을 충족할 때만 진입하도록 명시하십시오.**
- **캔들 데이터, orderbook 및 최근 체결(trade) 데이터는 반드시 실시간 API 호출을 통해 얻어 최신 데이터를 사용하십시오.**
  - 캔들 데이터 및 orderbook, trade 데이터의 캐싱은 절대 금지합니다.
  - orderbook 및 trade API 호출 실패 시에는 진입 판단을 보류하고 매수를 진행하지 않습니다. 이 과정을 self.logger에 명확히 기록합니다.
- **모든 지표 값, 시장 상태 평가 결과, 진입 조건 만족 여부 및 결정 과정을 self.logger에 상세히 로그로 기록하십시오.**
- 선택된 지표, timeframe, 명확한 조건(예: RSI(1분,14)<35, EMA(3분,5)>EMA(3분,15), ADX(5분,14) 상승 중)을 get_description()에 정확히 기술하십시오.
- 지난 응답에서 사용된 지표는 previous_indicators 리스트로 전달되며, 중복을 반드시 피하십시오.
- 캔들 및 거래 데이터는 반드시 시간 오름차순 정렬된 것을 확인하고, 정렬 상태를 self.logger로 기록하십시오.
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
