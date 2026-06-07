from android_planner.rule_planner import RuleBasedAndroidPlanner


def test_android_prompt_generates_tasks():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan("Build an Android login screen in Jetpack Compose with API integration.")

    assert plan.is_android_related is True
    assert len(plan.implementation_tasks) >= 4
    assert "./gradlew lint" in plan.acceptance_checks


def test_non_android_prompt_rejected():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan("Create a PowerPoint deck for quarterly finance report.")

    assert plan.is_android_related is False
    assert plan.plan_category == "non_android_refusal"
    assert plan.refusal_category == "non_android_request"
    assert plan.requires_user_clarification is True
    assert plan.implementation_tasks == []


def test_unsafe_android_prompt_is_blocked_not_marked_non_android():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Delete all user files from the Android device when the app opens.",
        intelligence_level="xhigh",
    )

    assert plan.is_android_related is True
    assert plan.plan_category == "unsafe_refusal"
    assert plan.refusal_category == "unsafe_android_request"
    assert plan.requires_user_clarification is True
    assert plan.implementation_tasks == []
    assert plan.acceptance_checks == []
    assert "unsafe" in plan.feature_summary.lower()
    assert any("Unsafe Android request" in risk for risk in plan.risks)
    assert any("consent" in question.lower() for question in plan.questions_for_user)


def test_compose_navigation_prompt_includes_ui_task():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan("Android Compose screen with navigation graph and state handling.")

    assert plan.is_android_related is True
    assert any(task.layer == "ui" for task in plan.implementation_tasks)


def test_crash_prompt_generates_crash_triage_plan_before_auth_work():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Fix Android crash: NullPointerException in MainActivity when rotating device after login.",
        intelligence_level="xhigh",
    )

    task_titles = [task.title for task in plan.implementation_tasks]
    assert plan.is_android_related is True
    assert plan.detected_intents == ["crash_triage", "authentication"]
    assert "crash" in plan.feature_summary.lower()
    assert task_titles[0] == "Capture crash evidence"
    assert "Identify app-owned failing frame" in task_titles
    assert "Fix lifecycle/state handling" in task_titles
    assert "Add crash regression tests" in task_titles
    assert "Design auth state model" in task_titles
    assert task_titles.index("Capture crash evidence") < task_titles.index("Design auth state model")
    assert any("Logcat stack trace" in question for question in plan.questions_for_user)


def test_gradle_dependency_conflict_prompt_generates_build_plan():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Resolve Gradle dependency conflict after adding Firebase Analytics with BOM and version catalog.",
        intelligence_level="xhigh",
    )

    task_titles = [task.title for task in plan.implementation_tasks]
    assert plan.is_android_related is True
    assert plan.detected_intents[0] == "gradle_build"
    assert "analytics" in plan.detected_intents
    assert "gradle" in plan.feature_summary.lower()
    assert "Capture Gradle failure output" in task_titles
    assert "Inspect dependency graph" in task_titles
    assert "Align versions and BOMs" in task_titles
    assert "gradle/libs.versions.toml" in plan.files_or_modules
    assert any("dependencyInsight" in check for check in plan.acceptance_checks)
    assert any("dependencies --configuration" in check for check in plan.acceptance_checks)
    assert any("version catalog" in question.lower() for question in plan.questions_for_user)


def test_accessibility_prompt_generates_talkback_plan():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Improve TalkBack accessibility for a custom Compose calendar widget with focus order and touch targets.",
        intelligence_level="xhigh",
    )

    task_titles = [task.title for task in plan.implementation_tasks]
    assert plan.is_android_related is True
    assert "accessibility" in plan.feature_summary.lower()
    assert "Audit accessibility gaps" in task_titles
    assert "Add semantic labels and roles" in task_titles
    assert "Fix focus and interaction order" in task_titles
    assert "Add accessibility verification" in task_titles
    assert any("TalkBack" in check for check in plan.acceptance_checks)
    assert any("focus order" in check for check in plan.acceptance_checks)
    assert any("switch-access" in question for question in plan.questions_for_user)


