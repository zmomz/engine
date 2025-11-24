import logging
import pytest
from app.core.logging_config import SensitiveDataFilter, setup_logging

def test_sensitive_data_filter():
    filter_ = SensitiveDataFilter()
    
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py", lineno=1,
        msg="User login: api_key='12345', secret_key='abcde'", args=(), exc_info=None
    )
    filter_.filter(record)
    assert "api_key=***MASKED***" in record.msg
    assert "secret_key=***MASKED***" in record.msg

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py", lineno=1,
        msg="encrypted_api_keys={'data': 'enc'}", args=(), exc_info=None
    )
    filter_.filter(record)
    assert "encrypted_api_keys=***MASKED***" in record.msg

    # Non-string msg
    record.msg = 123
    assert filter_.filter(record) is True

def test_setup_logging(tmp_path):
    # Mock logs dir to use tmp_path
    import app.core.logging_config as lc
    
    original_path = lc.Path
    lc.Path = lambda x: tmp_path / x
    
    try:
        log_file = setup_logging()
        assert log_file.name == "app.log"
        assert log_file.exists()
        
        logger = logging.getLogger()
        assert len(logger.handlers) > 0
    finally:
        lc.Path = original_path
