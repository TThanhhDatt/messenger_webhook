import logging
import json
import re
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console

console = Console(force_terminal=True, width=120)

class ColoredLogger:
    """Wrapper class cung cấp các method với màu cố định cho console"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def debug(self, message, color="cyan", **extra_fields):
        self.logger.debug(f"🔍 {message}", extra={"markup": True, "color": color, **extra_fields})
    
    def info(self, message, color="bright_magenta", **extra_fields):
        self.logger.info(f"ℹ️  {message}", extra={"markup": True, "color": color, **extra_fields})
    
    def warning(self, message, color="orange3", **extra_fields):
        self.logger.warning(f"⚠️  {message}", extra={"markup": True, "color": color, **extra_fields})
    
    def error(self, message, color="bright_red", **extra_fields):
        self.logger.error(f"❌ {message}", extra={"markup": True, "color": color, **extra_fields})
    
    def critical(self, message, color="bold purple", **extra_fields):
        self.logger.critical(f"🚨 {message}", extra={"markup": True, "color": color, **extra_fields})
    
    def success(self, message, **extra_fields):
        self.logger.info(f"✅ {message}", extra={"markup": True, "color": "green", **extra_fields})
    
    def fail(self, message, **extra_fields):
        self.logger.error(f"💥 {message}", extra={"markup": True, "color": "red", **extra_fields})
    
    def highlight(self, message, **extra_fields):
        self.logger.info(f"⭐ {message}", extra={"markup": True, "color": "yellow", **extra_fields})
    
    def subtle(self, message, **extra_fields):
        self.logger.info(f"{message}", extra={"markup": True, "color": "dim", **extra_fields})


class JsonFormatter(logging.Formatter):
    """
    Formatter cho file - xuất log dưới dạng JSON
    """
    def format(self, record: logging.LogRecord) -> str:
        # Loại bỏ rich markup tags và emoji khỏi message
        msg = record.getMessage()
        msg = re.sub(r'\[/?[a-z_\s]+\]', '', msg)  # Loại bỏ [color] tags
        msg = re.sub(r'[🔍ℹ️⚠️❌🚨✅💥⭐]', '', msg).strip()  # Loại bỏ emoji
        
        # Tạo log object JSON
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Thêm exception info nếu có
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Thêm các extra fields (nếu có)
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                          'levelname', 'lineno', 'module', 'msecs', 'message', 
                          'pathname', 'process', 'processName', 'relativeCreated', 
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                          'markup', 'color', 'highlighter']:
                extra_fields[key] = value
        
        if extra_fields:
            log_obj["extra"] = extra_fields
        
        return json.dumps(log_obj, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """
    Formatter cho console - loại bỏ hoàn toàn markup và ANSI codes
    """
    def format(self, record: logging.LogRecord) -> str:
        # Tạo bản sao record để không ảnh hưởng đến handlers khác
        record_copy = logging.makeLogRecord(record.__dict__)
        
        # Loại bỏ rich markup tags khỏi message
        msg = record_copy.getMessage()
        msg = re.sub(r'\[/?[a-z_\s]+\]', '', msg)
        
        # Gán lại message đã clean
        record_copy.msg = msg
        record_copy.args = ()
        
        return super().format(record_copy)


def setup_logging(name: str, log_filename: str = "app.log", json_format: bool = True):
    """
    Setup logging với options:
    - json_format=True: File log dạng JSON (khuyến nghị cho Grafana/Loki)
    - json_format=False: File log dạng plain text
    """
    # Im lặng các logger "ồn ào"
    for noisy in ['urllib3', 'openai', 'langsmith', 'httpcore', 'httpx']:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

    # --- Handler console (Rich) - CÓ MÀU ---
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True
    )
    rich_handler.setLevel(logging.DEBUG)

    # --- Handler file ---
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Chọn formatter theo option
    if json_format:
        file_handler.setFormatter(JsonFormatter())
    else:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        file_handler.setFormatter(PlainFormatter(fmt, datefmt=datefmt))

    # Thêm handlers
    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)

    return ColoredLogger(logger)


# Test
if __name__ == "__main__":
    print("=== Test JSON Format ===")
    logger_json = setup_logging("app.test", "test_color.log", json_format=True)
    logger_json.debug("Debug message")
    logger_json.info("Info message")
    logger_json.warning("Warning message")
    logger_json.error("Error message", user_id=123, action="login")
    logger_json.success("Success message")
    logger_json.critical("Critical message")
    logger_json.fail("Failed message", reason="connection_timeout")
    logger_json.highlight("Highlighted message")
    logger_json.subtle("Subtle message")
    
    print("\n=== Test Plain Text Format ===")
    logger_plain = setup_logging("app.plain", "test_plain.log", json_format=False)
    logger_plain.error("This is plain text format")
    
    print("\n✅ Kiểm tra:")
    print("   - Console: Có màu sắc đẹp")
    print("   - File test_json.log: JSON format (mỗi log 1 dòng)")
    print("   - File test_plain.log: Plain text format")
    
    # Test exception logging
    try:
        1 / 0
    except Exception as e:
        logger_json.error("Exception occurred", exc_info=True)
    
    print("\n📝 Xem file test_json.log để thấy format JSON!")