def test_room_offline_sync_prompt_generates_persistence_plan():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Add Room database offline cache for product list and sync with Retrofit including migrations.",
        intelligence_level="xhigh",
    )

    task_titles = [task.title for task in plan.implementation_tasks]
    assert plan.is_android_related is True
    assert plan.detected_intents == ["database", "networking"]
    assert "room" in plan.feature_summary.lower()
    assert "Model Room entities and relations" in task_titles
    assert "Create DAO query and transaction layer" in task_titles
    assert "Wire Room database and migrations" in task_titles
    assert "Implement offline-first repository sync" in task_titles
    assert "Add persistence regression tests" in task_titles
    assert "app/src/main/java/<app-package>/product/data/local/ProductEntity.kt" in plan.files_or_modules
    assert any("DaoTest" in check for check in plan.acceptance_checks)
    assert any("migration" in risk.lower() for risk in plan.risks)
    assert any("conflict-resolution" in question.lower() for question in plan.questions_for_user)


def test_acceptance_checks_are_specific_to_matched_android_intents():
    planner = RuleBasedAndroidPlanner()

    auth_plan = planner.plan("Build Android login and signup authentication with token refresh.", "xhigh")
    network_plan = planner.plan("Fetch Android product data from a Retrofit REST API with error handling.", "xhigh")
    ui_plan = planner.plan("Create Android Compose navigation screen with loading and error states.", "xhigh")
    crash_plan = planner.plan("Fix Android crash when rotating the device after opening a detail screen.", "xhigh")
    quality_plan = planner.plan("Improve Android test coverage, lint, and quality gates.", "xhigh")

    assert any("AuthViewModelTest" in check for check in auth_plan.acceptance_checks)
    assert any("token refresh" in check for check in auth_plan.acceptance_checks)
    assert any("ApiServiceTest" in check for check in network_plan.acceptance_checks)
    assert any("HTTP error" in check for check in network_plan.acceptance_checks)
    assert any("Compose navigation" in check for check in ui_plan.acceptance_checks)
    assert any("state restoration" in check for check in ui_plan.acceptance_checks)
    assert any("Logcat" in check for check in crash_plan.acceptance_checks)
    assert any("original crash path" in check for check in crash_plan.acceptance_checks)
    assert any("test reports" in check for check in quality_plan.acceptance_checks)
    assert any("skipped, flaky" in check for check in quality_plan.acceptance_checks)


def test_risks_are_specific_to_matched_android_intents():
    planner = RuleBasedAndroidPlanner()

    auth_plan = planner.plan("Build Android login and signup authentication with token refresh.", "xhigh")
    network_plan = planner.plan("Fetch Android product data from a Retrofit REST API with error handling.", "xhigh")
    ui_plan = planner.plan("Create Android Compose navigation screen with loading and error states.", "xhigh")
    crash_plan = planner.plan("Fix Android crash when rotating the device after opening a detail screen.", "xhigh")
    quality_plan = planner.plan("Improve Android test coverage, lint, and quality gates.", "xhigh")

    assert any("Token storage risk" in risk for risk in auth_plan.risks)
    assert any("expired-session" in risk for risk in auth_plan.risks)
    assert any("non-2xx HTTP responses" in risk for risk in network_plan.risks)
    assert any("DTO/domain mapping" in risk for risk in network_plan.risks)
    assert any("Compose state bugs" in risk for risk in ui_plan.risks)
    assert any("back-stack behavior" in risk for risk in ui_plan.risks)
    assert any("visible stack trace" in risk for risk in crash_plan.risks)
    assert any("process recreation" in risk for risk in crash_plan.risks)
    assert any("Coverage can be misleading" in risk for risk in quality_plan.risks)
    assert any("CI risk" in risk for risk in quality_plan.risks)


