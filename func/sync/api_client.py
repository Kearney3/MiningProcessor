"""
MineBase HTTP API 客户端 (contractVersion 2)。

支持 session → batch → confirm 窗口化导入流程。
"""
import json

from func.logger import get_logger
from func.sync.constants import CONTRACT_VERSION

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 异常类
# ---------------------------------------------------------------------------


class MineBaseAPIError(RuntimeError):
    """MineBase API 通用错误。"""

    def __init__(self, message: str, status_code: int = 0, error_code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class SessionLimitReachedError(MineBaseAPIError):
    """并发导入会话数达到上限 (HTTP 409 / IMPORT_SESSION_LIMIT_REACHED)。"""


class SessionExpiredError(MineBaseAPIError):
    """导入会话已过期 (HTTP 410 / SESSION_EXPIRED)。"""


# ---------------------------------------------------------------------------
# HTTP 客户端
# ---------------------------------------------------------------------------


class MineBaseAPIClient:
    """MineBase HTTP API 客户端 (contractVersion 2)。"""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        """发送 HTTP 请求，对 409/410 抛出特定异常。"""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")[:500]
            # 尝试解析 JSON 错误体提取 errorCode
            error_code = ""
            try:
                err_json = json.loads(error_body)
                error_code = err_json.get("errorCode") or err_json.get("code", "")
            except (json.JSONDecodeError, ValueError):
                pass

            msg = f"HTTP {e.code}: {error_body}"

            # 409: 会话限制 / 状态冲突
            if e.code == 409:
                if error_code in ("IMPORT_SESSION_LIMIT_REACHED", "IMPORT_SESSION_BYTES_EXCEEDED"):
                    raise SessionLimitReachedError(msg, status_code=409, error_code=error_code) from e
                raise MineBaseAPIError(msg, status_code=409, error_code=error_code) from e

            # 410: 会话过期
            if e.code == 410:
                raise SessionExpiredError(msg, status_code=410, error_code=error_code) from e

            raise RuntimeError(msg) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"连接失败: {url} — {e.reason}") from e

    # ------------------------------------------------------------------
    # 认证
    # ------------------------------------------------------------------

    def login(self) -> None:
        """登录获取 JWT token。"""
        resp = self._request("POST", "/api/auth/login", {
            "username": self.username,
            "password": self.password,
        })
        self.token = resp.get("data", {}).get("token") or resp.get("token")
        if not self.token:
            raise RuntimeError(f"登录失败，未获取到 token (响应字段: {list(resp.keys())})")
        logger.info("MineBase 登录成功")

    # ------------------------------------------------------------------
    # 导入会话 (contractVersion 2)
    # ------------------------------------------------------------------

    def create_session(
        self,
        table: str,
        expected_batches: int,
        total_rows: int,
        conflict_policy: str = "SKIP",
    ) -> dict:
        """创建导入会话。

        Args:
            table: 目标表名。
            expected_batches: 预期批次数。
            total_rows: 预期总行数。
            conflict_policy: 冲突策略 ('SKIP' | 'UPDATE' | 'REJECT')。

        Returns:
            服务端返回的完整响应（含 data.session）。
        """
        resp = self._request("POST", f"/api/import/{table}/session", {
            "contractVersion": CONTRACT_VERSION,
            "expectedBatches": expected_batches,
            "totalRows": total_rows,
            "conflictPolicy": conflict_policy,
        })
        session_id = resp.get("data", {}).get("sessionId") or resp.get("sessionId")
        if not session_id:
            # v2 响应可能嵌套在 data.session.id
            session = resp.get("data", {}).get("session", {})
            session_id = session.get("id", "")
        if not session_id:
            raise RuntimeError(f"创建会话失败: {resp}")
        version = resp.get("data", {}).get("session", {}).get("version", 0)
        logger.info("创建导入会话: %s (table=%s, version=%d)", session_id[:8], table, version)
        return resp

    def send_batch(
        self,
        table: str,
        session_id: str,
        rows: list[dict],
        field_mappings: list[dict],
        batch_index: int,
        total_batches: int,
        expected_version: int = 0,
        row_offset: int = 0,
    ) -> dict:
        """发送一批数据到 staging (contractVersion 2)。"""
        payload = {
            "contractVersion": CONTRACT_VERSION,
            "sessionId": session_id,
            "expectedVersion": expected_version,
            "rows": rows,
            "fieldMappings": field_mappings,
            "batchIndex": batch_index,
            "totalBatches": total_batches,
            "rowOffset": row_offset,
            "skipUnmatchedFK": True,
        }
        return self._request("POST", f"/api/import/{table}/batch", payload)

    def confirm_batch(
        self,
        table: str,
        session_id: str,
        expected_version: int = 0,
    ) -> dict:
        """确认导入批次 (contractVersion 2, 窗口化)。

        服务端按窗口处理数据，客户端需循环调用直到返回 done=true。
        """
        return self._request("POST", f"/api/import/{table}/confirm", {
            "contractVersion": CONTRACT_VERSION,
            "sessionId": session_id,
            "expectedVersion": expected_version,
        })

    def cancel_import(self, table: str, session_id: str, expected_version: int = 0) -> dict:
        """取消导入 (contractVersion 2)。"""
        return self._request("POST", f"/api/import/{table}/cancel", {
            "contractVersion": CONTRACT_VERSION,
            "sessionId": session_id,
            "expectedVersion": expected_version,
        })
