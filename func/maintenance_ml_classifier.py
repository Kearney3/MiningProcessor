"""维修文本轻量级机器学习分类器。

用于规则分类后的二级兜底，不替代确定性规则。模型采用字符级 TF-IDF 与
SGD 对数损失线性分类器，适合中文短文本、拼写变体和中英文混合维修描述。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import normalize

from func.maintenance_classification import (
    MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION,
    normalize_maintenance_content,
)


MODEL_VERSION = 3
LABEL_SEPARATOR = "\u241f"
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "models" / "maintenance_classifier.joblib"
)


@dataclass(frozen=True)
class MaintenanceMLConfig:
    """训练和安全回填阈值。"""

    min_samples_per_class: int = 20
    max_samples_per_class: int = 3000
    max_features: int = 30000
    min_confidence: float = 0.65
    min_margin: float = 0.15
    min_text_length: int = 6
    min_centroid_similarity: float = 0.12
    validation_size: float = 0.2
    random_state: int = 42


@dataclass(frozen=True)
class MaintenanceMLPrediction:
    major: str
    minor: str
    confidence: float
    margin: float


def encode_label(major: str, minor: str) -> str:
    return f"{major}{LABEL_SEPARATOR}{minor}"


def decode_label(label: str) -> tuple[str, str]:
    major, minor = label.split(LABEL_SEPARATOR, 1)
    return major, minor


class MaintenanceMLClassifier:
    """可训练、保存和加载的维修文本分类器。"""

    def __init__(self, config: MaintenanceMLConfig | None = None):
        self.config = config or MaintenanceMLConfig()
        self.vectorizer: TfidfVectorizer | None = None
        self.major_classifier: SGDClassifier | None = None
        self.minor_classifiers: dict[str, SGDClassifier | str] = {}
        self.centroid_labels: np.ndarray | None = None
        self.centroids = None
        self.metrics: dict = {}

    @property
    def is_fitted(self) -> bool:
        return (
            self.vectorizer is not None
            and self.major_classifier is not None
            and self.centroids is not None
        )

    def _balanced_sample(
        self,
        texts: Sequence[str],
        labels: Sequence[str],
    ) -> tuple[list[str], list[str]]:
        counts = Counter(labels)
        allowed = {
            label
            for label, count in counts.items()
            if count >= self.config.min_samples_per_class
        }
        buckets: dict[str, list[str]] = defaultdict(list)
        for text, label in zip(texts, labels):
            if label in allowed:
                normalized = normalize_maintenance_content(text)
                if normalized:
                    buckets[label].append(normalized)

        rng = np.random.default_rng(self.config.random_state)
        sampled_texts: list[str] = []
        sampled_labels: list[str] = []
        for label in sorted(buckets):
            values = list(dict.fromkeys(buckets[label]))
            if len(values) > self.config.max_samples_per_class:
                indexes = rng.choice(
                    len(values),
                    self.config.max_samples_per_class,
                    replace=False,
                )
                values = [values[index] for index in sorted(indexes)]
            sampled_texts.extend(values)
            sampled_labels.extend([label] * len(values))
        return sampled_texts, sampled_labels

    def _new_vectorizer(self) -> TfidfVectorizer:
        return TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 5),
            min_df=2,
            max_features=self.config.max_features,
            sublinear_tf=True,
            dtype=np.float32,
        )

    def _new_classifier(self) -> SGDClassifier:
        return SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-5,
            max_iter=1500,
            tol=1e-3,
            class_weight="balanced",
            average=True,
            random_state=self.config.random_state,
        )

    def _fit_hierarchy(self, matrix, labels: Sequence[str]):
        majors = np.asarray([decode_label(label)[0] for label in labels])
        minors = np.asarray([decode_label(label)[1] for label in labels])
        major_classifier = self._new_classifier()
        major_classifier.fit(matrix, majors)
        minor_classifiers: dict[str, SGDClassifier | str] = {}
        for major in sorted(set(majors)):
            indexes = np.flatnonzero(majors == major)
            minor_values = minors[indexes]
            unique_minors = sorted(set(minor_values))
            if len(unique_minors) == 1:
                minor_classifiers[major] = unique_minors[0]
                continue
            classifier = self._new_classifier()
            classifier.fit(matrix[indexes], minor_values)
            minor_classifiers[major] = classifier
        return major_classifier, minor_classifiers

    @staticmethod
    def _top_probability(probabilities: np.ndarray, classes: np.ndarray):
        order = np.argsort(probabilities, axis=1)
        indexes = order[:, -1]
        rows = np.arange(len(probabilities))
        confidence = probabilities[rows, indexes]
        if probabilities.shape[1] == 1:
            margin = confidence.copy()
        else:
            margin = confidence - probabilities[rows, order[:, -2]]
        return classes[indexes], confidence, margin

    def _predict_hierarchy(
        self,
        matrix,
        major_classifier: SGDClassifier,
        minor_classifiers: dict[str, SGDClassifier | str],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        major_probabilities = major_classifier.predict_proba(matrix)
        majors, major_confidence, major_margin = self._top_probability(
            major_probabilities,
            major_classifier.classes_,
        )
        labels = np.empty(len(majors), dtype=object)
        confidence = major_confidence.astype(float, copy=True)
        margin = major_margin.astype(float, copy=True)
        for major in sorted(set(majors)):
            indexes = np.flatnonzero(majors == major)
            minor_model = minor_classifiers[str(major)]
            if isinstance(minor_model, str):
                labels[indexes] = encode_label(str(major), minor_model)
                continue
            minor_probabilities = minor_model.predict_proba(matrix[indexes])
            minors, minor_confidence, minor_margin = self._top_probability(
                minor_probabilities,
                minor_model.classes_,
            )
            confidence[indexes] = np.minimum(
                confidence[indexes],
                minor_confidence,
            )
            margin[indexes] = np.minimum(margin[indexes], minor_margin)
            labels[indexes] = [
                encode_label(str(major), str(minor))
                for minor in minors
            ]
        return labels, confidence, margin

    @staticmethod
    def _build_centroids(matrix, labels: Sequence[str]):
        label_array = np.asarray(labels)
        centroid_labels = np.asarray(sorted(set(labels)))
        rows = []
        for label in centroid_labels:
            indexes = np.flatnonzero(label_array == label)
            rows.append(sparse.csr_matrix(matrix[indexes].mean(axis=0)))
        centroids = normalize(
            sparse.vstack(rows).tocsr().astype(np.float32),
            norm="l2",
        )
        return centroid_labels, centroids

    @staticmethod
    def _centroid_gate(matrix, predicted_labels, centroid_labels, centroids):
        similarities = (matrix @ centroids.T).toarray()
        indexes = np.argmax(similarities, axis=1)
        nearest_labels = centroid_labels[indexes]
        rows = np.arange(len(indexes))
        nearest_similarity = similarities[rows, indexes]
        return nearest_labels == predicted_labels, nearest_similarity

    def fit(
        self,
        texts: Sequence[str],
        labels: Sequence[str],
    ) -> dict:
        """训练模型并返回留出集一致性指标。"""
        sampled_texts, sampled_labels = self._balanced_sample(texts, labels)
        class_counts = Counter(sampled_labels)
        if len(class_counts) < 2:
            raise ValueError("可训练分类少于 2 个，请增加已分类维修样本")

        train_x, valid_x, train_y, valid_y = train_test_split(
            sampled_texts,
            sampled_labels,
            test_size=self.config.validation_size,
            random_state=self.config.random_state,
            stratify=sampled_labels,
        )
        validation_vectorizer = self._new_vectorizer()
        train_matrix = validation_vectorizer.fit_transform(train_x)
        validation_major, validation_minors = self._fit_hierarchy(
            train_matrix,
            train_y,
        )
        predictions, confidence, margin = self._predict_hierarchy(
            validation_vectorizer.transform(valid_x),
            validation_major,
            validation_minors,
        )
        validation_matrix = validation_vectorizer.transform(valid_x)
        validation_centroid_labels, validation_centroids = self._build_centroids(
            train_matrix,
            train_y,
        )
        centroid_agreement, centroid_similarity = self._centroid_gate(
            validation_matrix,
            predictions,
            validation_centroid_labels,
            validation_centroids,
        )
        accepted = (
            (confidence >= self.config.min_confidence)
            & (margin >= self.config.min_margin)
            & np.asarray(
                [
                    len(normalize_maintenance_content(text))
                    >= self.config.min_text_length
                    and "正常" not in normalize_maintenance_content(text)
                    for text in valid_x
                ]
            )
            & centroid_agreement
            & (centroid_similarity >= self.config.min_centroid_similarity)
        )
        selective_accuracy = (
            accuracy_score(np.asarray(valid_y)[accepted], predictions[accepted])
            if accepted.any()
            else 0.0
        )

        self.vectorizer = self._new_vectorizer()
        full_matrix = self.vectorizer.fit_transform(sampled_texts)
        self.major_classifier, self.minor_classifiers = self._fit_hierarchy(
            full_matrix,
            sampled_labels,
        )
        self.centroid_labels, self.centroids = self._build_centroids(
            full_matrix,
            sampled_labels,
        )
        self.metrics = {
            "model_version": MODEL_VERSION,
            "schema_version": MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION,
            "training_samples": len(sampled_texts),
            "classes": len(class_counts),
            "validation_samples": len(valid_y),
            "validation_accuracy": float(accuracy_score(valid_y, predictions)),
            "validation_macro_f1": float(
                f1_score(valid_y, predictions, average="macro", zero_division=0)
            ),
            "accepted_coverage": float(accepted.mean()),
            "accepted_accuracy": float(selective_accuracy),
            "class_counts": dict(sorted(class_counts.items())),
        }
        return dict(self.metrics)

    def predict_many(
        self,
        texts: Iterable[str],
    ) -> list[MaintenanceMLPrediction | None]:
        """批量预测；未通过置信度与间隔阈值时返回 None。"""
        if not self.is_fitted:
            raise RuntimeError("维修分类模型尚未训练")
        values = [normalize_maintenance_content(text) for text in texts]
        matrix = self.vectorizer.transform(values)
        labels, confidence_values, margin_values = self._predict_hierarchy(
            matrix,
            self.major_classifier,
            self.minor_classifiers,
        )
        centroid_agreement, centroid_similarity = self._centroid_gate(
            matrix,
            labels,
            self.centroid_labels,
            self.centroids,
        )
        results: list[MaintenanceMLPrediction | None] = []
        for text, label, confidence, margin, agrees, similarity in zip(
            values,
            labels,
            confidence_values,
            margin_values,
            centroid_agreement,
            centroid_similarity,
        ):
            if (
                len(text) < self.config.min_text_length
                or "正常" in text
                or confidence < self.config.min_confidence
                or margin < self.config.min_margin
                or not agrees
                or similarity < self.config.min_centroid_similarity
            ):
                results.append(None)
                continue
            major, minor = decode_label(str(label))
            results.append(
                MaintenanceMLPrediction(
                    major=major,
                    minor=minor,
                    confidence=confidence,
                    margin=margin,
                )
            )
        return results

    def save(self, path: str | Path = DEFAULT_MODEL_PATH) -> Path:
        if not self.is_fitted:
            raise RuntimeError("维修分类模型尚未训练")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model_version": MODEL_VERSION,
                "schema_version": MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION,
                "config": asdict(self.config),
                "vectorizer": self.vectorizer,
                "major_classifier": self.major_classifier,
                "minor_classifiers": self.minor_classifiers,
                "centroid_labels": self.centroid_labels,
                "centroids": self.centroids,
                "metrics": self.metrics,
            },
            target,
            compress=3,
        )
        return target

    @classmethod
    def load(
        cls,
        path: str | Path = DEFAULT_MODEL_PATH,
    ) -> "MaintenanceMLClassifier":
        payload = joblib.load(Path(path))
        if payload.get("model_version") != MODEL_VERSION:
            raise ValueError("维修分类模型版本不兼容，请重新训练")
        if (
            payload.get("schema_version")
            != MAINTENANCE_CLASSIFICATION_SCHEMA_VERSION
        ):
            raise ValueError("维修分类体系已更新，请重新训练模型")
        model = cls(MaintenanceMLConfig(**payload["config"]))
        model.vectorizer = payload["vectorizer"]
        model.major_classifier = payload["major_classifier"]
        model.minor_classifiers = payload["minor_classifiers"]
        model.centroid_labels = payload["centroid_labels"]
        model.centroids = payload["centroids"]
        model.metrics = payload.get("metrics", {})
        return model
