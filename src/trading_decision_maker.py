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
당신은 암호화폐 스캘핑 트레이딩 전문가입니다. {symbol}에 대한 매매 판단이 필요합니다.
- 1~5분 간격의 초단기 매매에 특화되어 있습니다.
- 기술적 지표, 호가창, 선물 시장 데이터를 종합 분석하여 판단합니다.
- 신속하고 명확한 매매 판단을 내려야 합니다.
- 수수료를 고려하여 실현 가능한 수익을 극대화합니다.
- 시장 안정성과 철저한 리스크 관리를 최우선합니다.
- 응답은 반드시 지정된 JSON 형식을 엄격히 준수해야 합니다.

[시장 기술 지표]
1. 가격 동향:
- 현재가: {market_data.current_price:,.0f} KRW
- 1분 이동평균: {market_data.ma1:,.0f} KRW
- 3분 이동평균: {market_data.ma3:,.0f} KRW
- 5분 이동평균: {market_data.ma5:,.0f} KRW
- 10분 이동평균: {market_data.ma10:,.0f} KRW
- 20분 이동평균: {market_data.ma20:,.0f} KRW
- VWAP(3분): {market_data.vwap_3m:,.0f} KRW

2. 모멘텀 지표:
- 1분 RSI: {market_data.rsi_1:.1f}
- 3분 RSI: {market_data.rsi_3:.1f}
- 7분 RSI: {market_data.rsi_7:.1f}
- 14분 RSI: {market_data.rsi_14:.1f}
- 볼린저밴드 폭: {market_data.bb_width:.2f}%

3. 변동성/추세:
- 3분 변동성: {market_data.volatility_3m:.2f}%
- 5분 변동성: {market_data.volatility_5m:.2f}%
- 10분 변동성: {market_data.volatility_10m:.2f}%
- 15분 변동성: {market_data.volatility_15m:.2f}%
- 1분 가격추세: {market_data.price_trend_1m}
- 1분 거래량추세: {market_data.volume_trend_1m}

4. 캔들 분석:
- 캔들 실체 비율: {market_data.candle_body_ratio:.2f}
- 캔들 강도: {market_data.candle_strength}
- 5분 신고가: {"갱신" if market_data.new_high_5m else "미갱신"}
- 5분 신저가: {"갱신" if market_data.new_low_5m else "미갱신"}

5. 호가/선물 지표:
- 매수/매도 비율: {market_data.order_book_ratio:.2f}
- 호가 스프레드: {market_data.spread:.3f}%
- 선물 프리미엄: {market_data.premium_rate:.3f}%
- 펀딩비율: {market_data.funding_rate:.4f}%
- 가격 안정성: {market_data.price_stability:.2f}

[보유 자산 정보]
- 보유수량: {asset_data.balance:.8f} {symbol}
- 평균단가: {asset_data.avg_buy_price:,.0f} KRW
- 평가손익: {asset_data.profit_loss_rate:+.2f}%
- 거래가능 KRW: {asset_data.krw_balance:,.0f}

[매매 판단 액션 가이드]
- 가능한 한 적극적으로 "매수" 또는 "매도"를 선택합니다.
- "관망"은 아래의 경우에만 허용됩니다:
  a. 신호 강도가 0.2 미만으로 매우 낮고, 시장 상태가 극도로 불확실할 때
  b. 여러 지표가 명백히 상충하여 명확한 방향성을 찾기 어려울 때
- "매수" 또는 "매도" 선택 시 다음 중 최소 2가지 이상을 근거로 구체적으로 제시합니다:
  a. 이동평균 및 RSI 등 모멘텀 지표의 명확한 신호
  b. 거래량 및 호가창 지표의 뚜렷한 방향성 일치
  c. 선물 프리미엄 및 펀딩비율 등 파생상품 지표의 명확한 신호
  d. 최근 3분간의 가격 및 거래량 추세의 방향 일치
- 신호 강도가 0.4 이상이면 반드시 "매수" 또는 "매도"를 선택해야 합니다.

[다음 판단 시점 결정 기준]
1. 시장이 불안정하거나, 신호 강도가 0.4 이상인 경우 즉시(30초~1분 이내) 재판단합니다.
2. 보유 포지션이 목표가 또는 손절가에 근접한 경우 즉시(30초~1분 이내) 재판단합니다.
3. 가격 급등락, 거래량 급증 등 특이 상황 시 즉시(30초~1분 이내) 재판단합니다.
4. "관망" 판단 시 다음 기준으로 대기 후 재판단합니다:
   - 신호 강도 0.2 이하로 시장이 정체된 경우 최대 5분
   - 신호 강도 0.2~0.4로 중립적이고 방향성이 불분명한 경우 최대 3분
   - 관망 중 주요 지표(RSI, 볼린저밴드 폭, 거래량)의 급변 시 즉시(1분 이내)

[리스크 관리 원칙]
- 목표가와 손절가를 엄격히 준수합니다.
- 손절가 도달 시 즉시 청산 후 동일 방향 재진입은 최소 1분간 금지합니다.
- 손절 폭은 최대 1% 이내, 목표가는 최소 0.3% 이상 기대 수익이 있을 때만 설정합니다.

[시장 상황별 유연성]
- "강한 상승 추세"에서는 하락 신호에도 매도를 신중히 결정합니다.
- "강한 하락 추세"에서는 상승 신호에도 매수를 신중히 결정합니다.
- "횡보" 상태에서는 볼린저밴드 폭과 RSI 지표를 적극 활용하여 빠른 판단을 내립니다.

{json_format}

위의 지침을 철저히 준수하여 명확하고 빠른 판단으로 최고의 스캘핑 수익을 창출합니다.
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