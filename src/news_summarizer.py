from typing import List, Dict, Optional
import json
import requests
from datetime import datetime
from src.utils.logger import setup_logger
from src.news import News
import os

logger = setup_logger('news_summarizer')

class NewsSummarizer:
    """뉴스 요약 및 감성 분석기 (GPT-4o-mini-2024-07-18 모델 사용)"""
    
    # 감성 점수 범위: -1.0 (매우 부정) ~ 1.0 (매우 긍정)
    SENTIMENT_LABELS = {
        (-1.0, -0.6): "매우 부정적",
        (-0.6, -0.2): "부정적",
        (-0.2, 0.2): "중립적",
        (0.2, 0.6): "긍정적",
        (0.6, 1.0): "매우 긍정적"
    }
    
    def __init__(self, api_key: str, api_endpoint: str):
        """초기화
        
        Args:
            api_key: OpenAI API 키
            api_endpoint: OpenAI API 엔드포인트
        """
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.news = News()
    
    def _create_prompt(self, news_items: List[Dict]) -> str:
        """GPT-4에 전달할 프롬프트를 생성합니다.
        
        Args:
            news_items: 뉴스 목록
            
        Returns:
            프롬프트 문자열
        """
        symbol = news_items[0]["symbol"]
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        prompt = f"""아래는 {symbol} 관련 뉴스 {len(news_items)}개입니다. 
각 뉴스에 대해 다음 정보를 제공해주세요:

1. 각 뉴스의 핵심 내용 요약 (2-3문장)
2. 각 뉴스의 감정 점수 (-1.0 ~ 1.0)
   - -1.0: 매우 부정적
   - 0.0: 중립적
   - 1.0: 매우 긍정적
3. 각 뉴스와 {symbol}의 연관성 점수 (0.0 ~ 1.0)
   - 0.0: 관련 없음
   - 1.0: 매우 밀접한 관련

=== 뉴스 목록 ===
"""
        
        for i, item in enumerate(news_items, 1):
            published = item["published_at"].strftime("%Y-%m-%d %H:%M")
            prompt += f"\n[뉴스 {i}]"
            prompt += f"\n제목: {item['title']}"
            prompt += f"\n출처: {item['source']} ({published})"
            if item["summary"]:
                prompt += f"\n내용: {item['summary']}"
            prompt += "\n"
            
        prompt += """
다음 JSON 형식으로 응답해주세요:
{
    "news_analysis": [
        {
            "id": 1,
            "summary": "뉴스 요약",
            "sentiment_score": 0.0,
            "relevance_score": 0.0
        }
    ],
    "overall_summary": "전체 뉴스의 핵심 내용 요약 (3-4문장)",
    "average_sentiment": 0.0,
    "average_relevance": 0.0
}"""
        return prompt
    
    def _call_gpt4(self, prompt: str) -> Dict:
        """GPT-4 API를 호출합니다.
        
        Args:
            prompt: 프롬프트 문자열
            
        Returns:
            API 응답 (JSON)
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = """당신은 암호화폐 뉴스 요약 전문가입니다. 
각 뉴스의 핵심 내용을 간단히 요약하고, 감정 점수와 키워드와의 연관성을 분석합니다.
감정 점수는 뉴스의 톤과 내용이 얼마나 긍정적인지를 나타내며,
연관성 점수는 뉴스가 해당 암호화폐와 얼마나 직접적으로 관련되어 있는지를 나타냅니다.

