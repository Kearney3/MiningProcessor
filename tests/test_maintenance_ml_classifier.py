"""维修 ML 二级分类器测试。"""
from datetime import date
import json

import pandas as pd

from func.maintenance_ml_classifier import (
    DEFAULT_MODEL_PATH,
    MaintenanceMLClassifier,
    MaintenanceMLConfig,
    MaintenanceMLPrediction,
    encode_label,
)


def _training_data():
    texts = []
    labels = []
    for index in range(24):
        texts.append(f"发动机喷油器故障需要更换 {index}")
        labels.append(encode_label("发动机系统", "燃油供给与喷射"))
        texts.append(f"变速箱换挡异常无法挂挡 {index}")
        labels.append(encode_label("变速箱与变矩器", "换挡/离合器"))
    return texts, labels


def test_fit_predict_and_round_trip(tmp_path):
    texts, labels = _training_data()
    config = MaintenanceMLConfig(
        min_samples_per_class=5,
        min_confidence=0.5,
        min_margin=0.05,
        max_features=5000,
    )
    model = MaintenanceMLClassifier(config)
    metrics = model.fit(texts, labels)
    assert metrics["classes"] == 2
    assert metrics["accepted_accuracy"] >= 0.9

    prediction = model.predict_many(["喷油器损坏发动机无法工作"])[0]
    assert prediction is not None
    assert prediction.major == "发动机系统"
    assert prediction.minor == "燃油供给与喷射"

    path = model.save(tmp_path / "model.joblib")
    loaded = MaintenanceMLClassifier.load(path)
    assert loaded.predict_many(["变速箱不能换挡"])[0].minor == "换挡/离合器"


def test_default_trained_model_is_present_and_loadable():
    assert DEFAULT_MODEL_PATH.is_file()
    model = MaintenanceMLClassifier.load()
    assert model.is_fitted
    assert model.metrics["training_samples"] >= 40_000
    assert model.metrics["classes"] >= 80
    assert model.metrics["accepted_accuracy"] >= 0.95
    assert model.metrics["schema_version"] == 2


def test_process_uses_ml_only_for_pending_fault(monkeypatch, tmp_path):
    from func import excel_maintenance

    class FakeClassifier:
        def predict_many(self, texts):
            return [
                MaintenanceMLPrediction(
                    major="驾驶室与车身",
                    minor="座椅/操纵踏板",
                    confidence=0.91,
                    margin=0.52,
                )
                for _ in texts
            ]

    source = tmp_path / "input.xlsx"
    source.touch()
    records = [
        {
            "日期": date(2026, 7, 1),
            "原始设备名称": "TR001",
            "原因": "检修",
            "班次": "白班",
            "维修内容": "驾驶室异响",
            "工时_分钟": 30,
        }
    ]
    monkeypatch.setattr(
        excel_maintenance,
        "extract_all_records",
        lambda *args, **kwargs: records,
    )
    sheets = excel_maintenance.process_maintenance_data(
        str(source),
        return_sheets=True,
        details_only=True,
        ml_classifier=FakeClassifier(),
    )
    row = sheets["维修明细"].iloc[0]
    assert row["大类"] == "驾驶室与车身"
    assert row["分类方式"] == "ML辅助"
    assert row["分类置信度"] == 0.91


def test_llm_supervision_consolidates_conflicts(tmp_path):
    from func.train_maintenance_classifier import load_llm_supervision

    df = pd.DataFrame(
        {
            "维修内容": [
                "轮胎破损待更换",
                "轮胎破损待更换",
                "轮胎破损待更换",
                "发动机漏水",
            ]
        }
    )
    checkpoint = tmp_path / "labels.jsonl"
    rows = [
        {
            "record_id": "row-0",
            "major": "轮胎与车轮",
            "minor": "轮胎损伤/磨损",
            "confidence": 0.95,
            "reason": "",
        },
        {
            "record_id": "row-1",
            "major": "轮胎与车轮",
            "minor": "轮胎损伤/磨损",
            "confidence": 0.9,
            "reason": "",
        },
        {
            "record_id": "row-2",
            "major": "轮胎与车轮",
            "minor": "拆装/换位/更换",
            "confidence": 0.5,
            "reason": "",
        },
        {
            "record_id": "row-3",
            "major": "发动机系统",
            "minor": "冷却系统",
            "confidence": 0.95,
            "reason": "",
        },
    ]
    checkpoint.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    labels, metrics = load_llm_supervision(
        df,
        checkpoint,
        min_confidence=0.9,
        min_agreement=0.75,
    )
    assert labels["轮胎破损待更换"] == ("轮胎与车轮", "轮胎损伤/磨损")
    assert labels["发动机漏水"] == ("发动机系统", "冷却系统")
    assert metrics["llm_conflicting_contents"] == 1


def test_llm_supervision_supports_stable_ids_and_collapses_retries(tmp_path):
    from func.train_maintenance_classifier import load_llm_supervision

    df = pd.DataFrame(
        {
            "原始记录ID": ["maint-100", "maint-200"],
            "维修内容": ["发动机等待配件", "发动机等待配件"],
        }
    )
    checkpoint = tmp_path / "labels.jsonl"
    rows = [
        {
            "record_id": "maint-100",
            "major": "发动机系统",
            "minor": "发动机总成/大修",
            "confidence": 0.95,
        },
        {
            "record_id": "maint-100",
            "major": "发动机系统",
            "minor": "发动机总成/大修",
            "confidence": 0.9,
        },
        {
            "record_id": "maint-100",
            "major": "低压电气与控制",
            "minor": "启动机/启动回路",
            "confidence": 0.6,
        },
        {
            "record_id": "maint-200",
            "major": "发动机系统",
            "minor": "发动机总成/大修",
            "confidence": 0.95,
        },
    ]
    checkpoint.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    labels, metrics = load_llm_supervision(
        df,
        checkpoint,
        record_id_column="原始记录ID",
        min_confidence=0.9,
        min_agreement=0.75,
    )

    assert labels["发动机等待配件"] == (
        "发动机系统",
        "发动机总成/大修",
    )
    assert metrics["llm_checkpoint_labels"] == 4
    assert metrics["llm_checkpoint_unique_records"] == 2
    assert metrics["llm_checkpoint_duplicate_labels"] == 2
    assert metrics["llm_record_conflicts"] == 1
