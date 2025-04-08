import os
import json
import logging
import traceback
from queue import Queue, Empty
from threading import Thread
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict

class DateTimeEncoder(json.JSONEncoder):
    """datetime 객체를 JSON으로 직렬화하기 위한 인코더"""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        return super().default(obj)

@dataclass
class LogEntry:
    """로그 엔트리 데이터 클래스"""
    timestamp: str
    category: str
    message: str
    data: Optional[Dict] = None
    stacktrace: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        """로그 엔트리를 딕셔너리로 변환"""
        return asdict(self)

class LogCategory:
    """로그 카테고리 정의"""
    SYSTEM = "SYSTEM"      # 시스템 상태, 시작/종료
    TRADING = "TRADING"    # 매매 실행 관련
    DECISION = "DECISION"  # 매매 판단 관련
    ASSET = "ASSET"       # 자산 상태 관련
    DISCORD = "DISCORD"   # Discord 알림 관련
    ERROR = "ERROR"       # 에러/예외 상황
    API = "API"           # API 호출 관련
    MARKET = "MARKET"     # 시장 데이터 관련

class LogManager:
    """로깅 관리자"""
    
    def __init__(self, base_dir: str = "logs/trading_sessions"):
        """
        Args:
            base_dir (str): 로그 파일이 저장될 기본 디렉토리 경로
        """
        self.base_dir = base_dir
        self.current_log_file: Optional[str] = None
        self.log_queue = Queue()
        self.is_running = False
        self.logging_thread: Optional[Thread] = None
        
        # 로거 설정
        self.logger = logging.getLogger('log_manager')
        self.logger.setLevel(logging.INFO)
        
        self._initialize_log_directory()
    
    def _initialize_log_directory(self):
        """로그 디렉토리를 초기화합니다."""
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            self.logger.info(f"로그 디렉토리 초기화 완료: {self.base_dir}")
        except Exception as e:
            self.logger.error(f"로그 디렉토리 생성 실패: {str(e)}")
            raise
    
    def start_new_trading_session(self, symbol: str):
        """새로운 트레이딩 세션을 시작하고 새 로그 파일을 생성합니다.

        Args:
            symbol (str): 트레이딩 심볼 (예: BTC)
        """
        try:
            # 이전 세션이 실행 중이면 중지
            if self.is_running:
                self.stop()
            
            # 새로운 로그 파일 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_log_file = os.path.join(self.base_dir, f"{symbol}_{timestamp}.log")
            
            # 로깅 쓰레드 시작
            self.start_logging_thread()
            
            # 세션 시작 로그
            self.log(
                category=LogCategory.SYSTEM,
                message=f"새로운 트레이딩 세션 시작: {symbol}",
                data={"symbol": symbol, "log_file": self.current_log_file}
            )
            
        except Exception as e:
            self.logger.error(f"새 트레이딩 세션 시작 실패: {str(e)}")
            raise
    
    def start_logging_thread(self):
        """로깅 쓰레드를 시작합니다."""
        self.is_running = True
        self.logging_thread = Thread(target=self._logging_worker, daemon=True)
        self.logging_thread.start()
        self.logger.info("로깅 쓰레드 시작됨")
    
    def stop(self):
        """로깅을 중지합니다."""
        if self.is_running:
            self.is_running = False
            if self.logging_thread:
                self.logging_thread.join()
            self.logger.info("로깅 쓰레드 종료됨")
    
    def log(self, category: str, message: str, data: Dict = None):
        """로그를 큐에 추가합니다.

        Args:
            category (str): 로그 카테고리
            message (str): 로그 메시지
            data (Dict, optional): 추가 데이터. Defaults to None.
        """
        try:
            stacktrace = None
            if category == LogCategory.ERROR:
                stacktrace = traceback.format_stack()[:-1]  # 현재 함수 호출은 제외
            
            log_entry = LogEntry(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                category=category,
                message=message,
                data=data,
                stacktrace=stacktrace
            )
            self.log_queue.put(log_entry)
            
        except Exception as e:
            self.logger.error(f"로그 추가 실패: {str(e)}")
    
    def _logging_worker(self):
        """로그 큐에서 로그를 가져와서 파일에 기록하는 워커 쓰레드"""
        while self.is_running:
            try:
                # 1초 타임아웃으로 큐에서 로그 가져오기
                log_entry = self.log_queue.get(timeout=1)
                self._write_log(log_entry)
                self.log_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"로그 처리 중 오류 발생: {str(e)}")
    
    def _write_log(self, log_entry: LogEntry):
        """로그를 파일에 기록합니다.

        Args:
            log_entry (LogEntry): 기록할 로그 엔트리
        """
        if not self.current_log_file:
            self.logger.error("현재 로그 파일이 설정되지 않았습니다.")
            return
        
        try:
            with open(self.current_log_file, 'a', encoding='utf-8') as f:
                json.dump(log_entry.to_dict(), f, ensure_ascii=False, cls=DateTimeEncoder)
                f.write('\n')
                
        except Exception as e:
            self.logger.error(f"로그 파일 쓰기 실패: {str(e)}")
    
    def __del__(self):
        """소멸자: 실행 중인 로깅 쓰레드를 정리합니다."""
        self.stop() 