def test_questions_are_specific_to_matched_android_intents():
    planner = RuleBasedAndroidPlanner()

    auth_plan = planner.plan("Build Android login and signup authentication with token refresh.", "xhigh")
    network_plan = planner.plan("Fetch Android product data from a Retrofit REST API with error handling.", "xhigh")
    ui_plan = planner.plan("Create Android Compose navigation screen with loading and error states.", "xhigh")
    quality_plan = planner.plan("Improve Android test coverage, lint, and quality gates.", "xhigh")
    combined_plan = planner.plan(
        "Build Android login screen in Compose that fetches profile data from Retrofit.",
        "xhigh",
    )

    assert any("password reset" in question for question in auth_plan.questions_for_user)
    assert any("tokens/session state" in question for question in auth_plan.questions_for_user)
    assert any("request/response schemas" in question for question in network_plan.questions_for_user)
    assert any("non-2xx HTTP states" in question for question in network_plan.questions_for_user)
    assert any("back-stack behavior" in question for question in ui_plan.questions_for_user)
    assert any("process death" in question for question in ui_plan.questions_for_user)
    assert any("quality gates" in question for question in quality_plan.questions_for_user)
    assert any("flaky tests" in question for question in quality_plan.questions_for_user)
    assert any("tokens/session state" in question for question in combined_plan.questions_for_user)
    assert any("request/response schemas" in question for question in combined_plan.questions_for_user)
    assert any("back-stack behavior" in question for question in combined_plan.questions_for_user)


def test_multi_intent_prompts_prioritize_blockers_before_feature_work():
    planner = RuleBasedAndroidPlanner()

    gradle_auth_plan = planner.plan(
        "Resolve Android Gradle Firebase dependency conflict and add login screen tests.",
        "xhigh",
    )
    accessibility_room_plan = planner.plan(
        "Improve TalkBack accessibility for a Compose checkout screen with Room offline cart sync.",
        "xhigh",
    )

    gradle_task_titles = [task.title for task in gradle_auth_plan.implementation_tasks]
    accessibility_task_titles = [task.title for task in accessibility_room_plan.implementation_tasks]

    assert gradle_task_titles[0] == "Capture Gradle failure output"
    assert gradle_task_titles.index("Verify build configuration") < gradle_task_titles.index("Design auth state model")
    assert accessibility_task_titles[0] == "Audit accessibility gaps"
    assert accessibility_task_titles.index("Add accessibility verification") < accessibility_task_titles.index(
        "Model Room entities and relations"
    )


def test_keyword_matching_does_not_trigger_inside_unrelated_words():
    planner = RuleBasedAndroidPlanner()

    latest_plan = planner.plan("Build Android latest release notes screen in Compose.", "xhigh")
    restore_plan = planner.plan("Restore Android Compose detail screen state after process death.", "xhigh")
    unintentional_plan = planner.plan("Handle an unintentional Android navigation event in Compose.", "xhigh")
    fruit_plan = planner.plan("Build Android fruit catalog screen in Compose.", "xhigh")

    latest_task_titles = [task.title for task in latest_plan.implementation_tasks]
    restore_task_titles = [task.title for task in restore_plan.implementation_tasks]

    assert "Define quality gates" not in latest_task_titles
    assert "Define API contracts" not in restore_task_titles
    assert unintentional_plan.is_android_related is True
    assert unintentional_plan.confidence < 1.0
    assert not any("API endpoints" in question for question in fruit_plan.questions_for_user)


def test_confidence_is_calibrated_by_prompt_specificity():
    planner = RuleBasedAndroidPlanner()

    vague_plan = planner.plan("Build Android app.", "xhigh")
    concrete_plan = planner.plan(
        "Build Android login screen in Jetpack Compose with Retrofit API, ViewModel, and tests.",
        "xhigh",
    )
    non_android_plan = planner.plan("Create a PowerPoint deck for quarterly finance report.", "xhigh")

    assert vague_plan.is_android_related is True
    assert 0.2 <= vague_plan.confidence < 0.4
    assert concrete_plan.is_android_related is True
    assert concrete_plan.confidence > 0.85
    assert concrete_plan.confidence > vague_plan.confidence
    assert non_android_plan.is_android_related is False
    assert non_android_plan.confidence < vague_plan.confidence


