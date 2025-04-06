import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from src.utils.logger import setup_logger

logger = setup_logger('news')

class News:
    """코인 관련 뉴스 수집기"""
    
    # 뉴스 소스 URL
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    NAVER_NEWS_SEARCH = "https://search.naver.com/search.naver?where=news&query={query}"
    COINDESK_RSS = "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"  # 기본 RSS
    COINDESK_SEARCH = "https://www.coindesk.com/search?q={query}"  # 검색용
    
    # 심볼별 추가 검색 키워드
    SYMBOL_KEYWORDS = {
        "BTC": ["비트코인", "Bitcoin", "BTC", "$BTC", "bitcoin"],
        "ETH": ["이더리움", "Ethereum", "ETH", "$ETH", "ethereum"],
        "XRP": ["리플", "Ripple", "XRP", "$XRP", "ripple"],
        "DOGE": ["도지코인", "Dogecoin", "DOGE", "$DOGE", "dogecoin"],
        "SOL": ["솔라나", "Solana", "SOL", "$SOL", "solana"],
    }
    
    # 기본 검색 키워드 (모든 심볼에 공통 적용)
    COMMON_KEYWORDS = [
        "가상자산", "암호화폐", "크립토",
        "SEC", "CFTC", "코인베이스", "바이낸스",
        "cryptocurrency", "crypto", "blockchain"
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_update = None
        self.cached_news = {}  # symbol별 캐시
        self.cache_duration = 300  # 5분 캐시
    
    def _parse_datetime(self, date_str: str) -> datetime:
        """뉴스 발행일자를 파싱합니다."""
        try:
            # RSS 표준 형식
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        except:
            try:
                # 네이버 뉴스 형식
                if "분 전" in date_str:
                    minutes = int(date_str.replace("분 전", ""))
                    return datetime.now() - timedelta(minutes=minutes)
                elif "시간 전" in date_str:
                    hours = int(date_str.replace("시간 전", ""))
                    return datetime.now() - timedelta(hours=hours)
                elif "일 전" in date_str:
                    days = int(date_str.replace("일 전", ""))
                    return datetime.now() - timedelta(days=days)
                elif re.match(r'\d{4}\.\d{2}\.\d{2}\.', date_str):
                    # YYYY.MM.DD. 형식
                    return datetime.strptime(date_str.strip('.'), "%Y.%m.%d")
                elif re.match(r'\d{4}\-\d{2}\-\d{2}', date_str):
                    # YYYY-MM-DD 형식
                    return datetime.strptime(date_str.split()[0], "%Y-%m-%d")
                else:
                    logger.debug(f"지원하지 않는 날짜 형식: {date_str}")
                    return datetime.now()
            except Exception as e:
                logger.debug(f"날짜 파싱 실패: {date_str} (에러: {str(e)})")
                return datetime.now()
    
    def _clean_text(self, text: str) -> str:
        """텍스트를 정제합니다."""
        # HTML 태그 및 엔티티 제거
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&[a-zA-Z]+;', ' ', text)
        # 특수문자 정제 (한글, 영문, 숫자, 기본 문장부호만 허용)
        text = re.sub(r'[^\w\s가-힣.,·\-()%]', '', text)
        # 연속된 공백 제거
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _get_symbol_keywords(self, symbol: str) -> List[str]:
        """심볼에 대한 검색 키워드 목록을 반환합니다."""
        symbol = symbol.upper()
        keywords = self.SYMBOL_KEYWORDS.get(symbol, [symbol])
        if symbol not in self.SYMBOL_KEYWORDS:
            # 기본 키워드 생성
            keywords.extend([
                f"{symbol} 코인",
                f"{symbol} 시세",
                f"{symbol} 가격"
            ])
        return keywords
    
    def _get_coindesk_news(self, keyword: str, max_age_hours: int = 24) -> List[Dict]:
        """CoinDesk 뉴스를 수집합니다."""
        news_items = []
        now = datetime.now()
        
        try:
            # RSS 피드에서 최신 뉴스 가져오기
            feed = feedparser.parse(self.COINDESK_RSS)
            
            for entry in feed.entries:
                # 키워드 필터링
                if not any(kw.lower() in entry.title.lower() or 
                          kw.lower() in entry.description.lower() 
                          for kw in [keyword]):
                    continue
                
                published_at = self._parse_datetime(entry.published)
                age_hours = (now - published_at).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    continue
                
                # 제목과 출처 정제
                clean_title = self._clean_text(entry.title)
                
                # 요약 정제
                summary = self._clean_text(entry.description)
                if clean_title in summary:
                    summary = summary.replace(clean_title, "").strip()
                
                news_items.append({
                    "title": clean_title,
                    "summary": summary,
                    "link": entry.link,
                    "published_at": published_at,
                    "source": "CoinDesk",
                    "keyword": keyword,
                    "symbol": keyword.upper() if keyword.upper() in self.SYMBOL_KEYWORDS else None
                })
            
            # 검색 API를 통한 추가 뉴스 수집
            search_url = self.COINDESK_SEARCH.format(query=quote_plus(keyword))
            response = self.session.get(search_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for article in soup.select('article'):
                title_elem = article.select_one('h6')
                if not title_elem:
                    continue
                
                title = self._clean_text(title_elem.text)
                link = article.select_one('a')
                if link:
                    link = 'https://www.coindesk.com' + link.get('href', '')
                
                # 이미 RSS에서 수집된 뉴스는 건너뛰기
                if any(item['link'] == link for item in news_items):
                    continue
                
                time_elem = article.select_one('time')
                published = time_elem.get('datetime') if time_elem else None
                published_at = self._parse_datetime(published) if published else now
                
                age_hours = (now - published_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    continue
                
                summary = ""
                desc_elem = article.select_one('p')
                if desc_elem:
                    summary = self._clean_text(desc_elem.text)
                
                news_items.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published_at": published_at,
                    "source": "CoinDesk",
                    "keyword": keyword,
                    "symbol": keyword.upper() if keyword.upper() in self.SYMBOL_KEYWORDS else None
                })
            
            logger.debug(f"CoinDesk 뉴스 {len(news_items)}개 수집 완료")
            
        except Exception as e:
            logger.error(f"CoinDesk 뉴스 수집 실패: {str(e)}")
        
        return news_items

    def get_news(
        self,
        symbol: str,
        max_age_hours: int = 24,
        limit: int = 10,
        use_cache: bool = True
    ) -> List[Dict]:
        """특정 심볼의 뉴스를 수집합니다.
        
        Args:
            symbol: 코인 심볼 (예: BTC, ETH)
            max_age_hours: 최대 뉴스 나이 (시간)
            limit: 최대 뉴스 개수
            use_cache: 캐시 사용 여부
            
        Returns:
            List[Dict]: 뉴스 목록
        """
        symbol = symbol.upper()
        now = datetime.now()
        
        # 캐시 체크
        if (
            use_cache
            and symbol in self.cached_news
            and self.last_update is not None
            and (now - self.last_update).total_seconds() < self.cache_duration
        ):
            logger.debug(f"{symbol} 캐시된 뉴스 반환")
            return self.cached_news[symbol]
        
        all_news = []
        keywords = self._get_symbol_keywords(symbol)
        
        # 키워드별 뉴스 수집
        for keyword in keywords:
            try:
                # 구글 뉴스 수집
                url = self.GOOGLE_NEWS_RSS.format(query=quote_plus(keyword))
                feed = feedparser.parse(url)
                
                for entry in feed.entries:
                    published_at = self._parse_datetime(entry.published)
                    age_hours = (now - published_at).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        continue
                    
                    # 제목과 출처 분리
                    title_parts = entry.title.split(' - ')
                    clean_title = self._clean_text(title_parts[0])
                    source = title_parts[-1] if len(title_parts) > 1 else "Unknown"
                    
                    # 요약 정제
                    summary = self._clean_text(entry.get("summary", ""))
                    if clean_title in summary:
                        summary = summary.replace(clean_title, "").strip()
                    
                    all_news.append({
                        "title": clean_title,
                        "summary": summary,
                        "link": entry.link,
                        "published_at": published_at,
                        "source": source,
                        "keyword": keyword,
                        "symbol": symbol
                    })
                
                # 네이버 뉴스 수집
                url = self.NAVER_NEWS_SEARCH.format(query=quote_plus(keyword))
                response = self.session.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for news in soup.select('.news_area')[:5]:
                    title_elem = news.select_one('.news_tit')
                    if not title_elem:
                        continue
                    
                    title = self._clean_text(title_elem.get('title', ''))
                    link = title_elem.get('href', '')
                    
                    desc_elem = news.select_one('.dsc_txt_wrap')
                    summary = self._clean_text(desc_elem.text) if desc_elem else ""
                    
                    source_elem = news.select_one('.info_group a:first-child')
                    source = source_elem.text.strip() if source_elem else "Unknown"
                    
                    time_elem = news.select_one('.info_group span.info')
                    published = time_elem.text.strip() if time_elem else ""
                    published_at = self._parse_datetime(published)
                    
                    age_hours = (now - published_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        continue
                    
                    all_news.append({
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "published_at": published_at,
                        "source": source,
                        "keyword": keyword,
                        "symbol": symbol
                    })
                
                # CoinDesk 뉴스 수집
                coindesk_news = self._get_coindesk_news(keyword, max_age_hours)
                all_news.extend(coindesk_news)
                
                time.sleep(1)  # API 호출 간격 조절
                
            except Exception as e:
                logger.error(f"{symbol} {keyword} 뉴스 수집 실패: {str(e)}")
                continue
        
        # 중복 제거 (URL 기준)
        unique_news = list({news["link"]: news for news in all_news}.values())
        
        # 발행일시 기준 내림차순 정렬 후 limit 적용
        unique_news.sort(key=lambda x: x["published_at"], reverse=True)
        unique_news = unique_news[:limit]
        
        # 캐시 업데이트
        if use_cache:
            self.cached_news[symbol] = unique_news
            self.last_update = now
        
        logger.info(f"{symbol} 뉴스 {len(unique_news)}개 수집 완료")
        return unique_news
    
    def format_news(
        self,
        news_items: List[Dict],
        show_summary: bool = True
    ) -> str:
        """뉴스 결과를 보기 좋게 포맷팅합니다."""
        if not news_items:
            return "수집된 뉴스가 없습니다."
        
        symbol = news_items[0]["symbol"]
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        output = []
        output.append(f"\n📰 {symbol} 뉴스 모니터링 ({current_time})")
        output.append("=" * 60)
        
        # 통계 정보
        sources = {}
        for item in news_items:
            sources[item['source']] = sources.get(item['source'], 0) + 1
        
        output.append(f"\n📊 뉴스 통계")
        output.append(f"• 총 뉴스: {len(news_items)}개")
        output.append(f"• 언론사별 뉴스:")
        for src, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            output.append(f"  - {src}: {count}개")
        
        # 뉴스 목록
        output.append("\n📑 뉴스 목록")
        for i, item in enumerate(news_items, 1):
            published = item["published_at"].strftime("%Y-%m-%d %H:%M")
            output.append(f"\n{i}. {item['title']}")
            output.append(f"   {item['source']} | {published}")
            
            if show_summary and item["summary"]:
                summary = item["summary"]
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                output.append(f"\n   {summary}")
            
            output.append(f"   👉 {item['link']}")
        
        return "\n".join(output) 