from android_planner.ml import SklearnAndroidClassifier


def test_sklearn_android_classifier_fit_predict_and_proba():
    classifier = SklearnAndroidClassifier().fit(
        [
            "Build Android Compose login screen",
            "Fix Gradle dependency conflict",
            "Create PowerPoint budget deck",
            "Write a desktop Python script",
        ],
        [1, 1, 0, 0],
    )

    predictions = classifier.predict(["Android Room database migration", "Quarterly finance slides"])
    probabilities = classifier.predict_proba(["Android Room database migration"])

    assert predictions.shape == (2,)
    assert set(predictions.tolist()).issubset({0, 1})
    assert probabilities.shape == (1, 2)


def test_sklearn_android_classifier_save_and_load(tmp_path):
    path = tmp_path / "models" / "classifier.pkl"
    classifier = SklearnAndroidClassifier().fit(
        [
            "Build Android notification channel",
            "Add Retrofit API retry handling",
            "Draft a sales email",
            "Create spreadsheet formulas",
        ],
        [1, 1, 0, 0],
    )

    classifier.save(path)
    loaded = SklearnAndroidClassifier.load(path)

    assert path.exists()
    assert loaded.predict(["Android WorkManager sync"]).shape == (1,)