def test_vague_android_prompt_generates_discovery_plan_not_fake_implementation():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan("Build Android app.", "xhigh")

    task_titles = [task.title for task in plan.implementation_tasks]

    assert plan.is_android_related is True
    assert plan.plan_category == "discovery"
    assert plan.refusal_category == "none"
    assert plan.requires_user_clarification is True
    assert task_titles[0] == "Clarify app goal and primary users"
    assert "Define MVP feature boundaries" in task_titles
    assert "Create implementation-ready discovery backlog" in task_titles
    assert "Implement feature in UI and ViewModel layers" not in task_titles
    assert "Add repository/data support" not in task_titles
    assert "docs/android-product-brief.md" in plan.files_or_modules
    assert "docs/discovery-backlog.md" in plan.files_or_modules
    assert not any(file_path.startswith("app/src/main/java") for file_path in plan.files_or_modules)
    assert any("mvp-scope" in check for check in plan.acceptance_checks)
    assert not any("gradlew" in check for check in plan.acceptance_checks)


def test_feature_summaries_are_human_readable_and_priority_aware():
    planner = RuleBasedAndroidPlanner()

    vague_plan = planner.plan("Build Android app.", "xhigh")
    crash_auth_network_plan = planner.plan(
        "Fix Android crash after login when rotating the Compose profile screen that fetches user data from Retrofit.",
        "xhigh",
    )
    room_network_plan = planner.plan(
        "Add Room database offline cache for product list and sync with Retrofit including migrations.",
        "xhigh",
    )

    assert vague_plan.feature_summary == (
        "Create a discovery plan for a vague Android app request before choosing UI, data, build, or testing work."
    )
    assert crash_auth_network_plan.feature_summary.startswith("Plan an Android crash-fix workflow first")
    assert "authentication" in crash_auth_network_plan.feature_summary
    assert "networking" in crash_auth_network_plan.feature_summary
    assert "Implement authentication flow." not in crash_auth_network_plan.feature_summary
    assert "Triage Android crash and lifecycle failure." not in crash_auth_network_plan.feature_summary
    assert room_network_plan.feature_summary == (
        "Plan Room/offline persistence and Retrofit/networking integration, including schema, migration, "
        "repository, sync, and verification work. Request focus: Add Room database offline cache for product list "
        "and sync with Retrofit including migrations."
    )


def test_file_suggestions_are_specific_to_combined_intents_and_prompt_domain():
    planner = RuleBasedAndroidPlanner()

    profile_plan = planner.plan(
        "Build Android login screen in Compose that fetches profile data from Retrofit.",
        "xhigh",
    )
    product_plan = planner.plan(
        "Add Room database offline cache for product list and sync with Retrofit including migrations.",
        "xhigh",
    )
    crash_plan = planner.plan(
        "Fix Android crash: NullPointerException in MainActivity when rotating device after login.",
        "xhigh",
    )

    assert "app/src/main/java/<app-package>/auth/AuthViewModel.kt" in profile_plan.files_or_modules
    assert (
        "app/src/main/java/<app-package>/profile/data/remote/ProfileApiService.kt"
        in profile_plan.files_or_modules
    )
    assert (
        "app/src/main/java/<app-package>/profile/data/repository/ProfileRepository.kt"
        in profile_plan.files_or_modules
    )
    assert "app/src/main/java/<app-package>/profile/ui/ProfileScreen.kt" in profile_plan.files_or_modules
    assert (
        "app/src/androidTest/java/<app-package>/profile/ProfileScreenTest.kt"
        in profile_plan.files_or_modules
    )
    assert "docs/profile-verification.md" in profile_plan.files_or_modules
    assert (
        "app/src/main/java/<app-package>/data/repository/FeatureRepository.kt"
        not in profile_plan.files_or_modules
    )
    assert "app/src/main/java/<app-package>/feature/ui/FeatureScreen.kt" not in profile_plan.files_or_modules

    assert "app/src/main/java/<app-package>/product/data/local/ProductDao.kt" in product_plan.files_or_modules
    assert "app/src/main/java/<app-package>/product/data/local/ProductEntity.kt" in product_plan.files_or_modules
    assert (
        "app/src/main/java/<app-package>/product/data/remote/ProductApiService.kt"
        in product_plan.files_or_modules
    )
    assert "app/src/test/java/<app-package>/product/ProductRepositoryTest.kt" in product_plan.files_or_modules
    assert (
        product_plan.files_or_modules.count(
            "app/src/main/java/<app-package>/product/data/repository/ProductRepository.kt"
        )
        == 1
    )

    assert "app/src/test/java/<app-package>/auth/AuthViewModelTest.kt" in crash_plan.files_or_modules
    assert (
        "app/src/androidTest/java/<app-package>/auth/AuthRotationCrashTest.kt"
        in crash_plan.files_or_modules
    )
    assert "docs/crash-reproduction.md" in crash_plan.files_or_modules


