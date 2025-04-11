from typing import Dict, Optional, List
import json
import os
from datetime import datetime
import requests
from pathlib import Path
from src.trading_analyzer import TradingAnalyzer
from src.news_summarizer import NewsSummarizer
from src.utils.log_manager import LogManager, LogCategory
from src.models.market_data import (
    AnalysisResult, TradingDecision, NextDecision,
    ActionType, RiskLevelType, TradingDecisionResult
)

class TradingDecisionMaker:
    """뉴스와 시장 분석을 종합하여 매매 판단을 내리는 클래스"""
    
    # OpenAI API 엔드포인트 상수
    _OPENAI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
    
    def __init__(
        self,
        bithumb_api_key: str,
        bithumb_secret_key: str,
        openai_api_key: str,
        log_manager: LogManager
    ):
        """초기화
        
        Args:
            bithumb_api_key: 빗썸 API 키
            bithumb_secret_key: 빗썸 Secret 키
            openai_api_key: OpenAI API 키
            log_manager: 로그 매니저
        """
        self.trading_analyzer = TradingAnalyzer(bithumb_api_key, bithumb_secret_key, log_manager=log_manager)
        self.news_summarizer = NewsSummarizer(openai_api_key, self._OPENAI_API_ENDPOINT, log_manager=log_manager)
        self.log_manager = log_manager
        
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message="매매 판단기 초기화 완료",
                data={
                    "openai_endpoint": self._OPENAI_API_ENDPOINT
                }
            )
        
    def _convert_datetime(self, data: Dict) -> Dict:
        """datetime 객체를 ISO 형식 문자열로 변환합니다."""
        if isinstance(data, dict):
            return {k: self._convert_datetime(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_datetime(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        return data
    
    def _create_decision_prompt(
        self,
        symbol: str,
        analysis_result: AnalysisResult
    ) -> str:
        """스캘핑 트레이딩을 위한 의사결정 프롬프트 생성

        Args:
            symbol: 심볼 (예: BTC)
            analysis_result: 분석 결과 데이터

        Returns:
            str: GPT 프롬프트
        """
        try:
            asset_data = analysis_result.asset_info
            market_data = analysis_result.market_data

            # JSON 응답 형식 (포맷 지정자와 충돌하지 않도록 따옴표 처리)
            json_format = '''
[JSON 응답 형식]
{
    "action": "매수" | "매도" | "관망",
    "reason": "판단 이유 (최대 100자)",
    "entry_price": 매수/매도 희망가격 (현재가 기준 ±0.5% 이내),
    "stop_loss": 손절가격 (매수 시 -1% 이내, 매도 시 +1% 이내),
    "take_profit": 목표가격 (매수 시 +1% 이내, 매도 시 -1% 이내),
    "confidence": 확신도 (0.0 ~ 1.0),
    "risk_level": "상" | "중" | "하",
    "next_decision": {
        "interval_minutes": 0.5 | 1 | 2 | 3 | 5 | 10 | 30,
        "reason": "다음 판단 시점까지의 대기 시간 선택 이유 (최대 50자)"
    }
}'''

            # 최종 프롬프트 조합
            prompt = f"""
당신은 초단타 암호화폐 트레이딩에 특화된 전문 스캘핑 트레이더입니다. 현재 {symbol}에 대한 매매 판단이 필요합니다.

전략 핵심:
- 1~5분 이내의 초단기 수익 기회를 포착하여 즉각 진입/청산합니다.
- '관망'은 극히 예외적인 상황에만 허용되며, 가능한 한 적극적인 매수 또는 매도 판단을 내려야 합니다.
- 지표 간 소폭의 충돌이 있어도 수익 가능성이 우선되는 방향으로 판단합니다.

현재 포지션 상태:
- 보유 수량: {asset_data.balance:.8f} {symbol}
- 평균 매수가: {asset_data.avg_buy_price:,.0f} KRW
- 평가 손익: {asset_data.profit_loss_rate:+.2f}%

{"""
[무포지션 전략 - 매수 진입 조건 상세화]:

- 아래 조건 중 **최소 3개 이상**을 동시에 만족할 경우에만 매수를 시도합니다:
  1. 가격이 3분/5분/10분 이동평균 모두를 상향 돌파했거나, 정배열 상태입니다.
  2. RSI(3분) > 50 이고 RSI(7분) > RSI(14분) → 상승 모멘텀 확인
  3. 볼린저밴드 상단에 근접하면서도 밴드 폭이 확장 중일 경우 (상승 돌파 가능성)
  4. 호가창 매수/매도 비율이 1.2 이상이며, 스프레드가 0.05% 이하로 좁습니다.
  5. 프리미엄이 음수 → 현물 매수세 우위 (선물 과매도 반등 기대)
  6. 최근 3분 내 거래량이 평균 이상이며 가격도 함께 상승했습니다.

- 아래 상황에서는 매수를 절대 피합니다:
  - RSI가 급등 후 70 이상으로 과매수인 상태에서 캔들이 음봉으로 전환된 경우
  - 호가창 매수 비율이 높지만 스프레드가 0.1% 이상으로 비정상적으로 넓을 때
  - 볼린저밴드가 수축 중이거나 밴드폭이 0.1% 이하로 매우 좁은 경우
  - 5분 신고가 갱신 직후 매수 신호가 애매한 경우 (고점 돌파 후 피로 가능성)

- 매수 진입 시 반드시 다음 두 항목을 함께 설정합니다:
  - 손절가는 진입가 -0.7% 이내로 설정
  - 목표 수익은 +0.5% 이상 가능한 경우에만 진입
""" if asset_data.balance == 0 else """
📉 [보유 포지션 전략 - 매도 청산 조건 상세화]:

[1] 목표 수익 실현 매도 조건 (take-profit):
- 평가 수익률이 +0.3% 이상이고 아래 조건 중 2개 이상 만족 시, 수익 실현을 우선합니다:
  1. RSI(3분)가 70 이상 → 과매수권 진입
  2. 3분봉 기준 캔들 실체가 작아지고, 윗꼬리가 길어지기 시작
  3. 5분 신고가 갱신 후 바로 다음 봉이 음봉 전환
  4. 호가창 매수/매도 비율이 1.0 이하로 급변하거나 스프레드가 확대됨
  5. 프리미엄이 급등 후 하락 전환

[2] 손절 매도 조건:
- 손절가(-1%)에 도달하면 무조건 즉시 매도합니다.
- 그 외 상황에서는 아래 조건 중 **3개 이상이 동시에 충족될 때만** 손절 매도합니다:
  1. RSI(3/7/14분 모두) 하락 중이며, RSI(3분) < 40
  2. 볼린저밴드가 수축하며 중심선을 하향 돌파
  3. 캔들 강도가 "약함"이며, 실체 비율 < 0.3
  4. 프리미엄이 0 이상으로 전환되었고, 펀딩비율도 양수 → 선물 매수세 형성
  5. 호가창 매도세 급증(비율 < 0.85) + 스프레드 > 0.07%

[3] 주의할 상황:
- **단기 하락 중에도 모멘텀이 유지되면 매도 금지** (ex: RSI가 50 이상 유지되며 캔들 강도 "강함")
- 하락 반전으로 보이는 음봉이 하나 발생해도, 그 전 고점을 유지하거나 거래량이 급감한 경우 매도 보류
- **'평가 손실'만으로 매도하지 말 것. 지표 기반 반전 조건이 충족되지 않으면 대기 전략 유지**

[4] 매도 이후 원칙:
- 동일 방향 재진입은 반드시 1분 이상 대기 후, 재확인된 신호가 있어야만 진입 허용
"""}

시장 정보 분석:
[가격]
- 현재가: {market_data.current_price:,.0f} KRW
- MA (3/5/10/20분): {market_data.ma3:,.0f} / {market_data.ma5:,.0f} / {market_data.ma10:,.0f} / {market_data.ma20:,.0f}
- VWAP(3분): {market_data.vwap_3m:,.0f} KRW

[모멘텀]
- RSI (3/7/14분): {market_data.rsi_3:.1f} / {market_data.rsi_7:.1f} / {market_data.rsi_14:.1f}
- 볼린저밴드 폭: {market_data.bb_width:.2f}%

[변동성 & 추세]
- 변동성 (3/5/10/15분): {market_data.volatility_3m:.2f}% / {market_data.volatility_5m:.2f}% / {market_data.volatility_10m:.2f}% / {market_data.volatility_15m:.2f}%
- 가격 추세(1분): {market_data.price_trend_1m}
- 거래량 추세(1분): {market_data.volume_trend_1m}

[캔들 분석]
- 실체 비율: {market_data.candle_body_ratio:.2f}
- 강도: {market_data.candle_strength}
- 5분 신고가: {"갱신" if market_data.new_high_5m else "미갱신"}
- 5분 신저가: {"갱신" if market_data.new_low_5m else "미갱신"}

[호가 & 선물]
- 매수/매도 비율: {market_data.order_book_ratio:.2f}
- 스프레드: {market_data.spread:.3f}%
- 선물 프리미엄: {market_data.premium_rate:.3f}%
- 펀딩비율: {market_data.funding_rate:.4f}%
- 가격 안정성: {market_data.price_stability:.2f}

다음 판단 타이밍:
- 매매 결정 시 30초~1분 이내 즉시 재판단
- 관망 시에도 반드시 3분 이내 재판단

리스크 기준:
- 손절: 최대 -1% 이내
- 목표수익: 최소 +0.15% 이상
- 손절 후 동일 방향 재진입은 1분간 제한

{json_format}

위 기준에 따라 현재 포지션 상태를 반영한 매매 판단을 내려주세요.
"""

            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"{symbol} 매매 판단 프롬프트 생성 완료",
                    data={"prompt": prompt}
                )
            
            return prompt
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 매매 판단 프롬프트 생성 실패: {str(e)}",
                    data={"symbol": symbol, "error": str(e)}
                )
            raise
        
    def _call_gpt4(self, prompt: str) -> TradingDecision:
        """GPT-4 API를 호출하여 스캘핑 트레이딩 판단을 얻습니다.
        
        Args:
            prompt: GPT-4에 전달할 프롬프트
            
        Returns:
            Optional[TradingDecision]: 매매 판단 결과, 실패 시 None
        """
        headers = {
            "Authorization": f"Bearer {self.news_summarizer.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-2024-11-20",
            "messages": [
                {
                    "role": "system",
                    "content": """
                    당신은 암호화폐 스캘핑 트레이딩 전문가입니다. 1~5분 단위 초단기 전략을 사용하며, 
                    기술 지표와 시장 데이터를 종합적으로 분석하여 신속하고 명확한 매매 판단을 합니다. 
                    수수료를 고려한 실현 가능한 수익을 추구하고 리스크 관리를 철저히 합니다. 
                    응답은 반드시 지정된 JSON 형식을 따라야 합니다."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 500,
            "response_format": { "type": "json_object" }
        }
        
        try:
            response = requests.post(
                self.news_summarizer.api_endpoint,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="GPT-4 API 호출 실패",
                        data={"status_code": response.status_code, "response": response.text}
                    )
                return None
                
            response_data = response.json()

            # response_data 출력
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message="GPT-4 API 응답 데이터",
                    data={"response": response_data}
                )

            if not response_data or "choices" not in response_data:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="GPT-4 API 응답 형식 오류",
                        data={"response": response_data}
                    )
                return None
                
            content = response_data["choices"][0]["message"]["content"]
            # content = content.replace("```json", "").replace("```", "").strip()
            content = self._remove_commas_in_numbers(content)
            
            try:
                decision_dict = json.loads(content)
                
                # TradingDecision 객체 생성
                decision = TradingDecision.from_dict(decision_dict)
                
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.SYSTEM,
                        message="GPT-4 매매 판단 완료",
                        data={"decision": decision.__dict__}
                    )
                return decision
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message="GPT-4 응답 파싱 실패",
                        data={"error": str(e), "content": content}
                    )
                return None
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="GPT-4 API 호출 중 예외 발생",
                    data={"error": str(e)}
                )
            return None

    def _remove_commas_in_numbers(self, json_str: str) -> str:
        """JSON 문자열 내의 숫자에 포함된 콤마를 제거합니다.

        Args:
            json_str (str): 원본 JSON 문자열

        Returns:
            str: 숫자의 콤마가 제거된 JSON 문자열
        """
        import re
        # 숫자 내의 콤마만 제거 (숫자,숫자 패턴을 찾아서 콤마 제거)
        # 예: "123,456" -> "123456"
        while True:
            # 콤마를 포함한 숫자 패턴을 찾아서 콤마 제거
            new_str = re.sub(r'(\d),(\d)', r'\1\2', json_str)
            # 더 이상 변경이 없으면 종료
            if new_str == json_str:
                break
            json_str = new_str
        return json_str

    def make_decision(self, symbol: str) -> TradingDecisionResult:
        """뉴스와 시장 분석을 종합하여 매매 판단
        
        Args:
            symbol: 심볼 (예: 'BTC')
            
        Returns:
            TradingDecisionResult: 매매 판단 종합 결과
        """
        try:            
            # 2. 시장 분석 데이터 수집
            analysis_result = self.trading_analyzer.analyze(symbol)
                
            # 3. 매매 판단 프롬프트 생성
            prompt = self._create_decision_prompt(symbol, analysis_result)
            
            # 4. GPT-4 매매 판단 요청
            decision = self._call_gpt4(prompt)
            
            # 5. 결과 반환
            result = TradingDecisionResult(
                success=True,
                symbol=symbol,
                timestamp=datetime.now(),
                analysis=analysis_result,
                decision=decision
            )
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.DECISION,
                    message=f"{symbol} 매매 판단 완료",
                    data={"result": result.__dict__}
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=f"{symbol} 매매 판단 실패",
                    data={"error": str(e)}
                )
            
            raise

    def _analyze_market_conditions(self, symbol: str, market_data: Dict) -> Dict:
        """시장 상황을 분석합니다."""
        try:
            # 기존 분석
            conditions = super()._analyze_market_conditions(symbol, market_data)
            
            # 프리미엄 인덱스 분석 추가
            premium_index = self.market_analyzer.analyze_premium_index(symbol)
            
            # 프리미엄 인덱스 기반 추가 분석
            conditions['funding_rate'] = premium_index['funding_rate']
            conditions['market_bias'] = premium_index['market_bias']
            conditions['price_stability'] = premium_index['price_stability']
            
            # 매매 신호 보정
            if abs(premium_index['funding_rate']) > 0.1:  # 펀딩비율이 큰 경우
                conditions['trading_signals'].append({
                    'signal': "매수" if premium_index['funding_rate'] < 0 else "매도",
                    'strength': min(abs(premium_index['funding_rate']) / 0.2, 1.0),  # 0.2%를 최대 강도로
                    'reason': f"펀딩비율 {premium_index['funding_rate']:.4f}% ({premium_index['market_bias']})"
                })
            
            # 프리미엄/디스카운트 반영
            if abs(premium_index['premium_rate']) > 0.5:  # 0.5% 이상 차이
                conditions['trading_signals'].append({
                    'signal': "매수" if premium_index['premium_rate'] < 0 else "매도",
                    'strength': min(abs(premium_index['premium_rate']) / 2.0, 1.0),  # 2%를 최대 강도로
                    'reason': f"{'프리미엄' if premium_index['premium_rate'] > 0 else '디스카운트'} {abs(premium_index['premium_rate']):.4f}%"
                })
            
            return conditions
            
        except Exception as e:
            self.log_manager.log(
                category=LogCategory.ERROR,
                message="시장 상황 분석 실패",
                data={"error": str(e)}
            )
            return super()._analyze_market_conditions(symbol, market_data)