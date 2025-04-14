from src.news import News
import os
from dotenv import load_dotenv
import json
from dataclasses import dataclass
load_dotenv()

def main():
    from google import genai

    client = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        config={
            'response_mime_type': 'application/json',
            'response_schema': NewsResponse,
        },
        contents="""
당신은 초단기 암호화폐 매매에 특화된 스캘핑 트레이딩 전문가입니다.
지금 당신은 실시간 시장 데이터를 기반으로 매수 진입 가능성을 평가해야 합니다.

어떤 조건도 강제하지 않으며, 아래의 시장 정보를 종합적으로 해석하여
지금 시점에서의 매수 진입 여부를 자유롭게 판단하십시오.

당신의 임무:
1. 시장 데이터를 바탕으로 현재 매수 진입이 타당한지 결정
2. 진입이 타당하다면, 목표가(target_price)와 손절가(stop_loss_price)를 제시
3. 판단 이유는 반드시 3가지로 구체적으로 설명
4. 수익 실현 가능성과 리스크를 균형 있게 고려

단, 다음은 반드시 지켜야 합니다:
- 목표가는 반드시 현재가보다 높게 (정수)
- 손절가는 반드시 현재가보다 낮게 (정수)

[기본 시장 정보]
- 현재가: 3,124원
- 거래량 동향(1분): 상승
- 가격 동향(1분): 상승
- 캔들 강도: 강함 (실체비율: 95%)

[기술적 지표]
- RSI: 3분(65.2), 7분(59.1)
- 이동평균: MA1(3,123), MA3(3,121), MA5(3,120), MA10(3,117)
- 변동성: 3분(0.23%), 5분(0.20%), 10분(0.18%)
- VWAP(3분): 3,120원
- 볼린저밴드 폭: 0.21%

[호가 분석]
- 매수/매도 비율: 1.55
- 스프레드: 0.028%

[특이사항]
- 5분 신고가 돌파: O
- 5분 신저가 돌파: X

위 정보를 종합적으로 고려하여, 지금 시점에서 매수 진입이 타당한지 판단해 주세요.
아래 형식으로 정확히 응답해 주세요.

{
  "should_enter": true/false,
  "target_price": 0,
  "stop_loss_price": 0,
  "reasons": [
    "첫 번째 근거",
    "두 번째 근거",
    "세 번째 근거"
  ]
}
"""
    )
    
    print(response.parsed)

@dataclass
class NewsResponse:
    should_enter: bool
    target_price: int
    stop_loss_price: int
    reasons: list[str]


if __name__ == "__main__":
    main() 