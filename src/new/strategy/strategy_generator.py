from openai import OpenAI
import os
from typing import Tuple
class StrategyGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def create_prompt(self) -> Tuple[str, str]:
        template_code = open('src/new/strategy/template_signal.py', 'r').read()
        system_prompt = """
이 클래스는 코인 스캘핑 매매 시그널을 위한 클래스입니다.
당신은 최고의 소프트웨어 엔지니어로서, 최고의 수익률을 목표로 합니다.
코드는 즉시 실전에 투입할 수 있는 수준이어야 하며, 효율성과 가독성, 유지보수성이 높아야 합니다.
응답은 반드시 코드 형식으로 반환해주세요.
"""
        
        user_prompt = f"""
요구사항:
- 클래스와 메서드 이름에서 'Template'을 전략의 핵심을 명확히 나타내는 이름으로 변경하세요.
  (예: VolumeSpikeScalper, OrderbookMomentum 등)
- 반드시 should_buy 메서드를 구현해야 합니다.
- API 호출 횟수를 최소화하고, 중복 데이터 처리를 방지해 성능을 최적화하세요.
- 매수판단은 너무 복잡하지 않아야 하며, 당신이 구할 수 있는 지표 3개만 사용하세요.
- 예외처리를 반드시 구현하여 API 호출 실패 시에도 전략의 연속성을 보장하세요.
- 매수/매도 판단은 명확한 수치 기준(예: RSI < 30, EMA 단기 > EMA 장기 등)을 코드에 명시하고 활용해야 합니다.
- 제시한 코드의 포함된 함수의 이름과 매개변수, 반환값은 변경할 수 없습니다.
- 주석은 한글로 달아주세요

아래는 템플릿 코드입니다. 이 템플릿 이외에는 추가적인 참고가 불가능합니다.

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
    
    def generate_auto(self):
        system_prompt, user_prompt = self.create_prompt()
        code = self.create_from_gpt(system_prompt, user_prompt)
        return code
