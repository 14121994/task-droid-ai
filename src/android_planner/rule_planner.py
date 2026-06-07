"""Rule-based Android planner baseline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Set, Tuple

from .schemas import ImplementationTask, TaskPlan

PlannerDepth = Literal["low", "medium", "high", "xhigh"]
TaskEffort = Literal["S", "M", "L"]
CODE_PACKAGE_ROOT = "<app-package>"


@dataclass(frozen=True)
class IntentRule:
    keywords: Set[str]
    summary: str
    task_templates: List[Tuple[str, str, str]]
    files: List[str]


ANDROID_CORE_TERMS = {
    "android",
    "android app",
    "android work",
    "kotlin",
    "jetpack",
    "compose",
    "activity",
    "fragment",
    "viewmodel",
    "room",
    "retrofit",
    "gradle",
    "sdk",
    "manifest",
    "intent",
    "espresso",
    "adb",
    "workmanager",
    "hilt",
    "dagger",
    "firebase",
    "fcm",
    "camera",
    "camerax",
    "maps",
    "google maps",
    "google play",
    "play billing",
    "app link",
    "app links",
    "baseline profile",
    "play store",
    "instrumentation",
    "instrumentation tests",
    "background job",
    "background jobs",
    "process restart",
}

ANDROID_ACTION_TERMS = {
    "add",
    "build",
    "create",
    "debug",
    "fix",
    "implement",
    "improve",
    "resolve",
    "optimize",
    "localize",
    "release",
    "migrate",
    "test",
    "plan",
    "triage",
    "audit",
    "diagnose",
    "wire",
    "harden",
    "prepare",
    "refactor",
    "configure",
    "set up",
    "make",
    "review",
    "schedule",
    "reduce",
    "remove",
    "handle",
    "reject",
    "preserve",
}

ANDROID_VAGUE_CONTEXT_TERMS = {
    "app",
    "application",
    "feature",
}

NEGATIVE_TERMS = {
    "ios",
    "swiftui",
    "react",
    "nextjs",
    "excel",
    "powerpoint",
    "photoshop",
    "wordpress",
    "salesforce",
}

ANDROID_SAFETY_CONTEXT_TERMS = ANDROID_CORE_TERMS | {
    "app",
    "device",
    "phone",
    "user",
    "users",
    "file",
    "files",
    "contact",
    "contacts",
    "sms",
    "photo",
    "photos",
    "camera",
    "microphone",
    "location",
    "permission",
    "permissions",
}

HARMFUL_ANDROID_PATTERNS = {
    "delete all",
    "wipe",
    "erase",
    "steal",
    "exfiltrate",
    "spy",
    "secretly record",
    "secretly records",
    "record secretly",
    "records secretly",
    "track location without",
    "bypass permission",
    "bypass permissions",
    "disable security",
    "hide from user",
    "send contacts",
    "upload photos",
    "keylogger",
    "ransomware",
    "malware",
}

INTENT_RULES: Dict[str, IntentRule] = {
    "crash_triage": IntentRule(
        keywords={
            "crash",
            "crash-free",
            "exception",
            "nullpointerexception",
            "npe",
            "stack trace",
            "logcat",
            "anr",
            "rotate",
            "rotating",
            "rotation",
            "configuration change",
            "lifecycle",
            "savedinstance",
            "savedstate",
            "anr",
            "classcastexception",
            "indexoutofboundsexception",
            "illegalstateexception",
            "activitynotfoundexception",
            "securityexception",
            "missing hilt injection",
            "release-only crash",
            "duplicate push fix",
        },
        summary="Triage Android crash and lifecycle failure.",
        task_templates=[
            (
                "Capture crash evidence",
                "Collect Logcat, stack trace, app version, device/API level, and exact reproduction steps.",
                "testing",
            ),
            (
                "Identify app-owned failing frame",
                "Map the first app package stack frame to the owning Activity, Fragment, ViewModel, or repository.",
                "cross-cutting",
            ),
            (
                "Fix lifecycle/state handling",
                "Guard nullable state and preserve screen data across rotation, process death, and recomposition.",
                "ui",
            ),
            (
                "Add crash regression tests",
                "Add unit or instrumentation coverage for the failing lifecycle path and null/error state.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../MainActivity.kt",
            "app/src/main/java/.../feature/...ViewModel.kt",
            "app/src/androidTest/java/.../*CrashTest.kt",
            "app/src/test/java/.../*ViewModelTest.kt",
        ],
    ),
    "authentication": IntentRule(
        keywords={
            "login",
            "signup",
            "auth",
            "authentication",
            "token",
            "tokens",
            "oauth",
            "password",
            "session",
            "sessions",
            "expired session",
            "expired-session",
            "sso",
            "single sign-on",
            "biometric",
            "passkey",
            "passkeys",
            "magic link",
            "magic-link",
            "two-factor",
            "2fa",
            "account recovery",
            "logout",
            "guest",
            "authenticated",
            "auth-gated",
            "chrome custom tabs",
        },
        summary="Implement authentication flow.",
        task_templates=[
            ("Design auth state model", "Create sealed auth states and transitions in ViewModel.", "domain"),
            ("Integrate auth API", "Add Retrofit service and repository methods for auth endpoints.", "data"),
            ("Build auth UI", "Create Compose screens for login/signup with form validation.", "ui"),
            ("Add auth tests", "Write unit tests for ViewModel and repository auth flows.", "testing"),
        ],
        files=[
            "app/src/main/java/.../auth/AuthViewModel.kt",
            "app/src/main/java/.../auth/AuthRepository.kt",
            "app/src/main/java/.../auth/ui/LoginScreen.kt",
        ],
    ),
    "networking": IntentRule(
        keywords={
            "api",
            "apis",
            "network",
            "networking",
            "retrofit",
            "http",
            "rest",
            "fetch",
            "graphql",
            "gql",
            "dto",
            "dtos",
            "websocket",
            "socket",
            "multipart",
            "upload",
            "timeout",
            "retry",
            "backoff",
            "error body",
            "http error",
            "certificate pinning",
            "ssl pinning",
            "okhttp",
            "cache policy",
            "response caching",
            "typed error",
            "typed error handling",
            "weather",
            "weather repository",
            "forecast",
        },
        summary="Implement networking layer.",
        task_templates=[
            ("Define API contracts", "Create request/response DTOs and Retrofit interfaces.", "data"),
            ("Add repository orchestration", "Map DTOs to domain models and handle failures.", "domain"),
            ("Integrate loading/error UI", "Expose loading and error states to Compose UI.", "ui"),
            ("Write API tests", "Mock API responses and verify repository behavior.", "testing"),
        ],
        files=[
            "app/src/main/java/.../data/remote/ApiService.kt",
            "app/src/main/java/.../data/repository/FeatureRepository.kt",
        ],
    ),
    "database": IntentRule(
        keywords={
            "room",
            "sqlite",
            "database",
            "cache",
            "local storage",
            "offline",
            "offline-first",
            "sync",
            "synchronization",
            "dao",
            "entity",
            "entities",
            "migration",
            "migrations",
            "transaction",
            "transactional",
            "conflict resolution",
            "orders migration",
            "search history",
            "favorites",
            "draft autosave",
            "datastore",
            "sharedpreferences",
            "many-to-many",
            "offline cache",
            "room queue",
        },
        summary="Implement Room persistence and offline-first synchronization.",
        task_templates=[
            (
                "Model Room entities and relations",
                "Define entities, primary keys, indexes, relations, and mapping to domain models.",
                "data",
            ),
            (
                "Create DAO query and transaction layer",
                "Add DAO queries, transactional writes, paging/sorting queries, and conflict strategies.",
                "data",
            ),
            (
                "Wire Room database and migrations",
                "Configure RoomDatabase, DI providers, schema export, and migration or destructive-migration policy.",
                "build",
            ),
            (
                "Implement offline-first repository sync",
                "Coordinate Retrofit remote data, local cache reads, invalidation, refresh, and conflict handling.",
                "domain",
            ),
            (
                "Add persistence regression tests",
                "Test DAOs with in-memory Room plus repository offline, error, migration, and sync-conflict paths.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../data/local/AppDatabase.kt",
            "app/src/main/java/.../data/local/FeatureDao.kt",
            "app/src/main/java/.../data/local/FeatureEntity.kt",
            "app/src/main/java/.../data/local/FeatureMigrations.kt",
            "app/src/main/java/.../data/repository/FeatureRepository.kt",
            "app/src/test/java/.../data/local/FeatureDaoTest.kt",
        ],
    ),
    "gradle_build": IntentRule(
        keywords={
            "gradle",
            "dependency",
            "dependencies",
            "conflict",
            "firebase",
            "bom",
            "version catalog",
            "libs.versions.toml",
            "gradle sync",
            "build failed",
            "compile",
            "plugin",
            "agp",
            "ksp",
            "kapt",
            "upgrade",
            "wrapper",
            "compiler mismatch",
            "duplicate class",
            "namespace",
            "manifest package",
            "convention plugin",
            "product flavors",
            "r8",
            "minification",
        },
        summary="Diagnose Android Gradle build and dependency configuration.",
        task_templates=[
            (
                "Capture Gradle failure output",
                "Collect the exact sync/build error, failing task, Gradle/AGP/Kotlin versions, and module path.",
                "build",
            ),
            (
                "Inspect dependency graph",
                "Run dependency insight/dependencies reports to identify duplicate, forced, or conflicting artifacts.",
                "build",
            ),
            (
                "Align versions and BOMs",
                "Update version catalog, Firebase/Compose BOMs, plugin versions, or constraints with minimal scope.",
                "build",
            ),
            (
                "Verify build configuration",
                "Re-run sync-equivalent Gradle tasks, assemble, lint, and unit tests after the dependency change.",
                "testing",
            ),
        ],
        files=[
            "settings.gradle.kts",
            "build.gradle.kts",
            "app/build.gradle.kts",
            "gradle/libs.versions.toml",
        ],
    ),
    "accessibility": IntentRule(
        keywords={
            "accessibility",
            "a11y",
            "talkback",
            "screen reader",
            "semantics",
            "contentdescription",
            "content description",
            "focus order",
            "keyboard navigation",
            "touch target",
            "contrast",
            "accessible",
            "font scaling",
            "dynamic font",
            "page announcements",
            "error announcements",
            "focus trapping",
            "bottom sheet",
            "a11y",
            "chart",
        },
        summary="Improve Android accessibility and assistive-technology support.",
        task_templates=[
            (
                "Audit accessibility gaps",
                "Inspect labels, roles, semantics, focus traversal, touch targets, contrast, and dynamic content.",
                "ui",
            ),
            (
                "Add semantic labels and roles",
                "Add content descriptions, Compose semantics, state descriptions, and decorative-image exclusions.",
                "ui",
            ),
            (
                "Fix focus and interaction order",
                "Ensure TalkBack, keyboard, and switch-access navigation follow the visible user journey.",
                "ui",
            ),
            (
                "Add accessibility verification",
                "Add Compose UI assertions and manual TalkBack or Accessibility Scanner verification steps.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../feature/ui/FeatureScreen.kt",
            "app/src/main/java/.../feature/ui/components/FeatureComponents.kt",
            "app/src/androidTest/java/.../*AccessibilityTest.kt",
            "app/src/main/res/values/strings.xml",
        ],
    ),
    "ui_compose": IntentRule(
        keywords={
            "ui",
            "screen",
            "screens",
            "compose",
            "navigation",
            "theme",
            "layout",
            "profile editor",
            "dashboard",
            "settings",
            "settings form",
            "checkout flow",
            "onboarding",
            "carousel",
            "feed list",
            "calendar picker",
            "search screen",
            "media detail",
            "split pane",
            "foldable",
            "form",
            "list states",
            "field sales",
            "sales app",
        },
        summary="Implement Jetpack Compose UI feature.",
        task_templates=[
            ("Design screen state", "Define immutable UI state and intent events.", "domain"),
            ("Build Compose screens", "Implement composables with state hoisting.", "ui"),
            ("Add navigation routes", "Register routes and argument handling.", "ui"),
            ("Add UI tests", "Write Compose UI tests for core user journeys.", "testing"),
        ],
        files=[
            "app/src/main/java/.../feature/ui/FeatureScreen.kt",
            "app/src/main/java/.../navigation/AppNavGraph.kt",
        ],
    ),
    "testing_quality": IntentRule(
        keywords={
            "test",
            "tests",
            "testing",
            "quality",
            "lint",
            "bug",
            "coverage",
            "ci",
            "quality gates",
            "mockwebserver",
            "turbine",
            "screenshot",
            "contract tests",
            "baseline profile benchmarks",
            "flaky",
            "espresso",
            "property-based",
            "regression checks",
        },
        summary="Improve test coverage and code quality.",
        task_templates=[
            ("Define quality gates", "Set lint and unit test thresholds in CI.", "build"),
            ("Add unit tests", "Increase ViewModel and repository coverage.", "testing"),
            ("Add instrumentation tests", "Cover key happy and error paths.", "testing"),
            ("Fix discovered issues", "Address lint and flaky test findings.", "cross-cutting"),
        ],
        files=[
            "app/build.gradle.kts",
            "app/src/test/java/.../*Test.kt",
            "app/src/androidTest/java/.../*Test.kt",
        ],
    ),
    "permissions_privacy": IntentRule(
        keywords={
            "permission",
            "permissions",
            "runtime permission",
            "runtime permissions",
            "camera permission",
            "location permission",
            "notification permission",
            "privacy",
            "consent",
            "data safety",
            "data-safety",
            "contacts import",
            "permission rationale",
            "denied",
            "denial",
            "denied-state",
            "selected photos",
            "nearby devices",
            "microphone permission",
            "notification onboarding",
            "settings fallback",
            "permanently denied",
            "permission process-death",
        },
        summary="Implement Android permissions and privacy-compliance flow.",
        task_templates=[
            (
                "Map permission requirements",
                (
                    "Identify required Android runtime permissions, sensitive data access, consent needs, "
                    "and policy scope."
                ),
                "cross-cutting",
            ),
            (
                "Build permission request flow",
                "Add rationale, request, denial, permanently-denied, and settings-redirect UI states.",
                "ui",
            ),
            (
                "Guard sensitive feature access",
                "Gate camera, location, media, contacts, notification, or sensor access behind explicit grants.",
                "domain",
            ),
            (
                "Verify privacy behavior",
                "Test granted, denied, revoked, backgrounded, and settings-changed permission states.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/AndroidManifest.xml",
            "app/src/main/java/.../permissions/PermissionController.kt",
            "app/src/main/java/.../permissions/PermissionRationaleScreen.kt",
        ],
    ),
    "background_work": IntentRule(
        keywords={
            "workmanager",
            "worker",
            "background work",
            "background task",
            "background job",
            "background jobs",
            "background sync",
            "periodic sync",
            "scheduled work",
            "foreground service",
            "foreground-service",
            "job scheduler",
            "alarmmanager",
            "sync queue",
            "unique work",
            "worker chain",
            "retry policy",
            "foreground service",
            "duplicate jobs",
            "duplicate background jobs",
            "app process restart",
            "home feed refresh",
            "upload worker",
            "foreground workout service",
            "workout service",
            "scheduling",
            "sync status",
        },
        summary="Implement Android background work and scheduling.",
        task_templates=[
            (
                "Choose background execution strategy",
                "Select WorkManager, foreground service, exact alarm, or in-app coroutine based on timing guarantees.",
                "domain",
            ),
            (
                "Implement worker and constraints",
                "Add input data, retry/backoff, network/charging constraints, idempotency, and cancellation handling.",
                "data",
            ),
            (
                "Expose background status",
                "Surface queued, running, success, retry, and failed states to UI or notifications where needed.",
                "ui",
            ),
            (
                "Test scheduling behavior",
                "Verify constraints, retries, process recreation, duplicate work prevention, and failure reporting.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../work/FeatureWorker.kt",
            "app/src/main/java/.../work/WorkScheduler.kt",
            "app/src/test/java/.../work/FeatureWorkerTest.kt",
        ],
    ),
    "notifications": IntentRule(
        keywords={
            "notification",
            "notifications",
            "push notification",
            "push notifications",
            "fcm",
            "firebase cloud messaging",
            "notification channel",
            "deep link notification",
            "fcm token",
            "channel",
            "channels",
            "channel migration",
            "direct reply",
            "local reminder",
            "local reminders",
            "reminder",
            "reminders",
            "rich media push",
            "notification grouping",
            "duplicate push",
            "duplicate push fix",
            "delivery",
            "delivered",
            "opened",
            "dismissed",
        },
        summary="Implement Android notification and FCM behavior.",
        task_templates=[
            (
                "Define notification contract",
                "Specify payload shape, channels, importance, grouping, actions, and navigation target behavior.",
                "domain",
            ),
            (
                "Implement notification delivery",
                (
                    "Add FCM handling, channel setup, notification builder, pending intents, and Android 13 "
                    "permission flow."
                ),
                "data",
            ),
            (
                "Wire notification navigation",
                "Route notification taps and actions through safe deep links and authenticated app state.",
                "ui",
            ),
            (
                "Verify notification scenarios",
                "Test foreground, background, killed-process, denied-permission, and stale-payload behavior.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/AndroidManifest.xml",
            "app/src/main/java/.../notifications/AppFirebaseMessagingService.kt",
            "app/src/main/java/.../notifications/NotificationRouter.kt",
        ],
    ),
    "media_camera": IntentRule(
        keywords={
            "camera",
            "camerax",
            "photo",
            "photos",
            "image picker",
            "video",
            "media",
            "gallery",
            "file picker",
            "document picker",
            "photo picker",
            "selected photos",
            "exif",
            "orientation",
            "voice note",
            "voice-note",
            "voice notes",
            "audio recording",
            "audio recorder",
            "recorder",
            "document scanner",
            "image editing",
            "crop",
            "large image",
        },
        summary="Implement Android camera, media, and picker flow.",
        task_templates=[
            (
                "Define media capture contract",
                "Choose CameraX, Photo Picker, document picker, or gallery flow and define output ownership.",
                "domain",
            ),
            (
                "Implement media acquisition",
                "Handle permissions, URI access, capture/pick result, orientation, compression, and failure states.",
                "ui",
            ),
            (
                "Persist or upload media safely",
                "Store metadata, handle temporary files, redact logs, and upload through repository boundaries.",
                "data",
            ),
            (
                "Test media edge cases",
                "Verify denied permission, canceled picker, large files, rotation, process death, and upload failure.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../media/MediaPickerController.kt",
            "app/src/main/java/.../media/MediaRepository.kt",
            "app/src/androidTest/java/.../media/MediaFlowTest.kt",
        ],
    ),
    "location_maps": IntentRule(
        keywords={
            "location",
            "gps",
            "geofence",
            "geofencing",
            "maps",
            "map",
            "google maps",
            "fused location",
            "foreground location",
            "background location",
            "route preview",
            "store locator",
            "marker",
            "marker clustering",
            "tracking privacy",
            "tracking privacy toggle",
            "disabled services",
            "approximate location",
            "current location",
            "places api",
        },
        summary="Implement Android location and maps behavior.",
        task_templates=[
            (
                "Define location requirements",
                "Clarify precision, foreground/background access, update frequency, map provider, and retention needs.",
                "cross-cutting",
            ),
            (
                "Implement location data source",
                "Use fused location or geofencing APIs with permission, settings, cancellation, and battery controls.",
                "data",
            ),
            (
                "Build map or location UI",
                "Render permission, unavailable, loading, selected-place, and tracking states in Compose.",
                "ui",
            ),
            (
                "Verify location privacy and accuracy",
                "Test approximate/precise permission, disabled services, mock locations, and background restrictions.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/AndroidManifest.xml",
            "app/src/main/java/.../location/LocationDataSource.kt",
            "app/src/main/java/.../location/ui/LocationMapScreen.kt",
        ],
    ),
    "performance": IntentRule(
        keywords={
            "performance",
            "slow",
            "jank",
            "lag",
            "startup",
            "memory leak",
            "memory",
            "battery",
            "faster",
            "speed",
            "speed up",
            "recomposition",
            "baseline profile",
            "profiling",
            "benchmark",
            "benchmarks",
            "macrobenchmark",
            "cold start",
            "scrolling",
            "feed scrolling",
            "frame time",
            "typing latency",
            "apk size",
            "wakeups",
            "coIL",
            "image loading",
        },
        summary="Diagnose and improve Android performance.",
        task_templates=[
            (
                "Capture performance baseline",
                (
                    "Measure startup, frame time, recomposition, memory, network, database, or battery metrics "
                    "before changes."
                ),
                "testing",
            ),
            (
                "Identify bottleneck owner",
                (
                    "Map slow paths to UI composition, database query, network call, allocation, DI, "
                    "or build configuration."
                ),
                "cross-cutting",
            ),
            (
                "Apply targeted optimization",
                (
                    "Optimize only the measured bottleneck with stable state, caching, paging, baseline profiles, "
                    "or lazy work."
                ),
                "cross-cutting",
            ),
            (
                "Add performance regression guard",
                "Add macrobenchmark, baseline profile, trace, or lightweight metric check for the optimized path.",
                "testing",
            ),
        ],
        files=[
            "benchmark/src/main/java/.../StartupBenchmark.kt",
            "app/src/main/java/.../performance/PerformanceNotes.md",
            "app/src/androidTest/java/.../MacrobenchmarkTest.kt",
        ],
    ),
    "security_privacy": IntentRule(
        keywords={
            "security",
            "secure",
            "encryption",
            "encryptedsharedpreferences",
            "keystore",
            "certificate pinning",
            "ssl pinning",
            "token storage",
            "secrets",
            "pii",
            "redact",
            "redaction",
            "root detection",
            "secure screenshot",
            "secure screenshots",
            "block screenshot",
            "block screenshots",
            "screenshots",
            "recents",
            "recent apps",
            "flag_secure",
            "FLAG_SECURE",
            "cleartext",
            "network security config",
            "threat model",
            "clipboard",
            "exported activities",
            "exported activity",
            "pending intents",
            "device integrity",
            "fileprovider",
            "uri permissions",
            "consent-gated",
            "privacy compliance",
            "sdk integration",
        },
        summary="Harden Android app security and sensitive-data handling.",
        task_templates=[
            (
                "Identify sensitive data flows",
                "Map tokens, PII, secrets, local storage, logs, backups, and network transport boundaries.",
                "cross-cutting",
            ),
            (
                "Harden storage and transport",
                "Use Keystore-backed encryption, safe token/session storage, TLS policy, and log redaction.",
                "data",
            ),
            (
                "Add security failure handling",
                "Handle key invalidation, logout, compromised state, certificate failures, and recovery paths.",
                "domain",
            ),
            (
                "Verify security controls",
                "Test no secret leakage in logs, backups, screenshots, crash reports, and network error paths.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../security/SecureStorage.kt",
            "app/src/main/res/xml/network_security_config.xml",
            "app/src/test/java/.../security/SecureStorageTest.kt",
        ],
    ),
    "dependency_injection": IntentRule(
        keywords={
            "hilt",
            "dagger",
            "dependency injection",
            "di",
            "inject",
            "module",
            "provides",
            "binds",
            "component",
            "scope",
            "scopes",
            "service locator",
            "test bindings",
            "fake bindings",
            "assisted injection",
            "injection",
            "injectable clock",
            "dispatchers",
            "circular dependency",
            "entry point",
            "broadcastreceiver",
        },
        summary="Implement Android dependency injection boundaries.",
        task_templates=[
            (
                "Define DI ownership",
                "Map dependencies to app, activity, ViewModel, repository, worker, or feature scopes.",
                "domain",
            ),
            (
                "Add DI modules and bindings",
                "Create Hilt/Dagger modules, qualifiers, bindings, and test replacements with minimal scope.",
                "build",
            ),
            (
                "Wire injected consumers",
                "Inject ViewModels, repositories, workers, services, and navigation entry points safely.",
                "cross-cutting",
            ),
            (
                "Test dependency graph",
                "Verify graph compilation, fake bindings, and no accidental singleton/state leaks.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../di/AppModule.kt",
            "app/src/main/java/.../di/FeatureModule.kt",
            "app/src/test/java/.../di/TestAppModule.kt",
        ],
    ),
    "modularization": IntentRule(
        keywords={
            "modularize",
            "modularization",
            "multi-module",
            "module boundary",
            "feature module",
            "dynamic feature",
            "dependency direction",
            "clean architecture",
            "monolith",
            "design system module",
            "shared ui module",
            "ui module",
            "shared design system",
            "compose design system",
            "core-data module",
            "dynamic feature module",
            "dependency graph validation",
            "remove data implementation dependency",
            "feature dependency",
            "data implementation",
            "convention plugins",
            "module ownership",
            "test fixtures",
            "core networking module",
        },
        summary="Plan Android module boundaries and dependency direction.",
        task_templates=[
            (
                "Map current module dependencies",
                "Inspect Gradle modules, dependency direction, public APIs, resource ownership, and build impact.",
                "build",
            ),
            (
                "Define target module boundary",
                "Choose app, core, data, domain, design-system, and feature module ownership boundaries.",
                "cross-cutting",
            ),
            (
                "Move code behind stable APIs",
                "Migrate classes/resources incrementally behind interfaces without circular dependencies.",
                "cross-cutting",
            ),
            (
                "Verify module isolation",
                "Run affected Gradle tasks and tests to confirm dependency direction and build-cache behavior.",
                "testing",
            ),
        ],
        files=[
            "settings.gradle.kts",
            "feature/.../build.gradle.kts",
            "core/.../build.gradle.kts",
            "docs/module-boundaries.md",
        ],
    ),
    "release_deployment": IntentRule(
        keywords={
            "release",
            "deploy",
            "deployment",
            "play store",
            "google play",
            "bundle",
            "aab",
            "signing",
            "proguard",
            "r8",
            "rollout",
            "crashlytics",
            "firebase app distribution",
            "play integrity",
            "versioncode",
            "changelog",
            "mapping file",
            "release lane",
            "release lanes",
            "smoke test",
            "app bundle size",
            "play console",
        },
        summary="Prepare Android release and deployment workflow.",
        task_templates=[
            (
                "Define release gate checklist",
                "List versioning, signing, build variant, quality gate, privacy, and rollout requirements.",
                "cross-cutting",
            ),
            (
                "Configure release build",
                "Verify AAB generation, signing config, R8/ProGuard rules, mapping files, and dependency versions.",
                "build",
            ),
            (
                "Add rollout observability",
                "Confirm Crashlytics, analytics, logs, feature flags, and rollback or staged rollout paths.",
                "cross-cutting",
            ),
            (
                "Verify Play submission readiness",
                "Run release build, smoke test, data-safety review, and artifact/mapping retention checks.",
                "testing",
            ),
        ],
        files=[
            "app/build.gradle.kts",
            "app/proguard-rules.pro",
            "docs/release-checklist.md",
            "docs/play-data-safety.md",
        ],
    ),
    "analytics": IntentRule(
        keywords={
            "analytics",
            "event tracking",
            "tracking event",
            "firebase analytics",
            "telemetry",
            "funnel",
            "conversion",
            "screen tracking",
            "navigation tracking",
            "event",
            "events",
            "event taxonomy",
            "exposure logging",
            "debug overlay",
            "metrics",
            "latency metrics",
            "crash breadcrumbs",
            "event validation",
            "opt-out",
            "sdk integration",
            "privacy compliance",
            "open rates",
            "open-rate",
            "open-rate dashboard",
            "api latency metrics",
        },
        summary="Implement privacy-aware Android analytics instrumentation.",
        task_templates=[
            (
                "Define analytics taxonomy",
                "List events, parameters, user properties, screens, success/failure states, and privacy constraints.",
                "cross-cutting",
            ),
            (
                "Add analytics abstraction",
                "Create typed event APIs and provider adapters so UI/domain code does not depend on SDK details.",
                "domain",
            ),
            (
                "Instrument user journeys",
                "Track key screen, action, success, failure, and cancellation paths without sensitive payloads.",
                "ui",
            ),
            (
                "Verify analytics payloads",
                "Test event names, parameters, opt-out behavior, and redaction in debug or test providers.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../analytics/AnalyticsTracker.kt",
            "app/src/main/java/.../analytics/AnalyticsEvent.kt",
            "app/src/test/java/.../analytics/AnalyticsTrackerTest.kt",
        ],
    ),
    "localization": IntentRule(
        keywords={
            "localization",
            "localisation",
            "translate",
            "translation",
            "locale",
            "language",
            "rtl",
            "plural",
            "pluralization",
            "strings.xml",
            "hardcoded strings",
            "pseudo-locale",
            "per-app language",
            "language picker",
            "arabic",
            "hebrew",
            "date formatting",
            "currency",
            "number formatting",
            "translation key",
        },
        summary="Implement Android localization and locale support.",
        task_templates=[
            (
                "Audit user-visible text",
                (
                    "Find hardcoded strings, plurals, date/time/currency formats, content descriptions, "
                    "and error messages."
                ),
                "ui",
            ),
            (
                "Move text to resources",
                "Add strings, plurals, quantity strings, RTL-safe layouts, and locale-specific resource files.",
                "ui",
            ),
            (
                "Handle formatting and locale state",
                "Use locale-aware date, number, currency, sorting, casing, and dynamic language behavior.",
                "domain",
            ),
            (
                "Verify localized UI",
                "Test long translations, RTL, plurals, missing strings, accessibility labels, and screenshots.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/res/values/strings.xml",
            "app/src/main/res/values-es/strings.xml",
            "app/src/main/res/values-ar/strings.xml",
            "app/src/androidTest/java/.../LocalizationUiTest.kt",
        ],
    ),
    "billing_payments": IntentRule(
        keywords={
            "billing",
            "payment",
            "payments",
            "subscription",
            "subscriptions",
            "in-app purchase",
            "iap",
            "google play billing",
            "purchase",
            "refund",
            "restore purchases",
            "entitlement",
            "entitlements",
            "acknowledgement",
            "pending purchase",
            "price change",
            "payment retry",
            "promo code",
            "receipt validation",
            "subscription management",
            "payment sheet",
        },
        summary="Implement Android billing and payment workflow.",
        task_templates=[
            (
                "Define purchase products and states",
                "Map products, subscriptions, entitlement states, pending purchases, refunds, and restore behavior.",
                "domain",
            ),
            (
                "Integrate billing client",
                "Add Play Billing connection, product loading, purchase launch, acknowledgement, and retry handling.",
                "data",
            ),
            (
                "Build purchase UI states",
                (
                    "Show product loading, unavailable, purchase pending, success, failure, restore, "
                    "and entitlement states."
                ),
                "ui",
            ),
            (
                "Verify billing edge cases",
                (
                    "Test pending purchases, acknowledgement failures, offline, account switching, restore, "
                    "and cancellation."
                ),
                "testing",
            ),
        ],
        files=[
            "app/src/main/java/.../billing/BillingRepository.kt",
            "app/src/main/java/.../billing/BillingViewModel.kt",
            "app/src/test/java/.../billing/BillingRepositoryTest.kt",
        ],
    ),
    "deep_links": IntentRule(
        keywords={
            "deep link",
            "deep links",
            "deeplink",
            "app link",
            "app links",
            "universal link",
            "intent filter",
            "uri route",
            "dynamic link",
            "password reset",
            "assetlinks",
            "deferred deep link",
            "malformed url",
            "open redirect",
            "allowlist",
            "process-death deep link",
            "product detail deep link",
            "campaign deep links",
            "duplicate activity launch",
        },
        summary="Implement Android deep links and app links.",
        task_templates=[
            (
                "Define deep link contract",
                "List URI patterns, route arguments, auth requirements, fallback behavior, and ownership.",
                "domain",
            ),
            (
                "Configure app link entry points",
                "Add manifest intent filters, assetlinks validation, route parsing, and safe argument validation.",
                "build",
            ),
            (
                "Route deep links through navigation",
                "Handle cold start, warm start, auth-gated destinations, invalid links, and back-stack behavior.",
                "ui",
            ),
            (
                "Verify deep link paths",
                "Test adb am start, verified app links, invalid URIs, auth redirects, and notification link reuse.",
                "testing",
            ),
        ],
        files=[
            "app/src/main/AndroidManifest.xml",
            "app/src/main/java/.../navigation/DeepLinkRouter.kt",
            "app/src/androidTest/java/.../navigation/DeepLinkTest.kt",
        ],
    ),
}

INTENT_PRIORITY = {
    "crash_triage": 0,
    "gradle_build": 1,
    "security_privacy": 2,
    "permissions_privacy": 3,
    "performance": 4,
    "accessibility": 5,
    "database": 6,
    "dependency_injection": 7,
    "modularization": 8,
    "release_deployment": 9,
    "background_work": 10,
    "notifications": 11,
    "location_maps": 12,
    "media_camera": 13,
    "billing_payments": 14,
    "analytics": 15,
    "localization": 16,
    "deep_links": 17,
    "authentication": 18,
    "networking": 19,
    "ui_compose": 20,
    "testing_quality": 21,
}

INTENT_RELATED_LABELS = {
    "crash_triage": "crash triage",
    "gradle_build": "Gradle/build",
    "security_privacy": "security/privacy",
    "permissions_privacy": "permissions/privacy",
    "performance": "performance",
    "accessibility": "accessibility",
    "database": "persistence",
    "dependency_injection": "dependency injection",
    "modularization": "modularization",
    "release_deployment": "release/deployment",
    "background_work": "background work",
    "notifications": "notifications",
    "location_maps": "location/maps",
    "media_camera": "media/camera",
    "billing_payments": "billing/payments",
    "analytics": "analytics",
    "localization": "localization",
    "deep_links": "deep links",
    "authentication": "authentication",
    "networking": "networking",
    "ui_compose": "Compose UI",
    "testing_quality": "testing-quality",
}

INTENT_SINGLE_SUMMARIES = {
    "crash_triage": (
        "Plan an Android crash-fix workflow covering evidence capture, root-cause repair, and regression testing."
    ),
    "gradle_build": (
        "Plan an Android Gradle/build fix covering failure capture, dependency analysis, version alignment, "
        "and verification."
    ),
    "security_privacy": (
        "Plan Android security hardening covering sensitive-data flow, secure storage, network policy, "
        "and leakage tests."
    ),
    "permissions_privacy": (
        "Plan Android permission and privacy work covering rationale, denial states, consent, policy, and tests."
    ),
    "performance": (
        "Plan Android performance work covering measurement, bottleneck ownership, targeted optimization, "
        "and regression guard."
    ),
    "accessibility": (
        "Plan Android accessibility remediation covering semantics, focus order, assistive technology, "
        "and verification."
    ),
    "database": (
        "Plan Room/offline persistence work covering schema, DAO, migration, repository, sync, and verification."
    ),
    "dependency_injection": (
        "Plan Android dependency injection work covering scopes, Hilt/Dagger modules, consumers, and graph tests."
    ),
    "modularization": (
        "Plan Android modularization work covering Gradle modules, boundaries, migration, and dependency verification."
    ),
    "release_deployment": (
        "Plan Android release work covering signing, R8, Play submission, rollout observability, and verification."
    ),
    "background_work": (
        "Plan Android background work covering WorkManager strategy, constraints, retries, status, "
        "and scheduling tests."
    ),
    "notifications": (
        "Plan Android notification work covering FCM payloads, channels, permission, navigation, and delivery tests."
    ),
    "location_maps": (
        "Plan Android location/maps work covering permissions, fused location/geofencing, UI states, and privacy tests."
    ),
    "media_camera": (
        "Plan Android camera/media work covering capture or picker flow, permissions, URI handling, "
        "and edge-case tests."
    ),
    "billing_payments": (
        "Plan Android billing work covering products, Play Billing integration, entitlement UI, and purchase tests."
    ),
    "analytics": (
        "Plan Android analytics work covering taxonomy, typed tracking, privacy-safe instrumentation, "
        "and payload tests."
    ),
    "localization": (
        "Plan Android localization work covering string resources, plurals, RTL, locale formatting, and UI tests."
    ),
    "deep_links": (
        "Plan Android deep link work covering URI contracts, app links, route parsing, navigation, "
        "and adb verification."
    ),
    "authentication": (
        "Plan Android authentication work covering auth state, API integration, UI flows, secure session handling, "
        "and tests."
    ),
    "networking": "Plan Android networking work covering API contracts, repository mapping, failure states, and tests.",
    "ui_compose": "Plan Jetpack Compose UI work covering state, screens, navigation, restoration, and UI verification.",
    "testing_quality": (
        "Plan Android quality work covering lint, unit tests, instrumentation tests, flaky-test review, and CI gates."
    ),
}

INTENT_MULTI_PREFIXES = {
    "crash_triage": "Plan an Android crash-fix workflow first",
    "gradle_build": "Plan an Android Gradle/build fix first",
    "security_privacy": "Plan Android security and privacy hardening first",
    "permissions_privacy": "Plan Android permission and privacy work first",
    "performance": "Plan Android performance measurement and optimization first",
    "accessibility": "Plan Android accessibility remediation first",
    "database": "Plan Android persistence and offline data work first",
    "dependency_injection": "Plan Android dependency injection work first",
    "modularization": "Plan Android module-boundary work first",
    "release_deployment": "Plan Android release and deployment work first",
    "background_work": "Plan Android background execution work first",
    "notifications": "Plan Android notification delivery work first",
    "location_maps": "Plan Android location and maps work first",
    "media_camera": "Plan Android camera and media work first",
    "billing_payments": "Plan Android billing and payment work first",
    "analytics": "Plan Android analytics instrumentation first",
    "localization": "Plan Android localization work first",
    "deep_links": "Plan Android deep link routing first",
    "authentication": "Plan Android authentication work first",
    "networking": "Plan Android networking work first",
    "ui_compose": "Plan Jetpack Compose UI work first",
    "testing_quality": "Plan Android quality and test coverage work first",
}

FEATURE_DOMAIN_KEYWORDS = {
    "profile": {"profile", "user data", "user profile"},
    "product": {"product", "products", "catalog"},
    "checkout": {"checkout", "cart"},
    "calendar": {"calendar"},
    "settings": {"settings"},
    "onboarding": {"onboarding"},
    "search": {"search"},
    "feed": {"feed", "timeline"},
    "chat": {"chat", "message", "messages", "messaging"},
    "billing": {"billing", "payment", "payments", "subscription", "purchase"},
    "map": {"map", "maps", "location", "gps"},
    "media": {"camera", "photo", "photos", "video", "media", "gallery"},
    "notification": {"notification", "notifications", "fcm"},
    "sales": {"field sales", "sales app", "sales"},
}

CRASH_STRONG_TERMS = {
    "crash",
    "crash-free",
    "exception",
    "nullpointerexception",
    "npe",
    "stack trace",
    "logcat",
    "anr",
    "classcastexception",
    "indexoutofboundsexception",
    "illegalstateexception",
    "activitynotfoundexception",
    "securityexception",
    "release-only crash",
}

DEPENDENCY_INJECTION_STRONG_TERMS = {
    "hilt",
    "dagger",
    "dependency injection",
    "di",
    "inject",
    "provides",
    "binds",
    "scope",
    "scopes",
    "service locator",
    "test bindings",
    "fake bindings",
    "assisted injection",
    "injection",
    "injectable clock",
    "dispatchers",
    "circular dependency",
}

BILLING_STRONG_TERMS = {
    "billing",
    "subscription",
    "subscriptions",
    "in-app purchase",
    "iap",
    "google play billing",
    "purchase",
    "refund",
    "restore purchases",
    "entitlement",
    "entitlements",
    "acknowledgement",
    "pending purchase",
    "price change",
    "payment retry",
    "promo code",
    "receipt validation",
    "subscription management",
}

PERMISSION_STRONG_TERMS = {
    "permission",
    "permissions",
    "runtime permission",
    "runtime permissions",
    "camera permission",
    "location permission",
    "notification permission",
    "data-safety",
    "contacts import",
    "selected photos",
    "nearby devices",
    "microphone permission",
    "permission rationale",
    "permanently denied",
    "denied",
    "denial",
    "revokes",
    "revoked",
}

UI_COMPOSE_STRONG_TERMS = {
    "ui",
    "screen",
    "screens",
    "compose",
    "navigation",
    "theme",
    "layout",
    "profile editor",
    "dashboard",
    "checkout flow",
    "onboarding",
    "carousel",
    "feed list",
    "calendar picker",
    "search screen",
    "media detail",
    "split pane",
    "foldable",
    "form",
    "list states",
}


class RuleBasedAndroidPlanner:
    """Baseline planner that maps prompts into structured Android implementation tasks."""

    def plan(self, prompt: str, intelligence_level: PlannerDepth = "medium") -> TaskPlan:
        normalized = self._normalize(prompt)
        depth = self._normalize_depth(intelligence_level)
        is_android, confidence, matched_intents = self._classify(normalized)
        if self._is_unsafe_android_request(normalized):
            return self._unsafe_android_plan(confidence=max(confidence, 0.2), depth=depth)
        if not is_android:
            plan_category = "non_android_refusal"
            requires_user_clarification = True
            return TaskPlan(
                is_android_related=False,
                confidence=confidence,
                plan_quality_score=self._plan_quality_score(
                    confidence=confidence,
                    plan_category=plan_category,
                    requires_user_clarification=requires_user_clarification,
                    task_count=0,
                    matched_intents=[],
                ),
                confidence_reasons=self._confidence_reasons(
                    confidence=confidence,
                    plan_category=plan_category,
                    requires_user_clarification=requires_user_clarification,
                    matched_intents=[],
                    task_count=0,
                ),
                plan_category=plan_category,
                refusal_category="non_android_request",
                detected_intents=[],
                requires_user_clarification=requires_user_clarification,
                feature_summary="Prompt is not clearly Android app development related.",
                files_or_modules=[],
                implementation_tasks=[],
                acceptance_checks=[],
                risks=["[P2 Medium] Wrong domain detected; planner intentionally returns no implementation tasks."],
                questions_for_user=self._non_android_questions(depth),
            )

        tasks: List[ImplementationTask] = []
        files: List[str] = []

        task_count = 1
        for intent in matched_intents:
            rule = INTENT_RULES[intent]
            for title, description, layer in self._templates_for_depth(rule.task_templates, depth):
                task_id = f"T{task_count}"
                dependencies = self._dependencies_for_task(title, tasks)
                tasks.append(
                    ImplementationTask(
                        id=task_id,
                        title=title,
                        description=description,
                        layer=layer,  # type: ignore[arg-type]
                        estimated_effort=self._estimated_effort(intent, title, layer, depth),
                        dependencies=dependencies,
                    )
                )
                task_count += 1

        is_generic_plan = not tasks
        if is_generic_plan:
            tasks = self._generic_android_tasks(depth)
            files = self._generic_android_files(depth)
        else:
            tasks = self._enrich_tasks_for_depth(tasks, depth)
            files = self._files_for_depth(files, depth, prompt, matched_intents)

        plan_category = "discovery" if is_generic_plan else "implementation"
        detected_intents = [] if is_generic_plan else matched_intents
        requires_user_clarification = self._requires_user_clarification(
            confidence=confidence,
            is_generic_plan=is_generic_plan,
        )
        return TaskPlan(
            is_android_related=True,
            confidence=confidence,
            plan_quality_score=self._plan_quality_score(
                confidence=confidence,
                plan_category=plan_category,
                requires_user_clarification=requires_user_clarification,
                task_count=len(tasks),
                matched_intents=detected_intents,
            ),
            confidence_reasons=self._confidence_reasons(
                confidence=confidence,
                plan_category=plan_category,
                requires_user_clarification=requires_user_clarification,
                matched_intents=detected_intents,
                task_count=len(tasks),
            ),
            plan_category=plan_category,
            refusal_category="none",
            detected_intents=detected_intents,
            requires_user_clarification=requires_user_clarification,
            feature_summary=self._build_summary(matched_intents, is_generic_plan, prompt),
            files_or_modules=sorted(set(self._materialize_file_paths(files))),
            implementation_tasks=tasks,
            acceptance_checks=self._acceptance_checks_for_depth(depth, matched_intents),
            risks=self._risks_for_depth(depth, matched_intents),
            questions_for_user=self._follow_up_questions(prompt, matched_intents, depth),
        )

    @staticmethod
    def _normalize(prompt: str) -> str:
        return re.sub(r"\s+", " ", prompt.strip().lower())

    def _classify(self, normalized_prompt: str) -> Tuple[bool, float, List[str]]:
        core_matches: List[str] = []
        matched_intents: List[str] = []
        negative_matches: List[str] = []

        for term in ANDROID_CORE_TERMS:
            if self._contains_term(normalized_prompt, term):
                core_matches.append(term)

        for intent_name, rule in INTENT_RULES.items():
            if any(self._contains_term(normalized_prompt, keyword) for keyword in rule.keywords):
                matched_intents.append(intent_name)

        for term in NEGATIVE_TERMS:
            if self._contains_term(normalized_prompt, term):
                negative_matches.append(term)

        score = self._confidence_score(normalized_prompt, core_matches, matched_intents, negative_matches)

        bounded_score = min(max(score, 0.0), 1.0)
        is_android = bounded_score >= 0.2
        matched_intents = self._refine_matched_intents(normalized_prompt, matched_intents)
        return is_android, round(bounded_score, 3), self._prioritize_intents(matched_intents)

    @staticmethod
    def _confidence_score(
        normalized_prompt: str,
        core_matches: List[str],
        matched_intents: List[str],
        negative_matches: List[str],
    ) -> float:
        score = 0.0
        if "android" in core_matches:
            score += 0.18
        elif core_matches:
            score += 0.1

        concrete_core_matches = [term for term in core_matches if term != "android"]
        score += min(0.28, 0.07 * len(concrete_core_matches))
        score += min(0.36, 0.14 * len(matched_intents))

        if any(RuleBasedAndroidPlanner._contains_term(normalized_prompt, term) for term in ANDROID_ACTION_TERMS):
            score += 0.06
        if any(RuleBasedAndroidPlanner._contains_term(normalized_prompt, term) for term in ANDROID_VAGUE_CONTEXT_TERMS):
            score += 0.04
        if len(core_matches) >= 3 and matched_intents:
            score += 0.08
        if len(matched_intents) >= 2:
            score += 0.06

        score -= min(0.4, 0.2 * len(negative_matches))
        return score

    @staticmethod
    def _contains_term(normalized_prompt: str, term: str) -> bool:
        escaped_term = re.escape(term.lower())
        return re.search(rf"(?<![a-z0-9_]){escaped_term}(?![a-z0-9_])", normalized_prompt) is not None

    @classmethod
    def _contains_any(cls, normalized_prompt: str, terms: Set[str]) -> bool:
        return any(cls._contains_term(normalized_prompt, term) for term in terms)

    @classmethod
    def _refine_matched_intents(cls, normalized_prompt: str, matched_intents: List[str]) -> List[str]:
        refined = set(matched_intents)

        if cls._contains_term(normalized_prompt, "privacy compliance"):
            refined.update({"security_privacy", "analytics"})
            if not cls._contains_any(normalized_prompt, PERMISSION_STRONG_TERMS):
                refined.discard("permissions_privacy")

        if cls._contains_any(
            normalized_prompt,
            {"block screenshot", "block screenshots", "secure screenshot", "secure screenshots", "recents"},
        ):
            refined.add("security_privacy")
            if not cls._contains_any(normalized_prompt, BILLING_STRONG_TERMS):
                refined.discard("billing_payments")
            if not cls._contains_term(normalized_prompt, "compose"):
                refined.discard("ui_compose")

        if cls._contains_any(
            normalized_prompt,
            {"design system module", "shared ui module", "ui module", "shared design system", "compose design system"},
        ):
            refined.add("modularization")

        if "dependency_injection" in refined and not cls._contains_any(
            normalized_prompt,
            DEPENDENCY_INJECTION_STRONG_TERMS,
        ):
            refined.discard("dependency_injection")

        if "crash_triage" in refined and not cls._contains_any(normalized_prompt, CRASH_STRONG_TERMS):
            refined.discard("crash_triage")

        if "billing_payments" in refined and cls._contains_term(normalized_prompt, "payment"):
            if not cls._contains_any(normalized_prompt, BILLING_STRONG_TERMS):
                refined.discard("billing_payments")

        if "permissions_privacy" in refined and cls._contains_term(normalized_prompt, "privacy"):
            if not cls._contains_any(normalized_prompt, PERMISSION_STRONG_TERMS | {"consent", "data safety"}):
                refined.discard("permissions_privacy")

        if "ui_compose" in refined and cls._contains_term(normalized_prompt, "settings"):
            if not cls._contains_any(normalized_prompt, UI_COMPOSE_STRONG_TERMS - {"settings"}):
                refined.discard("ui_compose")

        return list(refined)

    @staticmethod
    def _prioritize_intents(matched_intents: List[str]) -> List[str]:
        return sorted(
            matched_intents,
            key=lambda intent: INTENT_PRIORITY.get(intent, len(INTENT_PRIORITY)),
        )

    @staticmethod
    def _is_unsafe_android_request(normalized_prompt: str) -> bool:
        has_android_context = any(
            RuleBasedAndroidPlanner._contains_term(normalized_prompt, term) for term in ANDROID_SAFETY_CONTEXT_TERMS
        )
        if not has_android_context:
            return False
        return any(
            RuleBasedAndroidPlanner._contains_term(normalized_prompt, pattern) for pattern in HARMFUL_ANDROID_PATTERNS
        )

    @staticmethod
    def _unsafe_android_plan(confidence: float, depth: PlannerDepth) -> TaskPlan:
        risks = [
            "[P0 High] Unsafe Android request detected; planner intentionally returns no implementation tasks.",
            (
                "[P0 High] The request appears destructive, privacy-invasive, permission-bypassing, "
                "or abusive to users/devices."
            ),
        ]
        questions = [
            (
                "Can you restate this as a legitimate Android safety, privacy, data-deletion, "
                "or permission-compliance feature?"
            ),
        ]
        if depth in {"high", "xhigh"}:
            risks.append(
                "[P1 High] A safe version should require explicit user consent, reversible flows, "
                "and platform policy review."
            )
            questions.append(
                "What user consent, retention, recovery, and Play policy requirements should the safe version meet?"
            )
        plan_category = "unsafe_refusal"
        requires_user_clarification = True
        return TaskPlan(
            is_android_related=True,
            confidence=round(min(max(confidence, 0.0), 1.0), 3),
            plan_quality_score=RuleBasedAndroidPlanner._plan_quality_score(
                confidence=confidence,
                plan_category=plan_category,
                requires_user_clarification=requires_user_clarification,
                task_count=0,
                matched_intents=[],
            ),
            confidence_reasons=RuleBasedAndroidPlanner._confidence_reasons(
                confidence=confidence,
                plan_category=plan_category,
                requires_user_clarification=requires_user_clarification,
                matched_intents=[],
                task_count=0,
            ),
            plan_category=plan_category,
            refusal_category="unsafe_android_request",
            detected_intents=[],
            requires_user_clarification=requires_user_clarification,
            feature_summary="Android request appears unsafe or privacy-invasive; no implementation tasks generated.",
            files_or_modules=[],
            implementation_tasks=[],
            acceptance_checks=[],
            risks=risks,
            questions_for_user=questions,
        )

    @staticmethod
    def _build_summary(matched_intents: List[str], is_generic_plan: bool, prompt: str) -> str:
        focus = RuleBasedAndroidPlanner._summary_focus(prompt)
        if is_generic_plan:
            return (
                "Create a discovery plan for a vague Android app request before choosing UI, data, build, "
                "or testing work."
            )
        if not matched_intents:
            return f"Android implementation plan for: {focus}."
        if len(matched_intents) == 1:
            return f"{INTENT_SINGLE_SUMMARIES[matched_intents[0]]} Request focus: {focus}."
        if "database" in matched_intents and "networking" in matched_intents:
            return (
                "Plan Room/offline persistence and Retrofit/networking integration, including schema, migration, "
                f"repository, sync, and verification work. Request focus: {focus}."
            )

        primary_intent = matched_intents[0]
        related_labels = [
            INTENT_RELATED_LABELS[intent] for intent in matched_intents[1:] if intent in INTENT_RELATED_LABELS
        ]
        if related_labels:
            return (
                f"{INTENT_MULTI_PREFIXES[primary_intent]}, then address related "
                f"{', '.join(related_labels)} work. Request focus: {focus}."
            )
        return f"{INTENT_MULTI_PREFIXES[primary_intent]}. Request focus: {focus}."

    @staticmethod
    def _summary_focus(prompt: str) -> str:
        normalized = re.sub(r"\s+", " ", prompt.strip()).strip(" .")
        if len(normalized) <= 110:
            return normalized
        return normalized[:107].rstrip() + "..."

    @staticmethod
    def _normalize_depth(intelligence_level: str) -> PlannerDepth:
        if intelligence_level in {"low", "medium", "high", "xhigh"}:
            return intelligence_level  # type: ignore[return-value]
        return "medium"

    @staticmethod
    def _requires_user_clarification(confidence: float, is_generic_plan: bool) -> bool:
        return is_generic_plan or confidence < 0.55

    @staticmethod
    def _plan_quality_score(
        confidence: float,
        plan_category: str,
        requires_user_clarification: bool,
        task_count: int,
        matched_intents: List[str],
    ) -> float:
        if plan_category in {"non_android_refusal", "unsafe_refusal"}:
            return 0.0

        score = confidence
        if plan_category == "discovery":
            score = min(score, 0.4)
        if requires_user_clarification:
            score -= 0.15
        if task_count >= 4 and matched_intents:
            score += 0.05
        if len(matched_intents) >= 2:
            score += 0.05

        return round(min(max(score, 0.0), 1.0), 3)

    @staticmethod
    def _confidence_reasons(
        confidence: float,
        plan_category: str,
        requires_user_clarification: bool,
        matched_intents: List[str],
        task_count: int,
    ) -> List[str]:
        if plan_category == "non_android_refusal":
            return [
                "Prompt does not contain enough Android-specific implementation context.",
                "Planner returned no implementation tasks by design.",
            ]
        if plan_category == "unsafe_refusal":
            return [
                "Unsafe Android behavior detected.",
                "Planner returned no implementation tasks and requires a safe restatement.",
            ]

        reasons = [f"Planner confidence is {confidence:.2f}."]
        if plan_category == "discovery":
            reasons.extend(
                [
                    "Prompt is Android-related but lacks a concrete implementation intent.",
                    "Discovery tasks are required before coding.",
                ]
            )
        elif matched_intents:
            reasons.append(f"Detected Android intents: {', '.join(matched_intents)}.")
            if confidence >= 0.75:
                reasons.append("High confidence from concrete Android technologies and intent keywords.")
            elif confidence < 0.45:
                reasons.append("Low confidence; ask clarifying questions before implementation.")
            else:
                reasons.append("Medium confidence from partial Android implementation context.")
            if len(matched_intents) >= 2:
                reasons.append("Multiple intents were prioritized before task generation.")
            if task_count >= 4:
                reasons.append("Generated implementation tasks, checks, risks, and follow-up questions.")

        if requires_user_clarification:
            reasons.append("Clarification is recommended before coding.")

        return reasons

    @staticmethod
    def _templates_for_depth(
        task_templates: List[Tuple[str, str, str]],
        depth: PlannerDepth,
    ) -> List[Tuple[str, str, str]]:
        if depth == "low":
            return task_templates[:2]
        return task_templates

    @staticmethod
    def _dependencies_for_task(title: str, prior_tasks: List[ImplementationTask]) -> List[str]:
        title_to_id = {task.title: task.id for task in prior_tasks}
        semantic_dependencies = {
            "Identify app-owned failing frame": ["Capture crash evidence"],
            "Fix lifecycle/state handling": ["Identify app-owned failing frame"],
            "Add crash regression tests": ["Fix lifecycle/state handling"],
            "Inspect dependency graph": ["Capture Gradle failure output"],
            "Align versions and BOMs": ["Inspect dependency graph"],
            "Verify build configuration": ["Align versions and BOMs"],
            "Add semantic labels and roles": ["Audit accessibility gaps"],
            "Fix focus and interaction order": ["Add semantic labels and roles"],
            "Add accessibility verification": ["Fix focus and interaction order"],
            "Create DAO query and transaction layer": ["Model Room entities and relations"],
            "Wire Room database and migrations": ["Create DAO query and transaction layer"],
            "Implement offline-first repository sync": [
                "Create DAO query and transaction layer",
                "Wire Room database and migrations",
                "Define API contracts",
                "Add repository orchestration",
            ],
            "Add persistence regression tests": [
                "Wire Room database and migrations",
                "Implement offline-first repository sync",
            ],
            "Integrate auth API": ["Design auth state model", "Define API contracts"],
            "Build auth UI": ["Design auth state model", "Integrate auth API"],
            "Add auth tests": ["Integrate auth API", "Build auth UI"],
            "Add repository orchestration": ["Define API contracts"],
            "Integrate loading/error UI": ["Add repository orchestration"],
            "Write API tests": ["Define API contracts", "Add repository orchestration"],
            "Build Compose screens": ["Design screen state"],
            "Add navigation routes": ["Build Compose screens"],
            "Add UI tests": ["Build Compose screens", "Add navigation routes"],
            "Add unit tests": ["Define quality gates"],
            "Add instrumentation tests": ["Define quality gates", "Add unit tests"],
            "Fix discovered issues": ["Add unit tests", "Add instrumentation tests"],
            "Build permission request flow": ["Map permission requirements"],
            "Guard sensitive feature access": ["Build permission request flow"],
            "Verify privacy behavior": ["Guard sensitive feature access"],
            "Implement worker and constraints": ["Choose background execution strategy"],
            "Expose background status": ["Implement worker and constraints"],
            "Test scheduling behavior": ["Implement worker and constraints"],
            "Implement notification delivery": ["Define notification contract"],
            "Wire notification navigation": ["Implement notification delivery"],
            "Verify notification scenarios": ["Implement notification delivery", "Wire notification navigation"],
            "Implement media acquisition": ["Define media capture contract"],
            "Persist or upload media safely": ["Implement media acquisition"],
            "Test media edge cases": ["Implement media acquisition", "Persist or upload media safely"],
            "Implement location data source": ["Define location requirements"],
            "Build map or location UI": ["Implement location data source"],
            "Verify location privacy and accuracy": ["Implement location data source", "Build map or location UI"],
            "Identify bottleneck owner": ["Capture performance baseline"],
            "Apply targeted optimization": ["Identify bottleneck owner"],
            "Add performance regression guard": ["Apply targeted optimization"],
            "Harden storage and transport": ["Identify sensitive data flows"],
            "Add security failure handling": ["Harden storage and transport"],
            "Verify security controls": ["Harden storage and transport", "Add security failure handling"],
            "Add DI modules and bindings": ["Define DI ownership"],
            "Wire injected consumers": ["Add DI modules and bindings"],
            "Test dependency graph": ["Add DI modules and bindings", "Wire injected consumers"],
            "Define target module boundary": ["Map current module dependencies"],
            "Move code behind stable APIs": ["Define target module boundary"],
            "Verify module isolation": ["Move code behind stable APIs"],
            "Configure release build": ["Define release gate checklist"],
            "Add rollout observability": ["Configure release build"],
            "Verify Play submission readiness": ["Configure release build", "Add rollout observability"],
            "Add analytics abstraction": ["Define analytics taxonomy"],
            "Instrument user journeys": ["Add analytics abstraction"],
            "Verify analytics payloads": ["Add analytics abstraction", "Instrument user journeys"],
            "Move text to resources": ["Audit user-visible text"],
            "Handle formatting and locale state": ["Move text to resources"],
            "Verify localized UI": ["Move text to resources", "Handle formatting and locale state"],
            "Integrate billing client": ["Define purchase products and states"],
            "Build purchase UI states": ["Integrate billing client"],
            "Verify billing edge cases": ["Integrate billing client", "Build purchase UI states"],
            "Configure app link entry points": ["Define deep link contract"],
            "Route deep links through navigation": ["Configure app link entry points"],
            "Verify deep link paths": ["Configure app link entry points", "Route deep links through navigation"],
        }
        return [
            title_to_id[dependency_title]
            for dependency_title in semantic_dependencies.get(title, [])
            if dependency_title in title_to_id
        ]

    @staticmethod
    def _estimated_effort(intent: str, title: str, layer: str, depth: PlannerDepth) -> TaskEffort:
        small_by_intent = {
            "crash_triage": {"Capture crash evidence", "Identify app-owned failing frame"},
            "gradle_build": {"Capture Gradle failure output", "Verify build configuration"},
        }
        large_by_intent = {
            "crash_triage": {"Fix lifecycle/state handling"},
            "authentication": {"Integrate auth API"},
            "database": {
                "Wire Room database and migrations",
                "Implement offline-first repository sync",
                "Add persistence regression tests",
            },
            "testing_quality": {"Add instrumentation tests"},
            "background_work": {"Implement worker and constraints"},
            "notifications": {"Implement notification delivery"},
            "media_camera": {"Implement media acquisition", "Persist or upload media safely"},
            "location_maps": {"Implement location data source"},
            "performance": {"Apply targeted optimization", "Add performance regression guard"},
            "security_privacy": {"Harden storage and transport"},
            "modularization": {"Move code behind stable APIs"},
            "release_deployment": {"Configure release build"},
            "billing_payments": {"Integrate billing client", "Verify billing edge cases"},
            "deep_links": {"Configure app link entry points", "Route deep links through navigation"},
        }

        if title in small_by_intent.get(intent, set()):
            return "S"
        if title in large_by_intent.get(intent, set()):
            return "L"
        if depth == "xhigh" and layer == "build" and intent == "database":
            return "L"
        return "M"

    @staticmethod
    def _generic_android_tasks(depth: PlannerDepth = "medium") -> List[ImplementationTask]:
        tasks = [
            ImplementationTask(
                id="T1",
                title="Clarify app goal and primary users",
                description="Identify the target users, core problem, platform constraints, and success criteria.",
                layer="cross-cutting",
                estimated_effort="S",
                dependencies=[],
            ),
            ImplementationTask(
                id="T2",
                title="Define MVP feature boundaries",
                description="Split the request into must-have, should-have, and later Android feature candidates.",
                layer="cross-cutting",
                estimated_effort="M",
                dependencies=["T1"],
            ),
            ImplementationTask(
                id="T3",
                title="Choose Android technical direction",
                description=(
                    "Decide whether the first plan needs Compose UI, data storage, networking, permissions, "
                    "or services."
                ),
                layer="cross-cutting",
                estimated_effort="M",
                dependencies=["T2"],
            ),
            ImplementationTask(
                id="T4",
                title="Write acceptance criteria and validation plan",
                description=(
                    "Define what must be true before implementation starts, including tests, manual QA, "
                    "and release checks."
                ),
                layer="testing",
                estimated_effort="M",
                dependencies=["T3"],
            ),
        ]
        if depth in {"high", "xhigh"}:
            tasks.append(
                ImplementationTask(
                    id="T5",
                    title="Identify platform integrations and risks",
                    description=(
                        "List required permissions, offline behavior, API needs, data retention, analytics, "
                        "and Play policy risks."
                    ),
                    layer="cross-cutting",
                    estimated_effort="M",
                    dependencies=["T4"],
                )
            )
        if depth == "xhigh":
            tasks.append(
                ImplementationTask(
                    id="T6",
                    title="Create implementation-ready discovery backlog",
                    description=(
                        "Turn clarified scope into ordered implementation stories with open questions and dependencies."
                    ),
                    layer="cross-cutting",
                    estimated_effort="S",
                    dependencies=["T5"],
                )
            )
        return tasks

    @staticmethod
    def _generic_android_files(depth: PlannerDepth = "medium") -> List[str]:
        files = [
            "docs/android-product-brief.md",
            "docs/mvp-scope.md",
            "docs/acceptance-criteria.md",
        ]
        if depth in {"high", "xhigh"}:
            files.extend(
                [
                    "docs/technical-direction.md",
                    "docs/platform-risk-review.md",
                ]
            )
        if depth == "xhigh":
            files.extend(
                [
                    "docs/discovery-backlog.md",
                    "docs/release-readiness-checklist.md",
                ]
            )
        return files

    @staticmethod
    def _enrich_tasks_for_depth(tasks: List[ImplementationTask], depth: PlannerDepth) -> List[ImplementationTask]:
        if depth == "low":
            return tasks[: max(2, min(len(tasks), 4))]
        enriched = list(tasks)
        next_id = len(enriched) + 1
        if depth in {"high", "xhigh"}:
            enriched.append(
                ImplementationTask(
                    id=f"T{next_id}",
                    title="Validate integration boundaries",
                    description=(
                        "Review dependency direction, ViewModel ownership, and repository contracts before coding."
                    ),
                    layer="cross-cutting",
                    estimated_effort="S",
                    dependencies=[enriched[-1].id] if enriched else [],
                )
            )
            next_id += 1
        if depth == "xhigh":
            enriched.extend(
                [
                    ImplementationTask(
                        id=f"T{next_id}",
                        title="Map edge cases and failure states",
                        description=(
                            "Enumerate empty, loading, error, offline, permission, and lifecycle-sensitive states."
                        ),
                        layer="cross-cutting",
                        estimated_effort="M",
                        dependencies=[enriched[-1].id] if enriched else [],
                    ),
                    ImplementationTask(
                        id=f"T{next_id + 1}",
                        title="Create verification matrix",
                        description="Tie each acceptance path to unit, UI, build, and device verification evidence.",
                        layer="testing",
                        estimated_effort="M",
                        dependencies=[f"T{next_id}"],
                    ),
                ]
            )
        return enriched

    @classmethod
    def _files_for_depth(
        cls,
        files: List[str],
        depth: PlannerDepth,
        prompt: str,
        matched_intents: List[str],
    ) -> List[str]:
        expanded = list(files)
        package_name, class_name = cls._feature_domain(prompt, matched_intents)

        for intent in matched_intents:
            expanded.extend(cls._files_for_intent(intent, package_name, class_name))

        if depth in {"high", "xhigh"}:
            expanded.append("app/src/main/java/.../di/AppModule.kt")
            expanded.append(f"docs/{package_name}-technical-notes.md")
        if depth == "xhigh":
            expanded.append(f"docs/{package_name}-verification.md")

        deduped = cls._dedupe(expanded)
        if depth == "low":
            return deduped[:4]
        return deduped

    @classmethod
    def _feature_domain(cls, prompt: str, matched_intents: List[str]) -> Tuple[str, str]:
        normalized_prompt = cls._normalize(prompt)
        for package_name, keywords in FEATURE_DOMAIN_KEYWORDS.items():
            if any(cls._contains_term(normalized_prompt, keyword) for keyword in keywords):
                return package_name, cls._class_name(package_name)
        if "authentication" in matched_intents:
            return "auth", "Auth"
        return "feature", "Feature"

    @staticmethod
    def _class_name(package_name: str) -> str:
        return "".join(part.capitalize() for part in package_name.split("_"))

    @classmethod
    def _files_for_intent(cls, intent: str, package_name: str, class_name: str) -> List[str]:
        intent_files = {
            "crash_triage": cls._crash_files(package_name, class_name),
            "authentication": [
                "app/src/main/java/.../auth/AuthViewModel.kt",
                "app/src/main/java/.../auth/AuthRepository.kt",
                "app/src/main/java/.../auth/ui/LoginScreen.kt",
                "app/src/test/java/.../auth/AuthViewModelTest.kt",
            ],
            "networking": [
                f"app/src/main/java/.../{package_name}/data/remote/{class_name}ApiService.kt",
                f"app/src/main/java/.../{package_name}/data/repository/{class_name}Repository.kt",
                f"app/src/test/java/.../{package_name}/{class_name}RepositoryTest.kt",
            ],
            "database": [
                f"app/src/main/java/.../{package_name}/data/local/AppDatabase.kt",
                f"app/src/main/java/.../{package_name}/data/local/{class_name}Dao.kt",
                f"app/src/main/java/.../{package_name}/data/local/{class_name}Entity.kt",
                f"app/src/main/java/.../{package_name}/data/local/{class_name}Migrations.kt",
                f"app/src/main/java/.../{package_name}/data/repository/{class_name}Repository.kt",
                f"app/src/test/java/.../{package_name}/{class_name}DaoTest.kt",
            ],
            "gradle_build": [
                "settings.gradle.kts",
                "build.gradle.kts",
                "app/build.gradle.kts",
                "gradle/libs.versions.toml",
                "docs/build-diagnostics.md",
            ],
            "accessibility": [
                f"app/src/main/java/.../{package_name}/ui/{class_name}Screen.kt",
                f"app/src/main/java/.../{package_name}/ui/components/{class_name}Components.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}AccessibilityTest.kt",
                "app/src/main/res/values/strings.xml",
            ],
            "ui_compose": [
                f"app/src/main/java/.../{package_name}/ui/{class_name}Screen.kt",
                "app/src/main/java/.../navigation/AppNavGraph.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}ScreenTest.kt",
            ],
            "testing_quality": [
                "app/build.gradle.kts",
                f"app/src/test/java/.../{package_name}/{class_name}ViewModelTest.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}FlowTest.kt",
            ],
            "permissions_privacy": [
                "app/src/main/AndroidManifest.xml",
                f"app/src/main/java/.../{package_name}/permissions/{class_name}PermissionController.kt",
                f"app/src/main/java/.../{package_name}/ui/{class_name}PermissionRationaleScreen.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}PermissionTest.kt",
            ],
            "background_work": [
                f"app/src/main/java/.../{package_name}/work/{class_name}Worker.kt",
                f"app/src/main/java/.../{package_name}/work/{class_name}WorkScheduler.kt",
                f"app/src/test/java/.../{package_name}/{class_name}WorkerTest.kt",
            ],
            "notifications": [
                "app/src/main/AndroidManifest.xml",
                "app/src/main/java/.../notifications/AppFirebaseMessagingService.kt",
                f"app/src/main/java/.../{package_name}/notifications/{class_name}NotificationRouter.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}NotificationTest.kt",
            ],
            "media_camera": [
                "app/src/main/AndroidManifest.xml",
                f"app/src/main/java/.../{package_name}/media/{class_name}MediaController.kt",
                f"app/src/main/java/.../{package_name}/media/{class_name}MediaRepository.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}MediaFlowTest.kt",
            ],
            "location_maps": [
                "app/src/main/AndroidManifest.xml",
                f"app/src/main/java/.../{package_name}/location/{class_name}LocationDataSource.kt",
                f"app/src/main/java/.../{package_name}/ui/{class_name}MapScreen.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}LocationTest.kt",
            ],
            "performance": [
                "benchmark/src/main/java/.../StartupBenchmark.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}MacrobenchmarkTest.kt",
                f"docs/{package_name}-performance-baseline.md",
            ],
            "security_privacy": [
                f"app/src/main/java/.../{package_name}/security/{class_name}SecureStorage.kt",
                "app/src/main/res/xml/network_security_config.xml",
                f"app/src/test/java/.../{package_name}/{class_name}SecurityTest.kt",
            ],
            "dependency_injection": [
                "app/src/main/java/.../di/AppModule.kt",
                f"app/src/main/java/.../{package_name}/di/{class_name}Module.kt",
                f"app/src/test/java/.../{package_name}/di/Test{class_name}Module.kt",
            ],
            "modularization": [
                "settings.gradle.kts",
                f"{package_name}/build.gradle.kts",
                "core/common/build.gradle.kts",
                "docs/module-boundaries.md",
            ],
            "release_deployment": [
                "app/build.gradle.kts",
                "app/proguard-rules.pro",
                "docs/release-checklist.md",
                "docs/play-data-safety.md",
            ],
            "analytics": [
                f"app/src/main/java/.../{package_name}/analytics/{class_name}AnalyticsEvent.kt",
                "app/src/main/java/.../analytics/AnalyticsTracker.kt",
                f"app/src/test/java/.../{package_name}/{class_name}AnalyticsTest.kt",
            ],
            "localization": [
                "app/src/main/res/values/strings.xml",
                "app/src/main/res/values-es/strings.xml",
                "app/src/main/res/values-ar/strings.xml",
                f"app/src/androidTest/java/.../{package_name}/{class_name}LocalizationTest.kt",
            ],
            "billing_payments": [
                f"app/src/main/java/.../{package_name}/billing/{class_name}BillingRepository.kt",
                f"app/src/main/java/.../{package_name}/billing/{class_name}BillingViewModel.kt",
                f"app/src/test/java/.../{package_name}/{class_name}BillingRepositoryTest.kt",
            ],
            "deep_links": [
                "app/src/main/AndroidManifest.xml",
                "app/src/main/java/.../navigation/DeepLinkRouter.kt",
                f"app/src/androidTest/java/.../{package_name}/{class_name}DeepLinkTest.kt",
            ],
        }
        return intent_files.get(intent, [])

    @staticmethod
    def _crash_files(package_name: str, class_name: str) -> List[str]:
        if package_name == "auth":
            return [
                "app/src/main/java/.../MainActivity.kt",
                "app/src/main/java/.../auth/AuthViewModel.kt",
                "app/src/main/java/.../auth/AuthRepository.kt",
                "app/src/test/java/.../auth/AuthViewModelTest.kt",
                "app/src/androidTest/java/.../auth/AuthRotationCrashTest.kt",
                "docs/crash-reproduction.md",
            ]
        return [
            "app/src/main/java/.../MainActivity.kt",
            f"app/src/main/java/.../{package_name}/{class_name}ViewModel.kt",
            f"app/src/test/java/.../{package_name}/{class_name}ViewModelTest.kt",
            f"app/src/androidTest/java/.../{package_name}/{class_name}CrashTest.kt",
            "docs/crash-reproduction.md",
        ]

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _materialize_file_paths(files: List[str]) -> List[str]:
        materialized: List[str] = []
        replacements = {
            "app/src/main/java/.../": f"app/src/main/java/{CODE_PACKAGE_ROOT}/",
            "app/src/test/java/.../": f"app/src/test/java/{CODE_PACKAGE_ROOT}/",
            "app/src/androidTest/java/.../": f"app/src/androidTest/java/{CODE_PACKAGE_ROOT}/",
            "benchmark/src/main/java/.../": f"benchmark/src/main/java/{CODE_PACKAGE_ROOT}/",
            "feature/.../": "feature/",
            "core/.../": "core/",
        }
        for file_path in files:
            concrete_path = file_path
            for placeholder, replacement in replacements.items():
                concrete_path = concrete_path.replace(placeholder, replacement)
            materialized.append(concrete_path.replace("...", "taskdroid"))
        return materialized

    @classmethod
    def _acceptance_checks_for_depth(cls, depth: PlannerDepth, matched_intents: List[str]) -> List[str]:
        if not matched_intents:
            checks = [
                "Review docs/android-product-brief.md with product owner or requester",
                "Confirm docs/mvp-scope.md separates must-have, should-have, and later work",
                "Verify docs/acceptance-criteria.md defines observable success criteria before implementation",
            ]
            if depth in {"high", "xhigh"}:
                checks.append("Review docs/technical-direction.md and docs/platform-risk-review.md")
            if depth == "xhigh":
                checks.append("Confirm docs/discovery-backlog.md is ordered by dependency and release risk")
            return cls._dedupe(checks)

        checks = ["./gradlew testDebugUnitTest --no-daemon"]
        intent_checks = {
            "crash_triage": [
                "./gradlew testDebugUnitTest --tests FeatureViewModelTest --no-daemon",
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Exploratory QA: reproduce the original crash path and verify Logcat has no new app-owned exception",
            ],
            "authentication": [
                "./gradlew testDebugUnitTest --tests AuthViewModelTest --no-daemon",
                "./gradlew testDebugUnitTest --tests AuthRepositoryTest --no-daemon",
                "Exploratory QA: verify login, signup, invalid credentials, token refresh, and logout paths",
            ],
            "networking": [
                "./gradlew testDebugUnitTest --tests FeatureRepositoryTest --no-daemon",
                "./gradlew testDebugUnitTest --tests FeatureApiServiceTest --no-daemon",
                "Exploratory QA: verify loading, success, HTTP error, timeout, and offline API states",
            ],
            "database": [
                "./gradlew testDebugUnitTest --tests FeatureDaoTest --no-daemon",
                "./gradlew testDebugUnitTest --tests FeatureRepositoryTest --no-daemon",
                "Verify Room schema export and migration coverage before release",
            ],
            "gradle_build": [
                "./gradlew :app:dependencies --configuration debugRuntimeClasspath",
                "./gradlew :app:dependencyInsight --dependency com.google.firebase:firebase-bom "
                "--configuration debugRuntimeClasspath",
                "./gradlew :app:assembleDebug --stacktrace",
            ],
            "accessibility": [
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Exploratory QA: run TalkBack through the affected user journey",
                "Exploratory QA: verify focus order, touch targets, labels, and contrast",
            ],
            "ui_compose": [
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Exploratory QA: verify Compose navigation, recomposition, state restoration, "
                "and empty/error UI states",
            ],
            "testing_quality": [
                "./gradlew lint",
                "./gradlew testDebugUnitTest --no-daemon",
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Review test reports for skipped, flaky, or newly failing test cases",
            ],
            "permissions_privacy": [
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Exploratory QA: verify allow, deny, permanently deny, revoke, and settings-return permission states",
                "Review Play data-safety and permission-rationale text for sensitive data access",
            ],
            "background_work": [
                "./gradlew testDebugUnitTest --tests FeatureWorkerTest --no-daemon",
                "Exploratory QA: verify constraints, retry/backoff, cancellation, and duplicate work prevention",
            ],
            "notifications": [
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Exploratory QA: verify foreground, background, killed-process, channel, tap, "
                "and denied-permission flows",
            ],
            "media_camera": [
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Exploratory QA: verify capture/pick cancel, large file, rotation, permission denial, "
                "and upload failure",
            ],
            "location_maps": [
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Exploratory QA: verify precise/approximate permission, disabled services, mock location, "
                "and map fallback",
            ],
            "performance": [
                "./gradlew connectedDebugAndroidTest --no-daemon",
                "Run macrobenchmark or profiling check for the measured performance path",
            ],
            "security_privacy": [
                "./gradlew testDebugUnitTest --tests FeatureSecurityTest --no-daemon",
                "Exploratory QA: verify logs, crash reports, backups, and screenshots do not expose sensitive data",
            ],
            "dependency_injection": [
                "./gradlew :app:hiltAggregateDepsDebug --no-daemon",
                "./gradlew testDebugUnitTest --tests FeatureModuleTest --no-daemon",
            ],
            "modularization": [
                "./gradlew projects",
                "./gradlew assembleDebug --no-daemon",
                "Verify no circular dependencies or forbidden module edges were introduced",
            ],
            "release_deployment": [
                "./gradlew :app:bundleRelease --no-daemon",
                "Verify signing, R8/ProGuard mapping retention, data-safety review, and staged rollout checklist",
            ],
            "analytics": [
                "./gradlew testDebugUnitTest --tests FeatureAnalyticsTest --no-daemon",
                "Exploratory QA: verify debug analytics payloads omit PII and respect opt-out behavior",
            ],
            "localization": [
                "./gradlew lint",
                "Exploratory QA: verify long translations, RTL layout, plurals, locale formatting, "
                "and accessibility labels",
            ],
            "billing_payments": [
                "./gradlew testDebugUnitTest --tests BillingRepositoryTest --no-daemon",
                "./gradlew testDebugUnitTest --tests BillingViewModelTest --no-daemon",
                "Exploratory QA: verify pending, canceled, acknowledged, restored, refunded, "
                "and offline purchase paths",
            ],
            "deep_links": [
                "adb shell am start -a android.intent.action.VIEW -d taskdroid://example/feature",
                "Verify cold start, warm start, invalid URI, auth-gated destination, and back-stack behavior",
            ],
        }
        if "gradle_build" in matched_intents:
            checks = []
        for intent in matched_intents:
            checks.extend(intent_checks.get(intent, []))
        if depth != "low":
            checks.insert(0, "./gradlew lint")
            checks.append("./gradlew assembleDebug --no-daemon")
        if depth in {"high", "xhigh"}:
            checks.append("./gradlew connectedDebugAndroidTest --no-daemon")
        if depth == "xhigh":
            checks.append("Exploratory QA: verify lifecycle, empty, loading, error, and accessibility paths")
        return cls._dedupe(checks)

    @staticmethod
    def _risks_for_depth(depth: PlannerDepth, matched_intents: List[str]) -> List[str]:
        risks = [
            "Requirements may be ambiguous without API contract and UX behavior details.",
        ]
        intent_risks = {
            "crash_triage": [
                (
                    "Crash may reappear if the fix only handles the visible stack trace instead of the "
                    "lifecycle/state root cause."
                ),
                (
                    "Regression risk if rotation, process recreation, null state, and delayed async callbacks "
                    "are not tested together."
                ),
                (
                    "Evidence risk if Logcat, device/API level, app version, and reproduction steps are not "
                    "captured before changing code."
                ),
            ],
            "authentication": [
                (
                    "Authentication state can become inconsistent if login, logout, token refresh, and "
                    "expired-session paths are not modeled explicitly."
                ),
                (
                    "Token storage risk if access or refresh tokens are persisted without secure storage and "
                    "lifecycle-aware cleanup."
                ),
                (
                    "Account-security risk if invalid credentials, rate limits, and server-side auth failures "
                    "are treated as generic errors."
                ),
            ],
            "networking": [
                (
                    "Networking bugs can appear if timeout, retry, cancellation, offline, and non-2xx HTTP "
                    "responses are not handled separately."
                ),
                "DTO/domain mapping risk if nullable or missing API fields are not validated before reaching UI state.",
                (
                    "User-experience risk if loading, empty, stale-cache, and error states collapse into the "
                    "same UI behavior."
                ),
            ],
            "database": [
                "Room migration mistakes can corrupt or drop user data across app upgrades.",
                "Offline-first sync can produce stale cache, duplicate rows, or local/remote conflict bugs.",
            ],
            "gradle_build": [
                "Dependency alignment risk if Gradle, AGP, Kotlin, Firebase, and Compose versions drift.",
                "Transitive dependency conflicts can reappear in other modules or build variants.",
            ],
            "accessibility": [
                "Accessibility regressions can block TalkBack, keyboard, or switch-access users.",
                "Missing labels, incorrect semantics, or poor focus order can make UI flows unusable.",
            ],
            "ui_compose": [
                (
                    "Compose state bugs can occur if state is owned by composables instead of ViewModel or "
                    "stable state holders."
                ),
                (
                    "Navigation bugs can occur if route arguments, back-stack behavior, and state restoration "
                    "are not verified."
                ),
                "UI regression risk if loading, empty, error, and success states are not independently tested.",
            ],
            "testing_quality": [
                (
                    "Coverage can be misleading if tests only verify happy paths and ignore error, lifecycle, "
                    "and offline states."
                ),
                (
                    "Quality gates can block delivery if lint/test tasks are added without handling flaky tests "
                    "and baseline ownership."
                ),
                "CI risk if local Gradle tasks differ from the checks required in pull requests or release builds.",
            ],
            "permissions_privacy": [
                (
                    "Permission flows can break if denied, permanently denied, revoked, or settings-return states "
                    "are not handled."
                ),
                "Policy risk if sensitive permissions or data-safety disclosures do not match actual behavior.",
            ],
            "background_work": [
                "Background execution can be throttled or killed if constraints and retry/backoff are misconfigured.",
                "Duplicate work or non-idempotent workers can corrupt data during retries or process recreation.",
            ],
            "notifications": [
                (
                    "Notification delivery can fail on Android 13+ if runtime notification permission and channels "
                    "are missing."
                ),
                "Security risk if notification deep links bypass auth or open stale/unvalidated payloads.",
            ],
            "media_camera": [
                (
                    "Media flows can leak files or break on rotation if URI permissions and temporary file cleanup "
                    "are wrong."
                ),
                "Large images/videos can cause memory, upload, or background execution failures.",
            ],
            "location_maps": [
                (
                    "Location features can violate privacy expectations if precision, retention, or background access "
                    "is unclear."
                ),
                "Battery risk if location updates are too frequent or not canceled with lifecycle changes.",
            ],
            "performance": [
                "Optimization can regress behavior if changes are not tied to measured bottlenecks.",
                "Performance fixes can be misleading without baseline, device/API context, and regression guardrails.",
            ],
            "security_privacy": [
                "Sensitive data can leak through logs, backups, screenshots, crash reports, or insecure local storage.",
                "Certificate pinning or encryption changes can lock users out if recovery paths are not planned.",
            ],
            "dependency_injection": [
                "DI scope mistakes can leak Activity/ViewModel state or create unintended singletons.",
                "Graph changes can break tests if fake bindings and module replacements are not planned.",
            ],
            "modularization": [
                "Module migrations can create circular dependencies or expose unstable internal APIs.",
                "Build time can regress if module boundaries and dependency directions are not measured.",
            ],
            "release_deployment": [
                (
                    "Release builds can fail late if signing, R8 rules, mapping files, or variant-specific configs "
                    "are unverified."
                ),
                "Rollout risk if observability, staged rollout, and rollback paths are not ready before submission.",
            ],
            "analytics": [
                "Analytics can collect PII or unstable event names if taxonomy and redaction are not defined first.",
                (
                    "Business metrics can become unreliable if cancellation, failure, and offline paths are not "
                    "tracked consistently."
                ),
            ],
            "localization": [
                "Localized UI can break with long text, RTL, plurals, date formats, or missing resource fallbacks.",
                (
                    "Accessibility labels can become inconsistent if translations are not tested with assistive "
                    "technology."
                ),
            ],
            "billing_payments": [
                (
                    "Billing bugs can grant or lose entitlements if pending, restore, refund, and acknowledgement "
                    "states are mishandled."
                ),
                "Play policy risk if purchase UI, subscription terms, or cancellation paths are unclear.",
            ],
            "deep_links": [
                "Deep links can bypass auth or crash if URI parsing and argument validation are incomplete.",
                "Back-stack and cold-start behavior can be inconsistent without adb/app-link verification.",
            ],
        }
        for intent in matched_intents:
            risks.extend(intent_risks.get(intent, []))
        if depth != "low":
            risks.append("Architecture drift risk if feature bypasses ViewModel/repository boundaries.")
        if depth in {"high", "xhigh"}:
            risks.append("Integration risk if DI, navigation, and state ownership are not verified together.")
        if depth == "xhigh":
            risks.append("Release risk if lifecycle, accessibility, analytics, and rollback paths are not exercised.")
        return RuleBasedAndroidPlanner._prioritized_risks(risks)

    @staticmethod
    def _prioritized_risks(risks: List[str]) -> List[str]:
        prioritized: List[str] = []
        for index, risk in enumerate(RuleBasedAndroidPlanner._dedupe(risks)):
            lowered = risk.lower()
            if any(term in lowered for term in {"unsafe", "security", "privacy", "data", "token", "billing"}):
                prefix = "P0 High"
            elif any(term in lowered for term in {"release", "crash", "migration", "dependency", "rollback"}):
                prefix = "P1 High"
            elif index < 3:
                prefix = "P2 Medium"
            else:
                prefix = "P3 Low"
            prioritized.append(f"[{prefix}] {risk}")
        return prioritized

    @staticmethod
    def _non_android_questions(depth: PlannerDepth) -> List[str]:
        questions = ["Can you restate the request with Android context (Kotlin/Compose/Gradle/modules)?"]
        if depth in {"high", "xhigh"}:
            questions.append("Should this be converted into an Android feature, build, test, or debugging task?")
        return questions

    @staticmethod
    def _follow_up_questions(prompt: str, matched_intents: List[str], depth: PlannerDepth) -> List[str]:
        questions: List[str] = []
        normalized_prompt = RuleBasedAndroidPlanner._normalize(prompt)
        if not matched_intents and RuleBasedAndroidPlanner._contains_term(normalized_prompt, "api"):
            questions.append("Do you already have API endpoints and authentication requirements?")
        if not matched_intents and (
            RuleBasedAndroidPlanner._contains_term(normalized_prompt, "ui")
            or RuleBasedAndroidPlanner._contains_term(normalized_prompt, "screen")
        ):
            questions.append("Do you have wireframes or should we use Material 3 defaults?")
        intent_questions = {
            "crash_triage": [
                "Can you provide the Logcat stack trace, device model, Android version, and reproduction steps?",
                (
                    "Does the crash happen after rotation, process recreation, navigation, backgrounding, "
                    "or async callbacks?"
                ),
            ],
            "authentication": [
                "Which auth flows are required: login, signup, logout, token refresh, password reset, or SSO?",
                "How should tokens/session state be stored, expired, refreshed, and cleared on logout?",
                (
                    "What server error codes should map to invalid credentials, locked account, rate limit, "
                    "or retryable failure?"
                ),
            ],
            "networking": [
                "Can you provide the endpoint paths, request/response schemas, auth headers, and pagination rules?",
                (
                    "How should timeout, offline, cancellation, retry, empty response, and non-2xx HTTP "
                    "states appear in UI?"
                ),
                "Should API DTOs be mapped into separate domain models, or can the UI consume network models directly?",
            ],
            "database": [
                "Which entities, relationships, and conflict-resolution rules should the Room schema support?",
                "Should cached data expire by time, manual refresh, server version, or write-through sync?",
            ],
            "gradle_build": [
                "Which module/configuration fails, and can you provide the Gradle sync or build error?",
                "Are you using a version catalog, Firebase/Compose BOM, or hardcoded dependency versions?",
            ],
            "accessibility": [
                "Which screens or components need TalkBack, keyboard, or switch-access verification?",
                "Are there required WCAG contrast, touch-target, or localization constraints?",
            ],
            "ui_compose": [
                (
                    "Which UI states are required: loading, empty, success, error, offline, permission, "
                    "or unauthenticated?"
                ),
                "What navigation routes, arguments, deep links, and back-stack behavior should this screen support?",
                "Should state survive rotation, process death, tab switches, or returning from the back stack?",
            ],
            "testing_quality": [
                (
                    "Which quality gates must pass locally and in CI: lint, unit tests, instrumentation tests, "
                    "or coverage?"
                ),
                "Are there known flaky tests, lint baselines, ignored tests, or modules that need priority coverage?",
                "Which user journeys are release-blocking and must be covered before merging?",
            ],
            "permissions_privacy": [
                "Which runtime permissions and sensitive data types are required, and which are optional?",
                "What should happen when the user denies, permanently denies, revokes, or later grants the permission?",
                "Are Play data-safety, consent, retention, or privacy-policy changes required?",
            ],
            "background_work": [
                (
                    "Does the work require exact timing, periodic execution, network/charging constraints, "
                    "or foreground service behavior?"
                ),
                "What retry, cancellation, duplicate-work, and failure-reporting behavior should the worker use?",
            ],
            "notifications": [
                "What payload fields, channels, actions, grouping, and tap destinations should notifications support?",
                (
                    "How should notification behavior differ in foreground, background, killed-process, "
                    "and denied-permission states?"
                ),
            ],
            "media_camera": [
                "Should the feature use CameraX, Android Photo Picker, document picker, or a custom camera flow?",
                (
                    "How should large files, orientation, temporary storage, upload failure, and canceled selection "
                    "be handled?"
                ),
            ],
            "location_maps": [
                "Does the feature need approximate, precise, foreground, background, or geofencing location access?",
                "What map provider, update frequency, battery limit, and retention policy should be used?",
            ],
            "performance": [
                (
                    "Which metric is failing: startup, jank, memory, battery, recomposition, database, network, "
                    "or build time?"
                ),
                "Do you have baseline traces, devices/API levels, or benchmark thresholds to preserve?",
            ],
            "security_privacy": [
                "Which tokens, PII, secrets, logs, backups, screenshots, or network paths contain sensitive data?",
                (
                    "Are Keystore, encrypted storage, network security config, certificate pinning, or log redaction "
                    "required?"
                ),
            ],
            "dependency_injection": [
                (
                    "Are you using Hilt or Dagger, and what scopes should app, Activity, ViewModel, repository, "
                    "and worker objects use?"
                ),
                "Which test fakes or module replacements are needed for local and instrumentation tests?",
            ],
            "modularization": [
                "What target module structure and dependency direction should the project enforce?",
                "Which package/resources should move first, and which Gradle tasks measure build impact?",
            ],
            "release_deployment": [
                (
                    "Which build variant, versioning scheme, signing setup, R8 rules, and artifact retention "
                    "requirements apply?"
                ),
                "What staged rollout, Crashlytics, analytics, feature flag, and rollback checks are required?",
            ],
            "analytics": [
                "What events, parameters, screens, funnels, and opt-out behavior should be tracked?",
                "Which fields are sensitive and must be excluded or redacted from analytics payloads?",
            ],
            "localization": [
                (
                    "Which locales, RTL languages, plural rules, date/time/currency formats, and fallback behavior "
                    "are required?"
                ),
                "Should screenshots or pseudo-locale tests be part of release verification?",
            ],
            "billing_payments": [
                (
                    "Which products, subscriptions, entitlement states, free trials, restore paths, and refund "
                    "behavior are required?"
                ),
                "How should pending purchases, acknowledgement failure, offline state, and account switching behave?",
            ],
            "deep_links": [
                (
                    "What URI patterns, route arguments, auth requirements, and fallback destinations should links "
                    "support?"
                ),
                "Should links be verified Android App Links with assetlinks.json, or internal-only intent filters?",
            ],
        }
        per_intent_limit = 3 if len(matched_intents) <= 1 else 2
        for intent in matched_intents:
            questions.extend(intent_questions.get(intent, [])[:per_intent_limit])
        if not matched_intents:
            questions.append("Which layer should be prioritized first: UI, data, or testing?")
        question_limit = RuleBasedAndroidPlanner._question_limit(depth, matched_intents)
        if RuleBasedAndroidPlanner._contains_any(
            normalized_prompt,
            {
                "sdk",
                "minimum sdk",
                "min sdk",
                "target sdk",
                "api level",
                "android 13",
                "android 14",
                "android 15",
                "gradle",
                "agp",
                "release",
            },
        ):
            questions.append("What minSdk, targetSdk, Kotlin, and AGP versions must the plan preserve?")
        if depth in {"high", "xhigh"} and len(RuleBasedAndroidPlanner._dedupe(questions)) < question_limit:
            questions.append("Which app architecture and dependency injection pattern should this preserve?")
        if depth == "xhigh" and len(RuleBasedAndroidPlanner._dedupe(questions)) < question_limit:
            questions.append(
                "Which lifecycle, accessibility, analytics, and rollout constraints must be verified before release?"
            )
        return RuleBasedAndroidPlanner._dedupe(questions)[:question_limit]

    @staticmethod
    def _question_limit(depth: PlannerDepth, matched_intents: List[str]) -> int:
        if not matched_intents:
            return {"low": 2, "medium": 3, "high": 4, "xhigh": 4}[depth]
        if len(matched_intents) > 1:
            return {"low": 3, "medium": 4, "high": 6, "xhigh": 6}[depth]
        return {"low": 3, "medium": 4, "high": 5, "xhigh": 5}[depth]
