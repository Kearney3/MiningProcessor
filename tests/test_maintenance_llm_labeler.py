"""维修记录大模型标注脚本测试。"""
import json
import os

import pandas as pd
import pytest

from func.label_maintenance_with_llm import (
    LLMLabel,
    BatchResult,
    MAX_BATCH_SIZE,
    OpenAICompatibleLabelClient,
    build_system_prompt,
    extract_response_content,
    get_allowed_taxonomy,
    label_file,
    parse_and_validate_labels,
    _normalize_url,
    _load_local_env,
    _build_records,
    _auto_correct_classification,
    _resolve_minor,
)


def test_load_local_env_includes_model_without_overriding_existing(
    tmp_path, monkeypatch
):
    env_file = tmp_path / ".maintenance_llm.env"
    env_file.write_text(
        "\n".join(
            [
                "MAINTENANCE_LLM_URL='https://example.com/v1'",
                'MAINTENANCE_LLM_API_KEY="secret-key"',
                "MAINTENANCE_LLM_MODEL=mimo-v2.5-pro",
                "UNSUPPORTED_KEY=ignored",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MAINTENANCE_LLM_URL", "https://existing.example/v1")
    monkeypatch.delenv("MAINTENANCE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("MAINTENANCE_LLM_MODEL", raising=False)

    _load_local_env(env_file)

    assert os.environ["MAINTENANCE_LLM_URL"] == "https://existing.example/v1"
    assert os.environ["MAINTENANCE_LLM_API_KEY"] == "secret-key"
    assert os.environ["MAINTENANCE_LLM_MODEL"] == "mimo-v2.5-pro"
    assert "UNSUPPORTED_KEY" not in os.environ


def test_system_prompt_covers_open_pit_and_waiting_parts_boundaries():
    prompt = build_system_prompt(get_allowed_taxonomy())

    assert "露天矿山工程机械" in prompt
    assert "重点检查是否为发动机配件" in prompt
    assert "不得把所有“等配件”都默认判为发动机" in prompt
    assert "等待轮马达配件" in prompt
    assert "主发/主发电机" in prompt


def test_parse_and_validate_strict_taxonomy():
    taxonomy = get_allowed_taxonomy()
    content = json.dumps(
        {
            "items": [
                {
                    "id": "row-1",
                    "major": "电驱动系统",
                    "minor": "逆变/功率模块",
                    "confidence": 0.96,
                    "reason": "IGBT报警",
                }
            ]
        },
        ensure_ascii=False,
    )
    labels, skipped = parse_and_validate_labels(content, ["row-1"], taxonomy)
    assert labels[0].minor == "逆变/功率模块"
    assert labels[0].confidence == 0.96
    assert skipped == []

    invalid = content.replace("逆变/功率模块", "模型自创小类")
    labels, skipped = parse_and_validate_labels(invalid, ["row-1"], taxonomy)
    assert labels == []
    assert skipped == ["row-1"]


def test_extract_chat_completion_and_code_fence():
    response = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"items":[]}\n```',
                }
            }
        ]
    }
    assert extract_response_content(response).startswith("```json")
    labels, skipped = parse_and_validate_labels(
        extract_response_content(response),
        [],
        get_allowed_taxonomy(),
    )
    assert labels == []
    assert skipped == []


def test_client_rejects_more_than_50_without_request():
    client = OpenAICompatibleLabelClient(
        url="https://example.invalid/v1/chat/completions",
        api_key="secret",
        model="test-model",
    )
    records = [{"id": f"row-{index}", "content": "x"} for index in range(51)]
    with pytest.raises(ValueError, match="1—50"):
        client.label_batch(
            records,
            taxonomy=get_allowed_taxonomy(),
            system_prompt="test",
        )


def test_label_file_batches_50_and_resumes(tmp_path):
    class FakeClient:
        def __init__(self):
            self.batch_sizes = []

        def label_batch(self, records, **kwargs):
            self.batch_sizes.append(len(records))
            return BatchResult(
                labels=[
                    LLMLabel(
                        record_id=record["id"],
                        major="发动机系统",
                        minor="性能/工况异常",
                        confidence=0.9,
                        reason="测试",
                    )
                    for record in records
                ],
                skipped_ids=[],
            )

    source = tmp_path / "input.xlsx"
    output = tmp_path / "output.xlsx"
    checkpoint = tmp_path / "checkpoint.jsonl"
    pd.DataFrame(
        {
            "大类": ["其他/待确认"] * 120,
            "维修内容": [f"待分类维修内容 {index}" for index in range(120)],
        }
    ).to_excel(source, index=False, sheet_name="维修明细")

    client = FakeClient()
    result = label_file(
        str(source),
        output_path=str(output),
        client=client,
        checkpoint_path=str(checkpoint),
        batch_size=MAX_BATCH_SIZE,
    )
    assert client.batch_sizes == [50, 50, 20]
    assert result["completed_rows"] == 120
    labeled = pd.read_excel(output)
    assert set(labeled["LLM标注状态"]) == {"已完成"}

    resumed_client = FakeClient()
    label_file(
        str(source),
        output_path=str(output),
        client=resumed_client,
        checkpoint_path=str(checkpoint),
        batch_size=MAX_BATCH_SIZE,
    )
    assert resumed_client.batch_sizes == []


def test_only_pending_filter_when_category_exists(tmp_path):
    class FakeClient:
        def label_batch(self, records, **kwargs):
            return BatchResult(
                labels=[
                    LLMLabel(
                        record_id=record["id"],
                        major="液压系统",
                        minor="压力/功能异常",
                        confidence=0.88,
                        reason="测试",
                    )
                    for record in records
                ],
                skipped_ids=[],
            )

    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"
    pd.DataFrame(
        {
            "大类": ["其他/待确认", "发动机系统"],
            "维修内容": ["液压动作异常", "发动机报警"],
        }
    ).to_csv(source, index=False)
    result = label_file(
        str(source),
        output_path=str(output),
        client=FakeClient(),
    )
    assert result["candidate_rows"] == 1
    labeled = pd.read_csv(output)
    assert labeled.loc[0, "LLM标注状态"] == "已完成"
    assert pd.isna(labeled.loc[1, "LLM标注状态"])


def test_label_file_uses_stable_record_id_column(tmp_path):
    class FakeClient:
        def __init__(self):
            self.ids = []

        def label_batch(self, records, **kwargs):
            self.ids.extend(record["id"] for record in records)
            return BatchResult(
                labels=[
                    LLMLabel(
                        record_id=record["id"],
                        major="液压系统",
                        minor="压力/功能异常",
                        confidence=0.91,
                        reason="测试",
                    )
                    for record in records
                ],
                skipped_ids=[],
            )

    source = tmp_path / "pending.csv"
    checkpoint = tmp_path / "pending.checkpoint.jsonl"
    pd.DataFrame(
        {
            "原始记录ID": ["row-17", "row-204"],
            "新版大类": ["其他/待确认", "其他/待确认"],
            "维修内容": ["液压动作慢", "液压无压力"],
        }
    ).to_csv(source, index=False)
    client = FakeClient()
    result = label_file(
        str(source),
        output_path=str(tmp_path / "labeled.csv"),
        client=client,
        category_column="新版大类",
        record_id_column="原始记录ID",
        checkpoint_path=str(checkpoint),
    )
    assert client.ids == ["row-17", "row-204"]
    assert result["completed_rows"] == 2
    checkpoint_ids = {
        json.loads(line)["record_id"]
        for line in checkpoint.read_text(encoding="utf-8").splitlines()
    }
    assert checkpoint_ids == {"row-17", "row-204"}


def test_only_pending_requires_category_column(tmp_path):
    class FakeClient:
        def label_batch(self, records, **kwargs):
            raise AssertionError("不应调用接口")

    source = tmp_path / "input.csv"
    pd.DataFrame({"维修内容": ["待分类内容"]}).to_csv(source, index=False)
    with pytest.raises(ValueError, match="必须存在列"):
        label_file(
            str(source),
            output_path=str(tmp_path / "output.csv"),
            client=FakeClient(),
        )


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("https://api.example.com/v1", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/v1/", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/v1/chat/completions", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/v1/chat/completions/", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com", "https://api.example.com/v1/chat/completions"),
    ],
)
def test_normalize_url(input_url, expected):
    assert _normalize_url(input_url) == expected


def test_client_init_normalizes_url():
    client = OpenAICompatibleLabelClient(
        url="https://api.example.com/v1",
        api_key="test-key",
        model="test-model",
    )
    assert client.url == "https://api.example.com/v1/chat/completions"


def test_label_file_concurrent_execution(tmp_path):
    """并发执行时所有批次都被处理，checkpoint 完整。"""
    import threading

    call_count = 0
    call_lock = threading.Lock()

    class FakeClient:
        def label_batch(self, records, **kwargs):
            nonlocal call_count
            with call_lock:
                call_count += 1
            return BatchResult(
                labels=[
                    LLMLabel(
                        record_id=r["id"],
                        major="发动机系统",
                        minor="发动机报警",
                        confidence=0.9,
                        reason="test",
                    )
                    for r in records
                ],
                skipped_ids=[],
            )

    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"
    rows = {"大类": ["其他/待确认"] * 120, "维修内容": [f"内容{i}" for i in range(120)]}
    pd.DataFrame(rows).to_csv(source, index=False)
    result = label_file(
        str(source),
        output_path=str(output),
        client=FakeClient(),
        batch_size=10,
        concurrency=4,
    )
    assert result["completed_rows"] == 120
    assert call_count == 12


def test_label_file_concurrency_must_be_positive(tmp_path):
    source = tmp_path / "input.csv"
    pd.DataFrame({"大类": ["其他/待确认"], "维修内容": ["内容"]}).to_csv(
        source, index=False
    )
    with pytest.raises(ValueError, match="concurrency"):
        label_file(
            str(source),
            output_path=str(tmp_path / "out.csv"),
            client=type("C", (), {"label_batch": lambda *a, **k: []})(),
            concurrency=0,
        )


def test_build_records_basic():
    import pandas as pd

    df = pd.DataFrame({"维修内容": ["漏油", "报警"], "设备编号": ["D1", "D2"]})
    records = _build_records(df, [0, 1], "维修内容", ["设备编号"], 100)
    assert len(records) == 2
    assert records[0]["id"] == "row-0"
    assert records[0]["content"] == "漏油"
    assert records[0]["context"]["设备编号"] == "D1"


def test_label_file_partial_resume_after_interruption(tmp_path):
    """模拟中断后续跑：第一批成功、第二批失败，第二次只补跑剩余。"""

    class FailAfterOneClient:
        def __init__(self):
            self.call_count = 0

        def label_batch(self, records, **kwargs):
            self.call_count += 1
            if self.call_count > 1:
                raise RuntimeError("模拟网络中断")
            return BatchResult(
                labels=[
                    LLMLabel(
                        record_id=r["id"],
                        major="发动机系统",
                        minor="发动机报警",
                        confidence=0.9,
                        reason="test",
                    )
                    for r in records
                ],
                skipped_ids=[],
            )

    source = tmp_path / "input.csv"
    output = tmp_path / "output.csv"
    checkpoint = tmp_path / "checkpoint.jsonl"
    rows = {"大类": ["其他/待确认"] * 120, "维修内容": [f"内容{i}" for i in range(120)]}
    pd.DataFrame(rows).to_csv(source, index=False)

    client1 = FailAfterOneClient()
    with pytest.raises(RuntimeError, match="批次失败"):
        label_file(
            str(source),
            output_path=str(output),
            client=client1,
            checkpoint_path=str(checkpoint),
            batch_size=50,
            concurrency=3,
        )
    assert client1.call_count == 3

    class CountingClient:
        def __init__(self):
            self.batch_sizes = []

        def label_batch(self, records, **kwargs):
            self.batch_sizes.append(len(records))
            return BatchResult(
                labels=[
                    LLMLabel(
                        record_id=r["id"],
                        major="发动机系统",
                        minor="发动机报警",
                        confidence=0.9,
                        reason="test",
                    )
                    for r in records
                ],
                skipped_ids=[],
            )

    client2 = CountingClient()
    result = label_file(
        str(source),
        output_path=str(output),
        client=client2,
        checkpoint_path=str(checkpoint),
        batch_size=50,
        concurrency=3,
    )
    assert result["completed_rows"] == 120
    assert len(client2.batch_sizes) == 2


def test_auto_correct_minor_as_major():
    taxonomy = get_allowed_taxonomy()
    # LLM 错把小类填到大类位置：排气与尾气后处理 是发动机系统下的小类
    result = _auto_correct_classification("排气与尾气后处理", "排气与尾气后处理", taxonomy)
    assert result == ("发动机系统", "排气与尾气后处理")


def test_auto_correct_invalid_major_valid_minor():
    taxonomy = get_allowed_taxonomy()
    # major 完全无效，minor 是有效小类 → 用 minor 的正确大类
    result = _auto_correct_classification("完全不存在", "排气与尾气后处理", taxonomy)
    assert result == ("发动机系统", "排气与尾气后处理")


def test_auto_correct_valid_major_wrong_minor_returns_none():
    taxonomy = get_allowed_taxonomy()
    # major 合法，minor 属于另一个大类 → 无法判断谁对，不纠正
    result = _auto_correct_classification("液压系统", "排气与尾气后处理", taxonomy)
    assert result is None


def test_auto_correct_both_invalid_returns_none():
    taxonomy = get_allowed_taxonomy()
    result = _auto_correct_classification("完全不存在的分类", "也不存在", taxonomy)
    assert result is None


def test_auto_correct_already_valid():
    taxonomy = get_allowed_taxonomy()
    result = _auto_correct_classification("发动机系统", "性能/工况异常", taxonomy)
    assert result == ("发动机系统", "性能/工况异常")


def test_auto_correct_valid_major_hallucinated_minor_returns_none():
    taxonomy = get_allowed_taxonomy()
    # major 合法，minor 是 LLM 幻觉 → 不纠正
    result = _auto_correct_classification("发动机系统", "LLM自创小类", taxonomy)
    assert result is None


def test_parse_and_validate_auto_corrects_minor_as_major():
    taxonomy = get_allowed_taxonomy()
    content = json.dumps(
        {
            "items": [
                {
                    "id": "row-1",
                    "major": "排气与尾气后处理",
                    "minor": "排气与尾气后处理",
                    "confidence": 0.85,
                    "reason": "排气管故障",
                }
            ]
        },
        ensure_ascii=False,
    )
    labels, skipped = parse_and_validate_labels(content, ["row-1"], taxonomy)
    assert labels[0].major == "发动机系统"
    assert labels[0].minor == "排气与尾气后处理"
    assert skipped == []


def test_parse_and_validate_skips_unfixable():
    """无法纠正的分类被跳过（不炸批次），下次运行自动重试。"""
    taxonomy = get_allowed_taxonomy()
    content = json.dumps(
        {
            "items": [
                {
                    "id": "row-1",
                    "major": "液压系统",
                    "minor": "排气与尾气后处理",
                    "confidence": 0.85,
                    "reason": "test",
                }
            ]
        },
        ensure_ascii=False,
    )
    labels, skipped = parse_and_validate_labels(content, ["row-1"], taxonomy)
    assert labels == []
    assert skipped == ["row-1"]


def test_resolve_minor_multi_select():
    taxonomy = get_allowed_taxonomy()
    result = _resolve_minor(
        "其他/待确认",
        "信息不足、仅现象未定位、多系统/需拆分",
        taxonomy,
    )
    assert result == "信息不足"


def test_resolve_minor_already_valid():
    taxonomy = get_allowed_taxonomy()
    result = _resolve_minor("发动机系统", "性能/工况异常", taxonomy)
    assert result == "性能/工况异常"


def test_resolve_minor_no_match_returns_original():
    taxonomy = get_allowed_taxonomy()
    result = _resolve_minor("发动机系统", "完全不存在的分类", taxonomy)
    assert result == "完全不存在的分类"


def test_parse_and_validate_resolves_multi_select_minor():
    taxonomy = get_allowed_taxonomy()
    content = json.dumps(
        {
            "items": [
                {
                    "id": "row-1",
                    "major": "其他/待确认",
                    "minor": "信息不足、仅现象未定位、多系统/需拆分",
                    "confidence": 0.6,
                    "reason": "信息不足",
                }
            ]
        },
        ensure_ascii=False,
    )
    labels, skipped = parse_and_validate_labels(content, ["row-1"], taxonomy)
    assert labels[0].major == "其他/待确认"
    assert labels[0].minor == "信息不足"
    assert skipped == []
