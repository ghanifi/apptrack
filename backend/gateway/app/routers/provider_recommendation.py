"""
Optimal Provider Selection Router
===================================
Recommends the best build provider for a project based on historical build
performance data. Evaluates providers by average duration, success rate,
and cost, then applies weighted scoring based on the user's priority
(speed, cost, reliability, or balanced). Also provides framework
compatibility information.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case
from app.dependencies import get_current_user
from app.database import get_db
from app.models import Build, Project

router = APIRouter(prefix="/api/provider-recommendation", tags=["provider-recommendation"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider cost rates (USD per minute) — aligned with cost_prediction router
# ---------------------------------------------------------------------------

PROVIDER_COSTS: dict[str, dict[str, float]] = {
    "eas": {"android": 0.02, "ios": 0.04},
    "codemagic": {"android": 0.015, "ios": 0.035},
    "github_actions": {"android": 0.008, "ios": 0.08},
}

ALL_PROVIDERS = list(PROVIDER_COSTS.keys())
VALID_PLATFORMS = {"android", "ios"}
VALID_PRIORITIES = {"speed", "cost", "reliability", "balanced"}

# ---------------------------------------------------------------------------
# Priority weight distributions
# Weights for: (speed_weight, cost_weight, reliability_weight)
# Higher weight = more important. All weights should sum to 1.0.
# ---------------------------------------------------------------------------

PRIORITY_WEIGHTS: dict[str, dict[str, float]] = {
    "speed": {"speed": 0.60, "cost": 0.10, "reliability": 0.30},
    "cost": {"speed": 0.10, "cost": 0.60, "reliability": 0.30},
    "reliability": {"speed": 0.15, "cost": 0.10, "reliability": 0.75},
    "balanced": {"speed": 0.35, "cost": 0.30, "reliability": 0.35},
}

# ---------------------------------------------------------------------------
# Framework-provider compatibility matrix
# Score: 1.0 = best fit, 0.7 = good, 0.4 = acceptable, 0.1 = poor
# ---------------------------------------------------------------------------

FRAMEWORK_COMPATIBILITY: dict[str, dict[str, dict]] = {
    "expo": {
        "eas": {
            "score": 1.0,
            "note": "EAS Build is Expo's native cloud build service. Best integration, fastest setup.",
        },
        "codemagic": {
            "score": 0.7,
            "note": "Codemagic supports Expo projects with custom configuration.",
        },
        "github_actions": {
            "score": 0.4,
            "note": "GitHub Actions requires manual Expo build setup and can be slower for iOS.",
        },
    },
    "react_native": {
        "eas": {
            "score": 0.9,
            "note": "EAS Build supports bare React Native projects well.",
        },
        "codemagic": {
            "score": 0.8,
            "note": "Codemagic has strong React Native support with pre-configured workflows.",
        },
        "github_actions": {
            "score": 0.5,
            "note": "GitHub Actions works but requires more setup for React Native builds.",
        },
    },
    "flutter": {
        "eas": {
            "score": 0.3,
            "note": "EAS Build is not designed for Flutter projects. Consider alternatives.",
        },
        "codemagic": {
            "score": 1.0,
            "note": "Codemagic is the recommended CI/CD for Flutter, built by the Flutter community.",
        },
        "github_actions": {
            "score": 0.6,
            "note": "GitHub Actions supports Flutter with community actions.",
        },
    },
    "swift": {
        "eas": {
            "score": 0.1,
            "note": "EAS Build does not support native Swift/Xcode projects.",
        },
        "codemagic": {
            "score": 0.8,
            "note": "Codemagic provides macOS machines with Xcode for native iOS builds.",
        },
        "github_actions": {
            "score": 0.9,
            "note": "GitHub Actions macOS runners are well-suited for native Swift projects.",
        },
    },
    "kotlin": {
        "eas": {
            "score": 0.1,
            "note": "EAS Build does not support native Kotlin/Android projects.",
        },
        "codemagic": {
            "score": 0.7,
            "note": "Codemagic supports native Android/Kotlin builds.",
        },
        "github_actions": {
            "score": 0.9,
            "note": "GitHub Actions Linux runners are cost-effective for native Android builds.",
        },
    },
    "unknown": {
        "eas": {
            "score": 0.3,
            "note": "EAS Build is specialized for Expo/React Native projects.",
        },
        "codemagic": {
            "score": 0.6,
            "note": "Codemagic supports multiple mobile frameworks.",
        },
        "github_actions": {
            "score": 0.7,
            "note": "GitHub Actions is a general-purpose CI/CD that works with most frameworks.",
        },
    },
}


def _calculate_score(
    avg_duration_seconds: float,
    success_rate: float,
    cost_per_minute: float,
    avg_duration_minutes: float,
    compatibility_score: float,
    weights: dict[str, float],
) -> dict:
    """
    Calculate a weighted composite score for a provider.

    Normalizes each metric to a 0-1 scale where higher is better:
    - Speed score: Inverse of duration, normalized to reasonable range (0-30 min).
    - Cost score: Inverse of estimated cost per build, normalized.
    - Reliability score: Directly from success_rate (already 0-1).
    - Compatibility is applied as a multiplier on the final score.

    Args:
        avg_duration_seconds: Average build duration in seconds.
        success_rate: Build success rate as a fraction (0.0 to 1.0).
        cost_per_minute: USD cost per minute.
        avg_duration_minutes: Average build duration in minutes.
        compatibility_score: Framework compatibility score (0.0 to 1.0).
        weights: Dict with speed, cost, reliability weights.

    Returns:
        Dict with individual scores and final composite score.
    """
    # Speed score: faster is better. 0 minutes = 1.0, 30+ minutes = ~0
    max_minutes = 30.0
    speed_score = max(0.0, 1.0 - (avg_duration_minutes / max_minutes))

    # Cost score: cheaper is better.
    estimated_build_cost = avg_duration_minutes * cost_per_minute
    max_cost = 5.0  # $5 per build as the upper bound
    cost_score = max(0.0, 1.0 - (estimated_build_cost / max_cost))

    # Reliability score: direct from success rate
    reliability_score = success_rate

    # Weighted composite
    composite = (
        speed_score * weights["speed"]
        + cost_score * weights["cost"]
        + reliability_score * weights["reliability"]
    )

    # Apply compatibility as a multiplier (minimum floor of 0.5 to avoid zeroing out)
    compatibility_factor = max(0.5, compatibility_score)
    final_score = round(composite * compatibility_factor, 4)

    return {
        "speed_score": round(speed_score, 4),
        "cost_score": round(cost_score, 4),
        "reliability_score": round(reliability_score, 4),
        "compatibility_score": round(compatibility_score, 2),
        "composite_score": round(composite, 4),
        "final_score": final_score,
    }


def _explain_recommendation(
    recommended: str,
    scores: dict[str, dict],
    priority: str,
    framework: str,
) -> str:
    """
    Generate a human-readable explanation of why a provider was recommended.

    Args:
        recommended: The recommended provider name.
        scores: Dict of provider -> score breakdown.
        priority: The user's priority mode.
        framework: The project framework.

    Returns:
        Human-readable explanation string.
    """
    rec_scores = scores.get(recommended, {})
    final = rec_scores.get("final_score", 0)

    parts = [f"{recommended.upper()} is recommended for your {framework} project"]
    parts.append(f"with a final score of {final:.2f} (priority: {priority}).")

    if priority == "speed":
        parts.append(f"Speed score: {rec_scores.get('speed_score', 0):.2f}.")
    elif priority == "cost":
        parts.append(f"Cost efficiency score: {rec_scores.get('cost_score', 0):.2f}.")
    elif priority == "reliability":
        parts.append(f"Reliability score: {rec_scores.get('reliability_score', 0):.2f}.")
    else:
        parts.append("Balanced across speed, cost, and reliability.")

    compat = rec_scores.get("compatibility_score", 0)
    if compat >= 0.9:
        parts.append(f"Excellent framework compatibility ({compat:.1f}/1.0).")
    elif compat >= 0.6:
        parts.append(f"Good framework compatibility ({compat:.1f}/1.0).")
    elif compat >= 0.3:
        parts.append(f"Acceptable framework compatibility ({compat:.1f}/1.0).")
    else:
        parts.append(f"Limited framework compatibility ({compat:.1f}/1.0) — consider alternatives.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.get("/recommend/{project_id}")
async def recommend_provider(
    project_id: str,
    platform: str = Query("android", description="Target platform: android or ios"),
    priority: str = Query("balanced", description="Priority mode: speed, cost, reliability, or balanced"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Recommend the optimal build provider for a project based on historical performance.

    Analyzes build history across all providers for the given project and platform,
    calculating scores based on speed, cost, and reliability. The priority parameter
    controls the weight distribution. Framework compatibility is also factored in.

    - **project_id**: UUID of the project.
    - **platform**: Target platform (android or ios).
    - **priority**: Optimization priority (speed, cost, reliability, balanced).
    """
    # Validate inputs
    if platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform '{platform}'. Must be one of: {', '.join(sorted(VALID_PLATFORMS))}",
        )
    if priority not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}",
        )

    # Verify project ownership
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project or project.owner_id != current_user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    framework = project.framework or "unknown"
    weights = PRIORITY_WEIGHTS[priority]

    # Query build stats grouped by provider
    provider_stats: dict[str, dict] = {}

    for provider in ALL_PROVIDERS:
        # Get completed builds for this provider
        builds_result = await db.execute(
            select(Build).where(
                and_(
                    Build.project_id == project_id,
                    Build.platform == platform,
                    Build.provider == provider,
                    Build.status.in_(["success", "failed"]),
                )
            ).order_by(Build.created_at.desc()).limit(50)
        )
        builds = builds_result.scalars().all()

        if not builds:
            # No history for this provider — use compatibility data only
            compat_data = FRAMEWORK_COMPATIBILITY.get(framework, FRAMEWORK_COMPATIBILITY["unknown"])
            provider_compat = compat_data.get(provider, {"score": 0.5, "note": "No data"})
            cost_rate = PROVIDER_COSTS.get(provider, {}).get(platform, 0.05)

            provider_stats[provider] = {
                "has_history": False,
                "total_builds": 0,
                "success_count": 0,
                "failed_count": 0,
                "success_rate": 0.0,
                "avg_duration_seconds": None,
                "estimated_cost_per_build_usd": None,
                "cost_per_minute_usd": cost_rate,
                "compatibility": provider_compat,
                "scores": _calculate_score(
                    avg_duration_seconds=600,  # assume 10 min default
                    success_rate=0.5,  # no data = assume 50%
                    cost_per_minute=cost_rate,
                    avg_duration_minutes=10.0,
                    compatibility_score=provider_compat["score"],
                    weights=weights,
                ),
            }
            continue

        # Calculate stats from actual build history
        total = len(builds)
        success_count = sum(1 for b in builds if b.status == "success")
        failed_count = total - success_count
        success_rate = success_count / total if total > 0 else 0.0

        # Duration stats from successful builds with timestamps
        successful_with_duration = [
            b for b in builds
            if b.status == "success"
            and b.started_at is not None
            and b.finished_at is not None
            and b.finished_at > b.started_at
        ]

        if successful_with_duration:
            durations = [(b.finished_at - b.started_at).total_seconds() for b in successful_with_duration]
            avg_duration = sum(durations) / len(durations)
        else:
            avg_duration = 600.0  # 10 min default

        avg_duration_minutes = avg_duration / 60.0
        cost_rate = PROVIDER_COSTS.get(provider, {}).get(platform, 0.05)
        estimated_cost = round(avg_duration_minutes * cost_rate, 4)

        compat_data = FRAMEWORK_COMPATIBILITY.get(framework, FRAMEWORK_COMPATIBILITY["unknown"])
        provider_compat = compat_data.get(provider, {"score": 0.5, "note": "No data"})

        scores = _calculate_score(
            avg_duration_seconds=avg_duration,
            success_rate=success_rate,
            cost_per_minute=cost_rate,
            avg_duration_minutes=avg_duration_minutes,
            compatibility_score=provider_compat["score"],
            weights=weights,
        )

        provider_stats[provider] = {
            "has_history": True,
            "total_builds": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": round(success_rate, 4),
            "avg_duration_seconds": round(avg_duration, 1),
            "estimated_cost_per_build_usd": estimated_cost,
            "cost_per_minute_usd": cost_rate,
            "compatibility": provider_compat,
            "scores": scores,
        }

    # Determine recommended provider (highest final_score)
    if not provider_stats:
        raise HTTPException(
            status_code=500,
            detail="Unable to compute provider recommendations.",
        )

    recommended = max(
        provider_stats.keys(),
        key=lambda p: provider_stats[p]["scores"]["final_score"],
    )

    # Build scores-only dict for explanation
    all_scores = {p: stats["scores"] for p, stats in provider_stats.items()}
    reasoning = _explain_recommendation(recommended, all_scores, priority, framework)

    # Sort providers by final score for ranking
    ranked = sorted(
        provider_stats.keys(),
        key=lambda p: provider_stats[p]["scores"]["final_score"],
        reverse=True,
    )

    logger.info(
        "Provider recommendation: project=%s platform=%s priority=%s recommended=%s score=%.4f",
        project_id, platform, priority, recommended,
        provider_stats[recommended]["scores"]["final_score"],
    )

    return {
        "project_id": project_id,
        "framework": framework,
        "platform": platform,
        "priority": priority,
        "weights": weights,
        "recommended_provider": recommended,
        "reasoning": reasoning,
        "ranking": ranked,
        "providers": provider_stats,
    }


