from typing import List, Dict, Optional
import json
import requests
from datetime import datetime
from pathlib import Path
from src.news import News
import os
from src.utils.log_manager import LogManager, LogCategory

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
    
    def __init__(
        self, 
        api_key: str, 
        api_endpoint: str,
        log_manager: Optional[LogManager] = None
    ):
        """초기화
        
        Args:
            api_key: OpenAI API 키
            api_endpoint: OpenAI API 엔드포인트
            log_manager: 로그 매니저 (선택사항)
        """
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.news = News()
        self.log_manager = log_manager
        
        # 실행 시간 기반 디렉토리 생성
        base_dir = Path(".temp")
        base_dir.mkdir(exist_ok=True)
        
        now = datetime.now()
        run_id = now.strftime("%Y%m%d_%H%M%S")
        self.run_dir = base_dir / run_id
        self.run_dir.mkdir(exist_ok=True)
    
    def _create_prompt(self, news_items: List[Dict], symbol: str) -> str:
        """GPT-4에 전달할 프롬프트를 생성합니다.
        
        Args:
            news_items: 뉴스 목록
            symbol: 코인 심볼
            
        Returns:
            프롬프트 문자열
        """
        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"{symbol} 뉴스 분석 프롬프트 생성 시작",
                data={"news_count": len(news_items)}
            )
            
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
        for i, news in enumerate(news_items, 1):
            published = news['published_at'].strftime("%Y-%m-%d %H:%M")
            prompt += f"""[뉴스 {i}]
제목: {news['title']}
출처: {news['source']} ({published})
내용: {news['summary']}
                                                                {' ' * (i * 2)}
"""

        prompt += """다음 JSON 형식으로 응답해주세요:
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

        if self.log_manager:
            self.log_manager.log(
                category=LogCategory.SYSTEM,
                message=f"{symbol} 뉴스 분석 프롬프트 생성 완료",
                data={"prompt_length": len(prompt)}
            )
            
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
            "model": "gpt-4o-mini-2024-07-18",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="GPT-4 API 호출 시작",
                    data={"endpoint": self.api_endpoint}
                )
                
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=data,
                timeout=30
            )
            
            # 응답 상태 코드 확인
            if response.status_code != 200:
                error_msg = f"API 오류 응답: {response.status_code} - {response.text}"
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.API,
                        message="GPT-4 API 호출 실패",
                        data={
                            "status_code": response.status_code,
                            "response": response.text
                        }
                    )
                return {
                    "success": False,
                    "error": error_msg
                }
                
            response_data = response.json()
            
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.API,
                    message="GPT-4 API 호출 성공",
                    data={
                        "status_code": response.status_code,
                        "response": response_data
                    }
                )
            
            return {
                "success": True,
                "content": response_data["choices"][0]["message"]["content"]
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API 요청 실패: {str(e)}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="GPT-4 API 요청 실패",
                    data={"error": str(e)}
                )
            return {
                "success": False,
                "error": error_msg
            }
            
        except Exception as e:
            error_msg = f"API 호출 실패: {str(e)}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message="GPT-4 API 호출 중 예외 발생",
                    data={"error": str(e)}
                )
            return {
                "success": False,
                "error": error_msg
            }
    
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

    def _convert_datetime(self, data: Dict) -> Dict:
        """datetime 객체를 ISO 형식 문자열로 변환합니다."""
        if isinstance(data, dict):
            return {k: self._convert_datetime(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_datetime(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        return data

    def analyze_news(
        self,
        symbol: str,
        max_age_hours: int = 24,
        limit: int = 5
    ) -> Dict:
        """뉴스를 분석합니다.
        
        Args:
            symbol: 심볼 (예: BTC)
            max_age_hours: 최대 뉴스 수집 시간 (시간)
            limit: 수집할 뉴스 개수
            
        Returns:
            Dict: 분석 결과
        """
        try:
            # 뉴스 수집
            news = News(self.log_manager)
            news_items = news.get_news(symbol, max_age_hours, limit)
            
            if not news_items:
                result={
                    "success": False,
                    "overall_summary": "수집된 뉴스가 없습니다."
                }
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.SYSTEM,
                        message="수집된 뉴스가 없습니다.",
                        data=result
                    )
                return result
            
            # 프롬프트 생성
            prompt = self._create_prompt(news_items, symbol)
            
            # 프롬프트 토큰 분석
            token_count = self._count_tokens(prompt)
            
            if self.log_manager:
                # 프롬프트 내용 로깅
                self.log_manager.log(
                    category=LogCategory.SYSTEM,
                    message=f"{symbol} 프롬프트 생성 완료",
                    data={
                        "prompt": prompt,
                        "token_count": token_count,
                        "news_count": len(news_items)
                    }
                )
            
            # GPT API 호출
            response = self._call_gpt4(prompt)
                
            if not response["success"]:
                error_result = {
                    "success": False,
                    "error": response.get("error", "API 호출 실패")
                }
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message=f"{symbol} GPT API 호출 실패",
                        data=error_result
                    )
                return error_result
            
            # 응답 파싱
            try:
                # 마크다운 형식의 JSON 문자열 처리
                json_str = self._parse_json_from_markdown(response["content"])
                analysis_result = json.loads(json_str)
                analysis_result["success"] = True
                
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.SYSTEM,
                        message=f"{symbol} GPT 응답 파싱 완료",
                        data=analysis_result
                    )
                
                return analysis_result
                
            except json.JSONDecodeError as e:
                error_msg = f"응답 파싱 실패: {str(e)}"
                if self.log_manager:
                    self.log_manager.log(
                        category=LogCategory.ERROR,
                        message=error_msg,
                        data={"error": str(e)}
                    )
                return {
                    "success": False,
                    "error": error_msg
                }
            
        except Exception as e:
            error_msg = f"뉴스 분석 실패: {str(e)}"
            if self.log_manager:
                self.log_manager.log(
                    category=LogCategory.ERROR,
                    message=error_msg,
                    data={"error": str(e)}
                )
            return {
                "success": False,
                "error": error_msg
            }
    
    def format_analysis(self, result: Dict) -> str:
        """분석 결과를 보기 좋게 포맷팅합니다."""
        if not result["success"]:
            return f"분석 실패: {result.get('error', '알 수 없는 오류')}"
        
        analysis = result
        
        output = []
        output.append(f"\n📰 뉴스 요약")
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

    def _parse_json_from_markdown(self, markdown_str: str) -> dict:
        """마크다운 코드 블록에서 JSON을 파싱합니다.

        Args:
            markdown_str (str): 마크다운 형식의 JSON 문자열

        Returns:
            dict: 파싱된 JSON 데이터
        """
        # 1. 마크다운 코드 블록 제거
        json_str = markdown_str.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]  # "```json" 제거
        if json_str.endswith("```"):
            json_str = json_str[:-3]  # "```" 제거
        
        # 2. 문자열 앞뒤의 공백 제거
        return json_str.strip() 