반드시 지정된 JSON 형식으로 응답해주세요."""
        
        data = {
            "model": "gpt-4o-mini-2024-07-18",  # 원래 모델로 복구
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=data,
                timeout=30
            )
            
            # 응답 상태 코드 확인
            if response.status_code != 200:
                logger.error(f"API 오류 응답: {response.status_code} - {response.text}")
                return None
                
            response_data = response.json()
            logger.debug(f"API 응답: {response_data}")
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API 요청 실패: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"GPT-4 API 호출 실패: {str(e)}")
            return None
    
    def _get_sentiment_label(self, score: float) -> str:
        """감성 점수에 해당하는 레이블을 반환합니다."""
        for (min_score, max_score), label in self.SENTIMENT_LABELS.items():
            if min_score <= score <= max_score:
                return label
        return "알 수 없음"
    
    def _count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산합니다.
        
        영어는 단어당 약 1.3 토큰, 한글은 글자당 약 1.5 토큰으로 계산
        """
        # 공백으로 분리하여 단어 수 계산
        words = text.split()
        eng_chars = sum(1 for c in text if ord('a') <= ord(c.lower()) <= ord('z'))
        kor_chars = sum(1 for c in text if 0xAC00 <= ord(c) <= 0xD7A3)
        
        # 영어는 단어당 1.3 토큰, 한글은 글자당 1.5 토큰으로 계산
        eng_tokens = (eng_chars / 4) * 1.3  # 평균 단어 길이 4로 가정
        kor_tokens = kor_chars * 1.5
        
        return int(eng_tokens + kor_tokens)

    def _get_dummy_response(self, symbol: str) -> Dict:
        """개발용 더미 응답을 생성합니다."""
        return {
            "success": True,
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "news_count": 5,
            "analysis": {
                "key_points": [
                    f"{symbol} 가격이 상승세를 보이며 투자자들의 관심이 집중",
                    "주요 기관들의 암호화폐 시장 진출이 가속화",
                    "규제 환경이 점차 명확해지면서 시장 안정성 향상"
                ],
                "market_impact": "전반적으로 긍정적인 뉴스들이 우세하며, 기관 투자자들의 참여로 시장이 성숙화되는 모습을 보이고 있습니다.",
                "sentiment_score": 0.65,
                "sentiment_label": "매우 긍정적",
                "investor_advice": "단기적으로는 변동성에 대비하되, 중장기적 관점에서 매수 기회로 활용할 수 있습니다."
            }
        }

    def _save_prompt_and_response(self, symbol: str, prompt: str, response: Dict = None) -> str:
        """프롬프트와 응답을 파일로 저장합니다.
        
        Args:
            symbol: 코인 심볼
            prompt: 저장할 프롬프트
            response: 저장할 응답 (선택사항)
            
        Returns:
            생성된 파일명의 기본 부분 (타임스탬프 포함)
        """
        try:
            # 현재 시간을 파일명에 포함
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"{symbol}_{timestamp}"
            
            # 프롬프트 저장
            prompt_dir = ".temp/prompt"
            os.makedirs(prompt_dir, exist_ok=True)
            prompt_file = f"{prompt_dir}/{base_filename}.txt"
            
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt)
            logger.info(f"프롬프트가 저장되었습니다: {prompt_file}")
            
            # 응답 저장 (있는 경우)
            if response:
                response_dir = ".temp/response"
                os.makedirs(response_dir, exist_ok=True)
                response_file = f"{response_dir}/{base_filename}.json"
                
                with open(response_file, "w", encoding="utf-8") as f:
                    json.dump(response, f, ensure_ascii=False, indent=2)
                logger.info(f"응답이 저장되었습니다: {response_file}")
            
            return base_filename
            
        except Exception as e:
            logger.error(f"파일 저장 실패: {str(e)}")
            return None

    def analyze_news(
        self,
        news_items: List[Dict],
        dev_mode: bool = False
    ) -> Dict:
        """뉴스를 분석합니다.
        
        Args:
            news_items: 분석할 뉴스 목록
            dev_mode: 개발 모드 여부 (True일 경우 더미 데이터 반환)
            
        Returns:
            분석 결과
        """
        if not news_items:
            return {
                "success": False,
                "error": "분석할 뉴스가 없습니다."
            }
            
        # 심볼은 첫 번째 뉴스에서 가져옴
        symbol = news_items[0]["symbol"]
            
        # 개발 모드일 경우 더미 데이터 반환
        if dev_mode:
            dummy_response = self._get_dummy_response(symbol)
            self._save_prompt_and_response(symbol, "개발 모드 더미 데이터", dummy_response)
            return dummy_response
            
        # 프롬프트 생성 및 모델 호출
        prompt = self._create_prompt(news_items)
        
        # 프롬프트 토큰 분석
        token_count = self._count_tokens(prompt)
        logger.info(f"프롬프트 토큰 수 (추정치): {token_count}")
        
        # GPT-4 API 호출
        response = self._call_gpt4(prompt)
        if not response:
            error_result = {
                "success": False,
                "error": "API 호출 실패"
            }
            self._save_prompt_and_response(symbol, prompt, error_result)
            return error_result
            
        try:
            # API 응답에서 실제 응답 텍스트 추출
            content = response["choices"][0]["message"]["content"]
            logger.debug(f"GPT 응답: {content}")
            
            # JSON 파싱
            analysis = json.loads(content)
            
            # 결과 생성
            result = {
                "success": True,
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "news_count": len(news_items),
                "analysis": analysis
            }
            
            # 프롬프트와 응답 저장
            self._save_prompt_and_response(symbol, prompt, result)
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": f"분석 중 오류 발생: {str(e)}"
            }
            self._save_prompt_and_response(symbol, prompt, error_result)
            return error_result
    
    def format_analysis(self, result: Dict) -> str:
        """분석 결과를 보기 좋게 포맷팅합니다."""
        if not result["success"]:
            return f"분석 실패: {result.get('error', '알 수 없는 오류')}"
        
        symbol = result["symbol"]
        analysis = result["analysis"]
        timestamp = datetime.fromisoformat(result["timestamp"]).strftime("%Y-%m-%d %H:%M")
        
        output = []
        output.append(f"\n📰 {symbol} 뉴스 요약 ({timestamp})")
        output.append("=" * 60)
        
        # 각 뉴스 분석
        output.append("\n📑 개별 뉴스 분석")
        for item in analysis["news_analysis"]:
            output.append(f"\n[뉴스 {item['id']}]")
            output.append(f"• 요약: {item['summary']}")
            output.append(f"• 감정 점수: {item['sentiment_score']:.2f} ({self._get_sentiment_label(item['sentiment_score'])})")
            output.append(f"• 연관성 점수: {item['relevance_score']:.2f}")
            
        # 전체 요약
        output.append("\n📌 전체 요약")
        output.append(analysis["overall_summary"])
        
        # 평균 점수
        output.append("\n📊 종합 점수")
        output.append(f"• 평균 감정 점수: {analysis['average_sentiment']:.2f} ({self._get_sentiment_label(analysis['average_sentiment'])})")
        output.append(f"• 평균 연관성 점수: {analysis['average_relevance']:.2f}")
        
        return "\n".join(output) 