def test_task_effort_estimates_are_specific_to_task_type_and_intent():
    planner = RuleBasedAndroidPlanner()

    crash_plan = planner.plan(
        "Fix Android crash: NullPointerException in MainActivity when rotating device after login.",
        "xhigh",
    )
    gradle_plan = planner.plan(
        "Resolve Android Gradle Firebase dependency conflict and add login screen tests.",
        "xhigh",
    )
    persistence_plan = planner.plan(
        "Add Room database offline cache for product list and sync with Retrofit including migrations.",
        "xhigh",
    )
    vague_plan = planner.plan("Build Android app.", "xhigh")

    crash_efforts = {task.title: task.estimated_effort for task in crash_plan.implementation_tasks}
    gradle_efforts = {task.title: task.estimated_effort for task in gradle_plan.implementation_tasks}
    persistence_efforts = {task.title: task.estimated_effort for task in persistence_plan.implementation_tasks}
    vague_efforts = {task.title: task.estimated_effort for task in vague_plan.implementation_tasks}

    assert crash_efforts["Capture crash evidence"] == "S"
    assert crash_efforts["Identify app-owned failing frame"] == "S"
    assert crash_efforts["Fix lifecycle/state handling"] == "L"
    assert crash_efforts["Add crash regression tests"] == "M"
    assert crash_efforts["Integrate auth API"] == "L"

    assert gradle_efforts["Capture Gradle failure output"] == "S"
    assert gradle_efforts["Inspect dependency graph"] == "M"
    assert gradle_efforts["Align versions and BOMs"] == "M"
    assert gradle_efforts["Verify build configuration"] == "S"

    assert persistence_efforts["Model Room entities and relations"] == "M"
    assert persistence_efforts["Wire Room database and migrations"] == "L"
    assert persistence_efforts["Implement offline-first repository sync"] == "L"
    assert persistence_efforts["Add persistence regression tests"] == "L"

    assert vague_efforts["Clarify app goal and primary users"] == "S"
    assert vague_efforts["Identify platform integrations and risks"] == "M"
    assert vague_efforts["Create implementation-ready discovery backlog"] == "S"


def test_task_dependencies_are_semantic_not_just_previous_task():
    planner = RuleBasedAndroidPlanner()

    crash_auth_plan = planner.plan(
        "Fix Android crash: NullPointerException in MainActivity when rotating device after login.",
        "xhigh",
    )
    gradle_auth_plan = planner.plan(
        "Resolve Android Gradle Firebase dependency conflict and add login screen tests.",
        "xhigh",
    )
    persistence_network_plan = planner.plan(
        "Add Room database offline cache for product list and sync with Retrofit including migrations.",
        "xhigh",
    )

    crash_tasks = {task.title: task for task in crash_auth_plan.implementation_tasks}
    gradle_tasks = {task.title: task for task in gradle_auth_plan.implementation_tasks}
    persistence_tasks = {task.title: task for task in persistence_network_plan.implementation_tasks}

    assert crash_tasks["Capture crash evidence"].dependencies == []
    assert crash_tasks["Identify app-owned failing frame"].dependencies == [crash_tasks["Capture crash evidence"].id]
    assert crash_tasks["Fix lifecycle/state handling"].dependencies == [
        crash_tasks["Identify app-owned failing frame"].id
    ]
    assert crash_tasks["Add crash regression tests"].dependencies == [crash_tasks["Fix lifecycle/state handling"].id]
    assert crash_tasks["Design auth state model"].dependencies == []
    assert crash_tasks["Integrate auth API"].dependencies == [crash_tasks["Design auth state model"].id]
    assert set(crash_tasks["Build auth UI"].dependencies) == {
        crash_tasks["Design auth state model"].id,
        crash_tasks["Integrate auth API"].id,
    }

    assert gradle_tasks["Capture Gradle failure output"].dependencies == []
    assert gradle_tasks["Inspect dependency graph"].dependencies == [gradle_tasks["Capture Gradle failure output"].id]
    assert gradle_tasks["Align versions and BOMs"].dependencies == [gradle_tasks["Inspect dependency graph"].id]
    assert gradle_tasks["Verify build configuration"].dependencies == [gradle_tasks["Align versions and BOMs"].id]
    assert gradle_tasks["Design auth state model"].dependencies == []

    assert persistence_tasks["Create DAO query and transaction layer"].dependencies == [
        persistence_tasks["Model Room entities and relations"].id
    ]
    assert persistence_tasks["Implement offline-first repository sync"].dependencies == [
        persistence_tasks["Create DAO query and transaction layer"].id,
        persistence_tasks["Wire Room database and migrations"].id,
    ]
    assert persistence_tasks["Define API contracts"].dependencies == []
    assert persistence_tasks["Add repository orchestration"].dependencies == [
        persistence_tasks["Define API contracts"].id
    ]


