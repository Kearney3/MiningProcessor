"""MineBase HTTP API 客户端。"""
import json

from func.logger import get_logger

logger = get_logger(__name__)


class MineBaseAPIClient:
    """MineBase HTTP API 客户端。"""

    def __init__(self, url: str, username: str, password: str):
        self.base_url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        """发送 HTTP 请求。"""
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
            error_body = e.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"HTTP {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"连接失败: {url} — {e.reason}") from e

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

    def create_session(self, table: str) -> str:
        """创建导入会话。"""
        resp = self._request("POST", f"/api/import/{table}/session")
        session_id = resp.get("data", {}).get("sessionId") or resp.get("sessionId")
        if not session_id:
            raise RuntimeError(f"创建会话失败: {resp}")
        logger.info("创建导入会话: %s (table=%s)", session_id[:8], table)
        return session_id

    def send_batch(
        self,
        table: str,
        session_id: str,
        rows: list[dict],
        field_mappings: list[dict],
        batch_index: int,
        total_batches: int,
    ) -> dict:
        """发送一批数据到 staging。"""
        payload = {
            "rows": rows,
            "fieldMappings": field_mappings,
            "batchIndex": batch_index,
            "totalBatches": total_batches,
            "sessionId": session_id,
            "duplicateStrategy": "skip",
            "skipUnmatchedFK": True,
        }
        return self._request("POST", f"/api/import/{table}/batch", payload)

    def confirm_batch(self, table: str, session_id: str, batch_index: int = 0) -> dict:
        """确认导入批次，将 staging 数据写入目标表。"""
        return self._request("POST", f"/api/import/{table}/confirm-batch", {
            "sessionId": session_id,
            "batchIndex": batch_index,
        })

    def cancel_import(self, table: str, session_id: str) -> dict:
        """取消导入。"""
        return self._request("POST", f"/api/import/{table}/cancel", {"sessionId": session_id})
