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
        "interval_minutes": 분 (0.1~10),
        "reason": "다음 판단 시점까지의 대기 시간 선택 이유 (최대 50자)"
    }
}'''

            prompt = f"""
당신은 초단타 스캘핑 방식의 암호화폐 전문 트레이더입니다. 현재 심볼 {{symbol}}에 대한 신속하고 명확한 매매 판단이 필요합니다.

- 당신은 고정된 규칙이 아닌, 시장 전체 흐름을 종합 해석하여 실시간 매수 또는 매도 판단을 내릴 수 있는 추론 전문가입니다.
- 판단은 철저히 수익 실현 가능성을 기준으로 하며, 가능한 한 관망을 최소화하고 적극적인 진입 또는 청산을 수행해야 합니다.
- 모든 판단은 다음의 기본 원칙과 제약 조건을 따릅니다:

---

**판단 원칙 (추론 기반)**

1. **고정 조건은 존재하지 않으며**, 아래에 제공된 수많은 지표와 흐름을 스스로 해석하여 시장의 방향성을 판단해야 합니다.
2. **지표 간 충돌이 있는 경우**, 다음의 우선 순위로 해석을 수행합니다:
   - (1) 시장 방향성 흐름  
   - (2) 거래량 흐름  
   - (3) 호가창 흐름  
   - (4) RSI, 볼린저밴드 등 기술적 지표  
3. 판단은 반드시 일관성을 유지해야 하며, 유사한 시장 구조에서는 유사한 매매 결정을 내려야 합니다.
4. **관망은 최후의 선택지**입니다. 단기 수익 실현 가능성이 0.3% 이상 있는 경우, 충돌 지표가 있어도 과감히 진입을 선택합니다.

---

**현재 포지션 상태**
- 보유 수량: {asset_data.balance:.8f} {symbol}
- 평균 매수가: {asset_data.avg_buy_price:,.0f} KRW
- 평가 손익률: {asset_data.profit_loss_rate:+.2f}%

---

**시장 데이터**
[가격 흐름]
- 현재가: {market_data.current_price:,.0f} KRW
- 이동평균 (3/5/10/20분): {market_data.ma3:,.0f} / {market_data.ma5:,.0f} / {market_data.ma10:,.0f} / {market_data.ma20:,.0f}
- VWAP(3분): {market_data.vwap_3m:,.0f} KRW

[모멘텀]
- RSI (3/7/14분): {market_data.rsi_3:.1f} / {market_data.rsi_7:.1f} / {market_data.rsi_14:.1f}
- 볼린저밴드 폭: {market_data.bb_width:.2f}%

[변동성 & 추세]
- 변동성 (3/5/10/15분): {market_data.volatility_3m:.2f}% / {market_data.volatility_5m:.2f}% / {market_data.volatility_10m:.2f}% / {market_data.volatility_15m:.2f}%
- 가격 추세(1분): {market_data.price_trend_1m}
- 거래량 추세(1분): {market_data.volume_trend_1m}

[캔들]
- 캔들 실체 비율: {market_data.candle_body_ratio:.2f}
- 강도: {market_data.candle_strength}
- 5분 신고가: {"갱신" if market_data.new_high_5m else "미갱신"}
- 5분 신저가: {"갱신" if market_data.new_low_5m else "미갱신"}

[호가 & 선물]
- 매수/매도 비율: {market_data.order_book_ratio:.2f}
- 스프레드: {market_data.spread:.3f}%
- 선물 프리미엄: {market_data.premium_rate:.3f}%
- 펀딩비율: {market_data.funding_rate:.4f}%
- 가격 안정성: {market_data.price_stability:.2f}

---

**판단 목표**
- 실현 가능한 수익이 0.3% 이상 발생할 가능성이 있다면 진입 우선
- 손절 기준은 -1% 이내, 리스크가 급격히 높아질 경우 청산 우선
- 포지션 보유 중일 경우 손실이라도 즉시 청산하지 않으며, 지표 기반 반전이 확실할 때만 매도
- 수익이 낮더라도 하락 전환이 명확하면 빠르게 이익을 확보

---

⏱ **판단 타이밍**
- 진입 또는 청산 결정 후에는 30초~1분 이내에 재판단
- 관망 선택 시에도 반드시 3분 이내 재판단 필요

---

**추가 규칙: 포지션 유지/반전 조건**
1. 직전 판단이 매수였고 아직 포지션을 보유 중이라면, 아래 조건 중 2가지 이상이 충족될 때에만 매도 또는 반대 포지션 전환을 고려:
   - 현재가가 평균 매수가 대비 -0.5% 이상 하락
   - 시장 방향성 흐름이 하락 추세로 급격히 전환 (예: 가격 추세, 거래량 추세 모두 하락 전환)
   - RSI 단기 지표가 과매도 구간(예: RSI < 30)으로 급변 후 추가 하락 신호
   - 호가창 매도세가 매수세 대비 현저히 우세 (매수/매도 비율 0.5 이하)

2. 직전 판단이 매도였고 아직 포지션을 보유 중이라면, 아래 조건 중 2가지 이상이 충족될 때에만 매수 전환 고려:
   - 현재가가 평균 매도가 대비 +0.5% 이상 상승
   - 시장 방향성 흐름이 상승 추세로 급격히 전환 (예: 가격 추세, 거래량 추세 모두 상승 전환)
   - RSI 단기 지표가 과매수 구간(예: RSI > 70)에서 추가 상승 신호
   - 호가창 매수세가 매도세 대비 현저히 우세 (매수/매도 비율 1.5 이상)

3. 최근 30초~1분 내에 포지션을 진입했다면, 사소한 단기 변동만으로 반대 포지션으로 즉시 전환하지 않음.
4. ‘관망’은 지표 충돌이 크거나 추세가 모호할 때만 사용.
5. 시장이 1% 이상 급등/급락 같은 돌발 변동을 보일 경우, 위 기준을 무시하고 신속하게 대응할 수 있음.

{json_format}

**감정 편향 통제 원칙**
당신은 인간의 감정 편향(예: 손실 회피, 후회 회피, 이익 조기 실현 등)에 영향을 받지 않습니다. 판단은 통계적 수익 기대값과 신호의 확실성을 기준으로 이루어져야 하며, 손실 중이라고 해서 무조건 포기하거나, 수익 중이라고 해서 무조건 조기 청산해서는 안 됩니다. 목표는 **장기 기대수익의 최적화**입니다.
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