"""Tests for auth middleware and rate limiting."""
import pytest
from unittest.mock import MagicMock, patch


def test_check_rate_limit_within_limit():
    """Rate limit should not raise when under the limit."""
    with patch("backend.app.auth._get_redis") as mock_redis:
        r = MagicMock()
        r.incr.return_value = 1
        r.expire.return_value = True
        mock_redis.return_value = r

        from backend.app.auth import check_rate_limit
        # Should not raise
        check_rate_limit("test-org", "investigations")
        r.incr.assert_called_once()


def test_check_rate_limit_exceeded():
    """Rate limit should raise 429 when over the limit."""
    with patch("backend.app.auth._get_redis") as mock_redis:
        r = MagicMock()
        r.incr.return_value = 101  # over investigations limit of 100
        r.ttl.return_value = 3600
        mock_redis.return_value = r

        from fastapi import HTTPException
        from backend.app.auth import check_rate_limit
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("test-org", "investigations")
        assert exc_info.value.status_code == 429
