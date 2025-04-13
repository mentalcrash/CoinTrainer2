import os
import json
import logging
import traceback
from queue import Queue, Empty
from threading import Thread
from datetime import datetime
from typing import Dict, Optional, List, Any, Literal
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
    """로그 카테고리"""
    SYSTEM = "SYSTEM"         # 시스템 관련
    WARNING = "WARNING"        # 경고
    ERROR = "ERROR"          # 오류
    API = "API"              # API 호출
    TRADE = "TRADE"          # 거래 실행
    TRADING = "TRADING"      # 거래 관련
    MARKET = "MARKET"        # 시장 데이터
    MONITOR = "MONITOR"      # 주문 모니터링
    MONITOR_STATE = "MONITOR_STATE"    # 모니터링 상태 변경
    MONITOR_ERROR = "MONITOR_ERROR"    # 모니터링 오류
    
    # 라운드 관련 카테고리
    ROUND = 'ROUND'                    # 일반적인 라운드 관련 로그
    ROUND_STATE = 'ROUND_STATE'        # 라운드 상태 변경
    ROUND_ENTRY = 'ROUND_ENTRY'        # 진입 관련 (시그널, 주문, 체결)
    ROUND_EXIT = 'ROUND_EXIT'          # 청산 관련 (시그널, 주문, 체결)
    ROUND_METRICS = 'ROUND_METRICS'    # 성과 지표 관련
    ROUND_WARNING = 'ROUND_WARNING'    # 라운드 관련 경고
    ROUND_ERROR = 'ROUND_ERROR'        # 라운드 관련 오류
    
    ASSET = 'ASSET'                    # 자산 관련
    
    DISCORD = 'DISCORD'                # 디스코드 관련

class LogManager:
    """로깅 관리자"""
    
    def __init__(
        self,
        base_dir: str = "logs/trading_sessions",
        log_mode: Literal["file", "console", "both"] = "file",
        console_format: Literal["simple", "detailed"] = "simple"
    ):
        """
        Args:
            base_dir (str): 로그 파일이 저장될 기본 디렉토리 경로
            log_mode (Literal["file", "console", "both"]): 로깅 모드
            console_format (Literal["simple", "detailed"]): 콘솔 출력 형식
        """
        self.base_dir = base_dir
        self.log_mode = log_mode
        self.console_format = console_format
        self.current_log_file: Optional[str] = None
        self.log_queue = Queue()
        self.is_running = False
        self.logging_thread: Optional[Thread] = None
        
        # 로거 설정
        self.logger = logging.getLogger('log_manager')
        self.logger.setLevel(logging.INFO)
        
        # 콘솔 핸들러 설정
        if log_mode in ['console', 'both']:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            self.logger.addHandler(console_handler)
        
        if log_mode in ['file', 'both']:
            self._initialize_log_directory()
    
    def _initialize_log_directory(self):
        """로그 디렉토리를 초기화합니다."""
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            self.logger.info(f"로그 디렉토리 초기화 완료: {self.base_dir}")
        except Exception as e:
            self.logger.error(f"로그 디렉토리 생성 실패: {str(e)}")
            raise
    
    def _format_console_output(self, log_entry: LogEntry) -> str:
        """콘솔 출력용 로그 포맷을 생성합니다.
        
        Args:
            log_entry (LogEntry): 로그 엔트리
            
        Returns:
            str: 포맷된 로그 문자열
        """
        if self.console_format == 'simple':
            # 간단한 형식: [시간] [카테고리] 메시지
            return f"[{log_entry.timestamp}] [{log_entry.category}] {log_entry.message}"
        else:
            # 상세 형식: JSON 형식의 모든 데이터 포함
            return json.dumps(
                log_entry.to_dict(),
                ensure_ascii=False,
                cls=DateTimeEncoder,
                indent=2
            )
    
    def start_new_trading_session(self, symbol: str):
        """새로운 트레이딩 세션을 시작하고 새 로그 파일을 생성합니다.

        Args:
            symbol (str): 트레이딩 심볼 (예: BTC)
        """
        try:
            # 이전 세션이 실행 중이면 중지
            if self.is_running:
                self.stop()
            
            # 파일 로깅이 활성화된 경우에만 새 로그 파일 생성
            if self.log_mode in ['file', 'both']:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.current_log_file = os.path.join(self.base_dir, f"{symbol}_{timestamp}.log")
            
            # 로깅 쓰레드 시작
            self.start_logging_thread()
            
            # 세션 시작 로그
            self.log(
                category=LogCategory.SYSTEM,
                message=f"새로운 트레이딩 세션 시작: {symbol}",
                data={
                    "symbol": symbol,
                    "log_file": self.current_log_file,
                    "log_mode": self.log_mode,
                    "console_format": self.console_format if self.log_mode in ['console', 'both'] else None
                }
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
        """로그를 파일과/또는 콘솔에 기록합니다.

        Args:
            log_entry (LogEntry): 기록할 로그 엔트리
        """
        try:
            # 파일 로깅
            if self.log_mode in ['file', 'both'] and self.current_log_file:
                with open(self.current_log_file, 'a', encoding='utf-8') as f:
                    json.dump(log_entry.to_dict(), f, ensure_ascii=False, cls=DateTimeEncoder)
                    f.write('\n')
            
            # 콘솔 로깅
            if self.log_mode in ['console', 'both']:
                formatted_log = self._format_console_output(log_entry)
                
                # 에러 로그는 빨간색으로 표시
                if log_entry.category in [LogCategory.ERROR, LogCategory.ROUND_ERROR]:
                    print("\033[91m" + formatted_log + "\033[0m")  # 빨간색
                # 경고 로그는 노란색으로 표시
                elif log_entry.category in [LogCategory.WARNING, LogCategory.ROUND_WARNING]:
                    print("\033[93m" + formatted_log + "\033[0m")  # 노란색
                # 성공 로그는 초록색으로 표시
                elif "성공" in log_entry.message or "완료" in log_entry.message:
                    print("\033[92m" + formatted_log + "\033[0m")  # 초록색
                # 나머지는 기본 색상
                else:
                    print(formatted_log)
                
        except Exception as e:
            self.logger.error(f"로그 쓰기 실패: {str(e)}")
    
    def __del__(self):
        """소멸자: 실행 중인 로깅 쓰레드를 정리합니다."""
        self.stop() 