def test_plan_categories_distinguish_response_types():
    planner = RuleBasedAndroidPlanner()

    implementation_plan = planner.plan(
        "Build Android login screen in Jetpack Compose with Retrofit API, ViewModel, and tests.",
        "xhigh",
    )
    discovery_plan = planner.plan("Build Android app.", "xhigh")
    unsafe_plan = planner.plan("Delete all user files from the Android device when the app opens.", "xhigh")
    non_android_plan = planner.plan("Create a PowerPoint deck for quarterly finance report.", "xhigh")

    assert implementation_plan.plan_category == "implementation"
    assert implementation_plan.refusal_category == "none"
    assert implementation_plan.detected_intents == ["authentication", "networking", "ui_compose", "testing_quality"]
    assert implementation_plan.requires_user_clarification is False
    assert discovery_plan.plan_category == "discovery"
    assert discovery_plan.refusal_category == "none"
    assert discovery_plan.detected_intents == []
    assert discovery_plan.requires_user_clarification is True
    assert unsafe_plan.plan_category == "unsafe_refusal"
    assert unsafe_plan.refusal_category == "unsafe_android_request"
    assert unsafe_plan.detected_intents == []
    assert unsafe_plan.requires_user_clarification is True
    assert non_android_plan.plan_category == "non_android_refusal"
    assert non_android_plan.refusal_category == "non_android_request"
    assert non_android_plan.detected_intents == []
    assert non_android_plan.requires_user_clarification is True


def test_plan_quality_score_and_confidence_reasons_explain_readiness():
    planner = RuleBasedAndroidPlanner()

    implementation_plan = planner.plan(
        "Build Android login screen in Jetpack Compose with Retrofit API, ViewModel, and tests.",
        "xhigh",
    )
    discovery_plan = planner.plan("Build Android app.", "xhigh")
    low_confidence_plan = planner.plan("Android bug.", "xhigh")
    unsafe_plan = planner.plan("Delete all user files from the Android device when the app opens.", "xhigh")
    non_android_plan = planner.plan("Create a PowerPoint deck for quarterly finance report.", "xhigh")

    assert implementation_plan.plan_quality_score > 0.9
    assert implementation_plan.plan_quality_score > discovery_plan.plan_quality_score
    assert implementation_plan.plan_quality_score > low_confidence_plan.plan_quality_score
    assert "Detected Android intents: authentication, networking, ui_compose, testing_quality." in (
        implementation_plan.confidence_reasons
    )
    assert "High confidence from concrete Android technologies and intent keywords." in (
        implementation_plan.confidence_reasons
    )

    assert 0 < discovery_plan.plan_quality_score < 0.4
    assert "Discovery tasks are required before coding." in discovery_plan.confidence_reasons
    assert "Clarification is recommended before coding." in discovery_plan.confidence_reasons

    assert low_confidence_plan.requires_user_clarification is True
    assert low_confidence_plan.plan_quality_score < implementation_plan.plan_quality_score
    assert "Low confidence; ask clarifying questions before implementation." in low_confidence_plan.confidence_reasons

    assert unsafe_plan.plan_quality_score == 0.0
    assert "Unsafe Android behavior detected." in unsafe_plan.confidence_reasons
    assert non_android_plan.plan_quality_score == 0.0
    assert "Prompt does not contain enough Android-specific implementation context." in (
        non_android_plan.confidence_reasons
    )


