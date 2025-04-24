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

### 초단기 특화 전략 생성 규칙
1. 서로 다른 카테고리에서 최소 2개, 최대 3개 지표를 선택하며 전략을 구성합니다.
2. 15초마다 진입 판단이 이루어지므로, 반드시 **실시간 orderbook 데이터 사용합니다.
3. 매수 결정을 위해서 다음의 3단계로 진행합니다.
   - 각 단계에서 반드시 **1개의 조건만 선택**하여 사용합니다.
   - 세 단계 중 하나라도 조건을 만족하지 않으면 진입하지 않습니다.
    1. 시장 방향 확인 (Market Direction: 추세 필터)
        - 주요 지표 예시:
	        - EMA(9) vs EMA(21) → 골든크로스 여부
	        - ADX > 20 → 추세 강도 존재
	        - WMA 상승 중 + 가격이 그 위에 존재
    2. 진입 모멘텀 감지 (Entry Momentum: 진입 조건 판단)
        - 주요 지표 예시:
            - RSI(14) > 50 → 매수 압력 존재
            - MACD Signal 상향 돌파
            - Stochastic Fast %K가 %D 상향 돌파
    3. 실시간 거래 강도 확인 (Execution Filter: 체결 압력)
        - 주요 지표 예시:
            - 호가창 매수 잔량 우세 (DepthImbalance > 0.2)
            - Spread이 좁고 매수 쪽 체결 지속
            - VWAP 대비 현재가가 아래에 있으나 매수량 증가
    - 매번 전략 생성 시 다음 조건을 지켜야 합니다:
        - 지표 선택은 Trend, Momentum, Volatility, Volume, Orderbook 중에서 shuffle → choice 방식으로 구성됩니다.
        - 반복적으로 동일한 지표 조합이 사용되는 것을 피해야 하며, 가능한 한 매 전략은 새로운 조합을 탐색합니다.
        - 단, 선택된 지표가 의미 없는 조합이 되지 않도록, 반드시 각 지표의 목적과 조합 타당성을 고려합니다.
4. 진입이 확정되었을 경우, set_entry_price() 메서드를 통해 다음 기준에 따라 목표가와 손절가를 설정하십시오:
    - 변동성(ATR)과 실시간 호가 스프레드(Spread)를 기반으로, 시장 상황에 따라 유동적으로 목표가와 손절가를 설정합니다.
    - 목표가(Target Price)는 다음 중 큰 값을 기준으로 설정합니다: `ATR × 0.5`, `Spread × 1.5`
    - 손절가(Stop Loss)는 다음 중 큰 값을 기준으로 설정합니다: `ATR × 0.35`, `Spread × 1.2`
    - 모든 가격은 진입가 기준으로 ± 보정되어야 하며, 10단위 반올림 처리합니다.
    - 이 설정은 최소 수익률 0.1% 이상, 손익비(RR) 1:1.5 이상을 확보하도록 설계되어야 합니다.
    - 호가폭이 비정상적으로 넓거나 좁을 경우도 포함하여, 항상 Spread 보정 로직을 적용합니다.
5. 수수료는 매수 시 0.04%, 매도 시 0.04%가 발생하며, 총 0.08%가 손실로 발생합니다.
    따라서 set_entry_price() 메서드에서는 목표가 설정 시 반드시 수수료를 고려하여 최소 0.15% 이상의 수익률이 확보되도록 설정합니다.
    예를 들어, 진입가가 10,000원인 경우, 목표가는 최소 10,015원 이상이어야 실질 이익이 발생합니다.
    수익률이 낮은 시장에서는 손익비(RR)를 확보하지 못하므로, 진입 자체를 피하거나 더 큰 변동성을 요구해야 합니다.
6. 모든 과정은 self.logger에 명확히 기록합니다.
7. 코드 실행 시 오류가 없고, 논리적으로 정확한 코드만 반환합니다.
8. 반환 시 코드 외 별도의 태그(```python 등)는 사용하지 않습니다.
"""
        
        user_prompt = f"""
요구사항:
- 클래스와 메서드 이름을 초단기(15초 단위) 전략의 핵심을 명확히 나타내도록 설정하십시오.
  (예: MicroMomentumScalper, OrderbookPressureScalper 등)
- should_buy()의 반환 값은 반드시 Tuple[bool, str]이며,
  매매 결정 여부(True/False), 진입 이유(str)를 순서대로 반환합니다.
  - should_buy()의 반환값 예시:
  - `(True, "RSI가 52로 상승 모멘텀 발생 + 매수 호가 강세")`
  - `(False, "시장 방향 조건(EMA9 < EMA21) 미충족")`
- set_entry_price()의 반환 값은 반드시 Tuple[float, float]이며,
  목표가(float), 손절가(float)를 순서대로 반환합니다.
  - 예시: `(25000.0, 24950.0)`
    - set_entry_price()의 내부에서는 다음 값을 함께 사용합니다:
        - atr: 최근 1분 간 캔들 기반의 평균 진폭 (Average True Range)
        - spread: 현재 호가창 매도1 - 매수1 가격 차이
    - 진입가 ± 보정값을 적용한 후, 목표가/손절가는 10단위 반올림 처리합니다.
    - 계산된 값은 self.logger.info(...)를 통해 로그에 남겨야 하며, 계산 근거를 함께 명시합니다.
    - 포지션 진입이 성공했을 경우, 다음 정보를 클래스 내부 상태로 반드시 저장합니다:
    - entry_price, entry_time, target_price, stop_loss_price
    - 이 값들은 should_sell() 평가 시 사용됩니다.
- should_sell()의 반환 값은 반드시 Tuple[bool, str]이며,
  매도 결정 여부(True/False), 매도 이유(str)를 순서대로 반환합니다.
  - 예시: `(True, "목표가 도달 – 현재가 25000, 목표가 25050")`
    - should_sell() 함수는 다음 조건 중 하나라도 만족하면 True를 반환해야 합니다:
        1. 현재가가 목표가 이상
        2. 현재가가 손절가 이하
        3. 최대 보유 시간 초과
        4. 실시간 호가/체결 데이터에서 매도 압력 우세 (예: DepthImbalance < -0.3)
    - 진입 시 entry_time은 반드시 저장되며, 최대 보유 시간은 기본 20초를 권장합니다.
    - 모든 매도 판단 과정은 self.logger를 통해 상세히 기록됩니다.
- trades 데이터를 이용해서 1초 캔들 데이터를 만들어서 사용합니다.
- **orderbook, 최근 체결(trade) 데이터를 포함한 모든 데이터는 반드시 호출 시마다 실시간 API를 사용하여 최신 상태를 유지합니다. 절대로 데이터를 캐싱하지 않습니다.**
  - API 호출 실패 시 즉시 진입 판단을 보류하고 매수를 진행하지 않습니다.
- 최근 체결(trade) 데이터를 사용하기전 시간별 정렬을 진행합니다.
- trade 데이터를 기반으로 1초 캔들을 생성할 때, 다음 순서로 진행됩니다:
  1. timestamp 기준 정렬
  2. 초 단위 그룹핑
  3. OHLCV 생성
- 모든 주요 판단 과정과 결정 이유를 self.logger에 매우 상세히 기록합니다.
    - self.logger 사용 예시:
        - `self.logger.info("시장 방향 확인 결과: 상승 추세, EMA9 > EMA21")`
        - `self.logger.warning("호가 데이터 수신 실패로 판단 보류")`
- 선택된 지표 등을 get_description()에 명확히 기술하십시오.
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
