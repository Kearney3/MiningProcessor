"""从维修明细 Excel 训练轻量级二级分类模型。"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from func.config_loader import get_maintenance_classifications
from func.maintenance_classification import (
    classify,
    compile_noise_patterns,
    get_default_classifications,
    normalize_maintenance_content,
)
from func.maintenance_ml_classifier import (
    DEFAULT_MODEL_PATH,
    MaintenanceMLClassifier,
    MaintenanceMLConfig,
    encode_label,
)


def load_llm_supervision(
    df: pd.DataFrame,
    checkpoint_path: str | Path,
    *,
    content_column: str = "维修内容",
    record_id_column: str | None = None,
    min_confidence: float = 0.9,
    min_agreement: float = 0.75,
) -> tuple[dict[str, tuple[str, str]], dict]:
    """合并 checkpoint 中的重复标注，返回规范化文本到分类标签的映射。

    同一 record_id 出现多次时先在记录粒度做置信度加权投票，再将每条记录
    作为一票汇总到规范化维修内容，避免并发重跑让部分记录被重复加权。
    """
    taxonomy = get_default_taxonomy()
    votes: dict[str, Counter] = defaultdict(Counter)
    confidence_sum: dict[tuple[str, tuple[str, str]], float] = defaultdict(float)
    label_count: dict[tuple[str, tuple[str, str]], int] = defaultdict(int)
    record_votes: dict[str, Counter] = defaultdict(Counter)
    record_confidence_sum: dict[
        tuple[str, tuple[str, str]], float
    ] = defaultdict(float)
    record_label_count: dict[
        tuple[str, tuple[str, str]], int
    ] = defaultdict(int)
    record_contents: dict[str, str] = {}
    raw_labels = 0
    valid_record_labels = 0
    invalid_labels = 0
    missing_rows = 0

    if record_id_column:
        if record_id_column not in df.columns:
            raise ValueError(f"LLM 标注输入缺少记录 ID 列: {record_id_column}")
        ids = df[record_id_column].fillna("").astype(str)
        if ids.eq("").any() or ids.duplicated().any():
            raise ValueError(f"记录 ID 列“{record_id_column}”必须非空且唯一")
        row_lookup = dict(zip(ids, df.index))
    else:
        row_lookup = None

    with Path(checkpoint_path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw_labels += 1
            item = json.loads(line)
            record_id = str(item.get("record_id", ""))
            try:
                if row_lookup is not None:
                    row_index = row_lookup[record_id]
                else:
                    row_index = int(record_id.split("-", 1)[1])
                content = df.at[row_index, content_column]
            except (KeyError, ValueError, TypeError, IndexError):
                missing_rows += 1
                continue
            major = str(item.get("major", "")).strip()
            minor = str(item.get("minor", "")).strip()
            if major not in taxonomy or minor not in taxonomy[major]:
                invalid_labels += 1
                continue
            if major in {"其他/待确认", "计划保养与非故障作业"}:
                continue
            normalized = normalize_maintenance_content(
                "" if pd.isna(content) else str(content)
            )
            if not normalized:
                continue
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence", 0))))
            except (TypeError, ValueError):
                confidence = 0.0
            label = (major, minor)
            valid_record_labels += 1
            record_contents[record_id] = normalized
            record_votes[record_id][label] += confidence
            record_confidence_sum[(record_id, label)] += confidence
            record_label_count[(record_id, label)] += 1

    record_conflicts = 0
    for record_id, label_votes in record_votes.items():
        if len(label_votes) > 1:
            record_conflicts += 1
        winner, winner_weight = label_votes.most_common(1)[0]
        total_weight = sum(label_votes.values())
        record_agreement = winner_weight / total_weight if total_weight else 0.0
        average_confidence = (
            record_confidence_sum[(record_id, winner)]
            / record_label_count[(record_id, winner)]
        )
        normalized = record_contents[record_id]
        vote_weight = record_agreement * average_confidence
        votes[normalized][winner] += vote_weight
        confidence_sum[(normalized, winner)] += average_confidence
        label_count[(normalized, winner)] += 1

    accepted: dict[str, tuple[str, str]] = {}
    conflicts = 0
    low_quality = 0
    for normalized, label_votes in votes.items():
        if len(label_votes) > 1:
            conflicts += 1
        winner, winner_weight = label_votes.most_common(1)[0]
        total_weight = sum(label_votes.values())
        agreement = winner_weight / total_weight if total_weight else 0.0
        average_confidence = (
            confidence_sum[(normalized, winner)]
            / label_count[(normalized, winner)]
        )
        if (
            average_confidence < min_confidence
            or agreement < min_agreement
        ):
            low_quality += 1
            continue
        accepted[normalized] = winner

    return accepted, {
        "llm_checkpoint_labels": raw_labels,
        "llm_checkpoint_unique_records": len(record_votes),
        "llm_checkpoint_duplicate_labels": (
            valid_record_labels - len(record_votes)
        ),
        "llm_record_conflicts": record_conflicts,
        "llm_unique_contents": len(votes),
        "llm_conflicting_contents": conflicts,
        "llm_low_quality_contents": low_quality,
        "llm_accepted_contents": len(accepted),
        "llm_invalid_labels": invalid_labels,
        "llm_missing_rows": missing_rows,
        "llm_min_confidence": min_confidence,
        "llm_min_agreement": min_agreement,
    }


def get_default_taxonomy() -> dict[str, set[str]]:
    taxonomy: dict[str, set[str]] = defaultdict(set)
    for entry in get_default_classifications()["classifications"]:
        taxonomy[entry["major"]].add(entry["minor"])
    taxonomy["其他/待确认"].update(
        {"信息不足", "仅现象未定位", "多系统/需拆分"}
    )
    return dict(taxonomy)


def train_from_excel(
    input_path: str,
    *,
    output_path: str | Path = DEFAULT_MODEL_PATH,
    sheet_name: str = "维修明细",
    content_column: str = "维修内容",
    config: MaintenanceMLConfig | None = None,
    llm_checkpoint: str | Path | None = None,
    llm_input_path: str | Path | None = None,
    llm_record_id_column: str | None = None,
    llm_min_confidence: float = 0.9,
    llm_min_agreement: float = 0.75,
) -> tuple[Path, dict]:
    df = pd.read_excel(input_path, sheet_name=sheet_name)
    if content_column not in df.columns:
        raise ValueError(f"缺少维修内容列: {content_column}")

    rules = get_maintenance_classifications()
    compiled_noise = compile_noise_patterns(rules["noise_patterns"])
    training: dict[str, tuple[str, str]] = {}
    unique_contents = df[content_column].fillna("").astype(str).drop_duplicates()
    for content in unique_contents:
        major, minor = classify(
            content,
            classifications=rules["classifications"],
            noise_exact=rules["noise_exact"],
            compiled_noise=compiled_noise,
        )
        if (
            major
            and minor
            and major not in {"其他/待确认", "计划保养与非故障作业"}
        ):
            training[normalize_maintenance_content(content)] = (
                content,
                encode_label(major, minor),
            )

    rule_training_contents = len(training)
    llm_metrics = {
        "llm_checkpoint_labels": 0,
        "llm_accepted_contents": 0,
        "llm_added_contents": 0,
        "llm_rule_conflicts": 0,
    }
    if llm_checkpoint:
        llm_df = df
        if llm_input_path:
            llm_source = Path(llm_input_path)
            if llm_source.suffix.lower() == ".csv":
                llm_df = pd.read_csv(llm_source)
            else:
                llm_df = pd.read_excel(
                    llm_source,
                    sheet_name=sheet_name,
                )
        llm_labels, llm_metrics = load_llm_supervision(
            llm_df,
            llm_checkpoint,
            content_column=content_column,
            record_id_column=llm_record_id_column,
            min_confidence=llm_min_confidence,
            min_agreement=llm_min_agreement,
        )
        added = 0
        rule_conflicts = 0
        for normalized, (major, minor) in llm_labels.items():
            label = encode_label(major, minor)
            existing = training.get(normalized)
            if existing is not None:
                if existing[1] != label:
                    rule_conflicts += 1
                continue
            training[normalized] = (normalized, label)
            added += 1
        llm_metrics["llm_added_contents"] = added
        llm_metrics["llm_rule_conflicts"] = rule_conflicts

    texts = [value[0] for value in training.values()]
    labels = [value[1] for value in training.values()]

    if len(Counter(labels)) < 2:
        raise ValueError("规则标注得到的有效分类不足，无法训练")
    model = MaintenanceMLClassifier(config)
    metrics = model.fit(texts, labels)
    metrics.update(
        {
            "rule_training_contents": rule_training_contents,
            **llm_metrics,
        }
    )
    model.metrics = dict(metrics)
    target = model.save(output_path)
    metadata_path = target.with_suffix(".metrics.json")
    metadata_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="训练维修记录轻量级分类模型")
    parser.add_argument("input_path", help="包含维修明细 sheet 的 Excel 文件")
    parser.add_argument("--output", default=str(DEFAULT_MODEL_PATH), help="模型输出路径")
    parser.add_argument("--sheet", default="维修明细", help="维修明细 sheet 名称")
    parser.add_argument("--content-column", default="维修内容", help="维修内容列名")
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument("--min-margin", type=float, default=0.3)
    parser.add_argument("--llm-checkpoint", help="LLM 标注 checkpoint JSONL")
    parser.add_argument(
        "--llm-input",
        help="checkpoint 对应的 Excel/CSV；为空时使用训练输入文件",
    )
    parser.add_argument(
        "--llm-record-id-column",
        help="LLM 标注输入中的稳定记录 ID 列",
    )
    parser.add_argument("--llm-min-confidence", type=float, default=0.9)
    parser.add_argument("--llm-min-agreement", type=float, default=0.75)
    args = parser.parse_args()
    config = MaintenanceMLConfig(
        min_confidence=args.min_confidence,
        min_margin=args.min_margin,
    )
    path, metrics = train_from_excel(
        args.input_path,
        output_path=args.output,
        sheet_name=args.sheet,
        content_column=args.content_column,
        config=config,
        llm_checkpoint=args.llm_checkpoint,
        llm_input_path=args.llm_input,
        llm_record_id_column=args.llm_record_id_column,
        llm_min_confidence=args.llm_min_confidence,
        llm_min_agreement=args.llm_min_agreement,
    )
    print(json.dumps({"model": str(path), **metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