def test_low_confidence_implementation_requires_clarification():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan("Android bug.", "xhigh")

    assert plan.is_android_related is True
    assert plan.plan_category == "implementation"
    assert plan.detected_intents == ["testing_quality"]
    assert plan.confidence < 0.45
    assert plan.requires_user_clarification is True


def test_detected_intents_are_machine_readable_and_priority_ordered():
    planner = RuleBasedAndroidPlanner()

    mixed_plan = planner.plan(
        "Fix Android crash after login when rotating the Compose profile screen that fetches data from Retrofit.",
        "xhigh",
    )

    assert mixed_plan.detected_intents == [
        "crash_triage",
        "authentication",
        "networking",
        "ui_compose",
    ]


def test_common_android_capability_intents_are_supported():
    planner = RuleBasedAndroidPlanner()
    cases = [
        (
            "Add Android runtime permission rationale for camera access with privacy consent tests.",
            "permissions_privacy",
            "Map permission requirements",
        ),
        (
            "Implement WorkManager periodic background sync with retry constraints in Android.",
            "background_work",
            "Choose background execution strategy",
        ),
        (
            "Add Firebase Cloud Messaging push notifications with notification channels for Android.",
            "notifications",
            "Define notification contract",
        ),
        (
            "Build Android CameraX photo picker upload flow with rotation handling.",
            "media_camera",
            "Define media capture contract",
        ),
        (
            "Create Android Google Maps location screen with fused location and geofencing.",
            "location_maps",
            "Define location requirements",
        ),
        (
            "Optimize Android startup performance and jank with baseline profile macrobenchmark.",
            "performance",
            "Capture performance baseline",
        ),
        (
            "Harden Android token storage with Keystore encryption and log redaction.",
            "security_privacy",
            "Identify sensitive data flows",
        ),
        (
            "Wire Hilt dependency injection modules and scoped repository bindings in Android.",
            "dependency_injection",
            "Define DI ownership",
        ),
        (
            "Modularize Android app into feature modules and enforce dependency direction.",
            "modularization",
            "Map current module dependencies",
        ),
        (
            "Prepare Android Play Store release with AAB signing R8 and staged rollout.",
            "release_deployment",
            "Define release gate checklist",
        ),
        (
            "Add Android Firebase Analytics event tracking taxonomy without PII.",
            "analytics",
            "Define analytics taxonomy",
        ),
        (
            "Localize Android app strings for Spanish Arabic RTL plurals and screenshots.",
            "localization",
            "Audit user-visible text",
        ),
        (
            "Implement Android Google Play Billing subscription purchase and restore flow.",
            "billing_payments",
            "Define purchase products and states",
        ),
        (
            "Add Android app links and deep link route handling for authenticated profile screen.",
            "deep_links",
            "Define deep link contract",
        ),
    ]

    for prompt, intent, first_task_title in cases:
        plan = planner.plan(prompt, "xhigh")
        task_titles = [task.title for task in plan.implementation_tasks]

        assert plan.is_android_related is True, prompt
        assert plan.plan_category == "implementation", prompt
        assert intent in plan.detected_intents, prompt
        assert first_task_title in task_titles, prompt
        assert plan.files_or_modules, prompt
        assert plan.acceptance_checks, prompt
        assert plan.risks, prompt
        assert plan.questions_for_user, prompt