@router.get("/compatibility/{framework}")
async def framework_compatibility(
    framework: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get framework compatibility information for all providers.

    Returns the compatibility score and notes for each provider with the
    given framework, helping users understand which providers work best
    with their technology stack.

    - **framework**: Framework name (expo, react_native, flutter, swift, kotlin, unknown).
    """
    framework_lower = framework.lower()

    # Normalize common names
    framework_aliases = {
        "react-native": "react_native",
        "reactnative": "react_native",
        "swiftui": "swift",
        "objective-c": "swift",
        "objc": "swift",
        "java": "kotlin",
        "android": "kotlin",
    }
    normalized = framework_aliases.get(framework_lower, framework_lower)

    compat_data = FRAMEWORK_COMPATIBILITY.get(normalized)
    if not compat_data:
        return {
            "framework": framework,
            "normalized": normalized,
            "known": False,
            "providers": FRAMEWORK_COMPATIBILITY.get("unknown", {}),
            "message": f"Framework '{framework}' is not in our compatibility database. "
                       "Showing default compatibility scores.",
        }

    # Sort providers by compatibility score descending
    sorted_providers = sorted(
        compat_data.items(),
        key=lambda x: x[1]["score"],
        reverse=True,
    )

    best_provider = sorted_providers[0][0] if sorted_providers else None

    return {
        "framework": framework,
        "normalized": normalized,
        "known": True,
        "best_provider": best_provider,
        "providers": dict(sorted_providers),
    }