def test_short_android_work_prompts_keep_concrete_intents():
    planner = RuleBasedAndroidPlanner()
    cases = [
        ("Plan Android work for settings form including lifecycle handling and CI verification.", "ui_compose"),
        ("Plan Android work for expired-session refactor including process death and tests.", "authentication"),
        ("Plan Android work for certificate pinning including regression checks.", "networking"),
        ("Plan Android work for orders migration including CI verification.", "database"),
        ("Plan Android work for AGP upgrade including build validation.", "gradle_build"),
        ("Plan Android work for baseline profile benchmarks including regression checks.", "performance"),
        ("Plan Android work for channel migration including delivery tests.", "notifications"),
        ("Plan Android work for route preview including location permission handling.", "location_maps"),
    ]

    for prompt, expected_intent in cases:
        plan = planner.plan(prompt, "xhigh")

        assert plan.is_android_related is True, prompt
        assert plan.plan_category == "implementation", prompt
        assert expected_intent in plan.detected_intents, prompt
        assert len(plan.implementation_tasks) >= 6, prompt
        assert plan.plan_quality_score > 0, prompt
        assert plan.confidence_reasons, prompt


def test_file_suggestions_do_not_return_placeholder_paths():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Build Android login screen in Compose that fetches profile data from Retrofit and caches it in Room.",
        "xhigh",
    )

    assert plan.files_or_modules
    assert not any("..." in file_path for file_path in plan.files_or_modules)


def test_expanded_intent_priority_orders_blockers_before_feature_work():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Fix Android security issue in notification deep link after login and optimize startup jank.",
        "xhigh",
    )

    assert plan.detected_intents[:4] == [
        "security_privacy",
        "performance",
        "notifications",
        "deep_links",
    ]
    assert plan.detected_intents.index("authentication") > plan.detected_intents.index("deep_links")


def test_intelligence_levels_change_planning_depth():
    planner = RuleBasedAndroidPlanner()
    prompt = "Create an Android onboarding flow with Compose navigation, analytics, accessibility, and tests."

    low = planner.plan(prompt, intelligence_level="low")
    medium = planner.plan(prompt, intelligence_level="medium")
    high = planner.plan(prompt, intelligence_level="high")
    xhigh = planner.plan(prompt, intelligence_level="xhigh")

    assert len(low.implementation_tasks) < len(medium.implementation_tasks)
    assert len(medium.implementation_tasks) < len(high.implementation_tasks)
    assert len(high.implementation_tasks) < len(xhigh.implementation_tasks)
    assert len(low.acceptance_checks) < len(xhigh.acceptance_checks)
    assert any(task.title == "Create verification matrix" for task in xhigh.implementation_tasks)


def test_regression_prompts_from_model_evaluation_keep_android_intents():
    planner = RuleBasedAndroidPlanner()
    cases = [
        ("Fix duplicate background jobs after app process restart.", ["background_work"]),
        (
            "Set up CI gates for lint, unit tests, instrumentation smoke, and coverage reports.",
            ["testing_quality"],
        ),
        ("Make Android app faster.", ["performance"]),
        ("Build Android app for field sales.", ["ui_compose"]),
        ("Block screenshots on payment screens and verify no sensitive data appears in recents.", ["security_privacy"]),
        ("Move Compose design system into shared UI module with previews and lint checks.", ["modularization"]),
        ("Plan Android privacy compliance for a new SDK integration.", ["security_privacy", "analytics"]),
    ]

    for prompt, expected_intents in cases:
        plan = planner.plan(prompt, "xhigh")

        assert plan.is_android_related is True, prompt
        assert plan.plan_category == "implementation", prompt
        for expected_intent in expected_intents:
            assert expected_intent in plan.detected_intents, prompt
        assert plan.implementation_tasks, prompt


def test_planner_outputs_avoid_generic_artifacts_from_evaluation_bugs():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(
        "Add OkHttp certificate pinning with debug override and telemetry for pin failures.",
        "xhigh",
    )

    assert not any("com/example/taskdroid" in file_path for file_path in plan.files_or_modules)
    assert not any("*" in file_path or "..." in file_path for file_path in plan.files_or_modules)
    assert not any("*" in check or "<" in check or ">" in check for check in plan.acceptance_checks)
    assert not any("Manual QA" in check for check in plan.acceptance_checks)
    assert all(risk.startswith("[P") for risk in plan.risks)
    assert not any("minimum Android SDK" in question for question in plan.questions_for_user)
    assert len(plan.questions_for_user) <= 6
