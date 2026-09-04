import base64
import json
import os
import re
from collections import defaultdict

import requests
from rapidfuzz import fuzz

from skills import SKILL_ALIASES

GITHUB_API = "https://api.github.com"

# Optional: set GITHUB_TOKEN in the environment to raise the rate limit
# from 60 req/hr (unauthenticated) to 5000 req/hr. Analysis works without
# it, it's just easy to hit the ceiling scanning multiple repos.
_TOKEN = os.environ.get("GITHUB_TOKEN")
_HEADERS = {"Accept": "application/vnd.github+json"}
if _TOKEN:
    _HEADERS["Authorization"] = f"Bearer {_TOKEN}"

MAX_REPOS_SCANNED = 15          # cap to stay inside rate limits / keep it fast
MAX_FILE_BYTES = 60_000         # skip huge dependency/config files


class GithubRateLimitError(Exception):
    """Raised when GitHub's API returns a rate-limit response, so callers
    can surface a clear 429 instead of misreading it as 'not found' or
    silently returning empty results."""
    pass


def _github_get(url: str, **kwargs):
    """Wrapper around requests.get that raises GithubRateLimitError on
    rate-limit responses. All GitHub API calls in this module should go
    through this instead of calling requests.get directly."""
    timeout = kwargs.pop("timeout", 10)
    r = requests.get(url, headers=_HEADERS, timeout=timeout, **kwargs)
    if r.status_code == 429 or (
        r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0"
    ):
        raise GithubRateLimitError(
            "GitHub API rate limit exceeded. Set GITHUB_TOKEN to raise the limit."
        )
    return r


# -- Reverse skill-alias lookup (built once) -----------------------

_ALIAS_TO_SKILL = {}
for canonical, aliases in SKILL_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_SKILL[alias.lower().strip()] = canonical


def _normalize_token(token: str) -> str:
    """Strip version pins, scopes, and punctuation noise from a raw
    package/dependency name so it has a chance of matching SKILL_ALIASES."""
    token = token.lower().strip()
    token = token.split("==")[0].split(">=")[0].split("<=")[0]
    token = token.split("~=")[0].split("^")[0].split("@")[0] if not token.startswith("@") else token
    token = re.sub(r"[\[\](){}<>~^]", "", token)
    token = token.strip().strip(",").strip()
    return token


def match_to_canonical_skill(raw_token: str) -> str | None:
    """Map a raw string (package name, topic, badge text...) to a canonical
    skill from SKILL_ALIASES, exact first, then fuzzy fallback."""
    token = _normalize_token(raw_token)
    if not token:
        return None
    if token in _ALIAS_TO_SKILL:
        return _ALIAS_TO_SKILL[token]
    # scoped npm packages: @org/pkg -> pkg
    if "/" in token:
        tail = token.split("/")[-1]
        if tail in _ALIAS_TO_SKILL:
            return _ALIAS_TO_SKILL[tail]
    # fuzzy fallback — catches things like "postgres14", "react-router" etc.
    best_skill, best_score = None, 0
    for alias, skill in _ALIAS_TO_SKILL.items():
        score = fuzz.partial_ratio(alias, token)
        if score > best_score:
            best_score, best_skill = score, skill
    return best_skill if best_score >= 90 else None


# -- GitHub API helpers ---------------------------------------------

def verify_github_user(username: str) -> dict | None:
    """Confirm a GitHub username exists. Returns the public profile dict
    (name, bio, public_repos, followers...) or None if it doesn't exist.
    Raises GithubRateLimitError if GitHub's API is rate-limited."""
    r = _github_get(f"{GITHUB_API}/users/{username}")
    if r.status_code != 200:
        return None
    return r.json()


def extract_github_username_from_text(resume_text: str) -> str | None:
    """Look for a github.com/<username> URL in resume text, used only to
    pre-fill the link field — never trusted without user confirmation +
    verify_github_user()."""
    blacklist = {
        "login", "settings", "marketplace", "sponsors", "features", "about",
        "pricing", "topics", "collections", "trending", "issues", "pulls",
        "notifications", "orgs", "apps", "explore", "join", "site"
    }
    matches = re.findall(r"github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]){0,38})", resume_text)
    for m in matches:
        candidate = m.strip("/").lower()
        if candidate not in blacklist:
            return m.strip("/")
    return None


def _get_repos(username: str) -> list:
    """Raises GithubRateLimitError if GitHub's API is rate-limited."""
    r = _github_get(
        f"{GITHUB_API}/users/{username}/repos",
        params={"per_page": 100, "sort": "updated", "type": "owner"},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    repos = [repo for repo in r.json() if not repo.get("fork")]
    # prioritize repos that look most substantial: stars, then recency
    repos.sort(key=lambda x: (x.get("stargazers_count", 0), x.get("updated_at", "")), reverse=True)
    return repos[:MAX_REPOS_SCANNED]


def _get_languages(username: str, repo_name: str) -> dict:
    """Raises GithubRateLimitError if GitHub's API is rate-limited."""
    r = _github_get(f"{GITHUB_API}/repos/{username}/{repo_name}/languages")
    return r.json() if r.status_code == 200 else {}


def _get_repo_tree(username: str, repo_name: str, default_branch: str) -> list:
    """Full recursive file listing for a repo via the git trees API.
    Raises GithubRateLimitError if GitHub's API is rate-limited."""
    r = _github_get(
        f"{GITHUB_API}/repos/{username}/{repo_name}/git/trees/{default_branch}",
        params={"recursive": "1"},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    return [item["path"] for item in r.json().get("tree", []) if item.get("type") == "blob"]


def _get_file_content(username: str, repo_name: str, path: str) -> str | None:
    """Raises GithubRateLimitError if GitHub's API is rate-limited."""
    r = _github_get(f"{GITHUB_API}/repos/{username}/{repo_name}/contents/{path}")
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("size", 0) > MAX_FILE_BYTES or data.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


# -- Dependency / config file parsers --------------------------------
# filename match (exact basename or path substring) -> parser(content) -> [raw tokens]

def _parse_package_json(content: str) -> list:
    try:
        data = json.loads(content)
    except Exception:
        return []
    tokens = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        tokens.extend((data.get(key) or {}).keys())
    return tokens


def _parse_requirements_txt(content: str) -> list:
    tokens = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        tokens.append(line)
    return tokens


def _parse_pipfile(content: str) -> list:
    tokens = []
    in_deps = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("[") :
            in_deps = "packages" in line.lower()
            continue
        if in_deps and "=" in line:
            tokens.append(line.split("=")[0].strip().strip('"'))
    return tokens


def _parse_cargo_toml(content: str) -> list:
    tokens = []
    in_deps = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_deps = "dependencies" in line.lower()
            continue
        if in_deps and "=" in line:
            tokens.append(line.split("=")[0].strip().strip('"'))
    return tokens


def _parse_go_mod(content: str) -> list:
    tokens = []
    for line in content.splitlines():
        line = line.strip()
        m = re.match(r"^([\w./-]+)\s+v[\d.]+", line)
        if m:
            tokens.append(m.group(1).split("/")[-1])
    return tokens


def _parse_gemfile(content: str) -> list:
    return re.findall(r'gem\s+["\']([\w-]+)["\']', content)


def _parse_gradle(content: str) -> list:
    tokens = []
    for m in re.finditer(r'["\']([\w.\-]+):([\w.\-]+):[\w.\-]+["\']', content):
        tokens.append(m.group(2))
    return tokens


def _parse_pom_xml(content: str) -> list:
    return re.findall(r"<artifactId>([\w.\-]+)</artifactId>", content)


DEPENDENCY_PARSERS = {
    "package.json": _parse_package_json,
    "requirements.txt": _parse_requirements_txt,
    "pipfile": _parse_pipfile,
    "cargo.toml": _parse_cargo_toml,
    "go.mod": _parse_go_mod,
    "gemfile": _parse_gemfile,
    "build.gradle": _parse_gradle,
    "pom.xml": _parse_pom_xml,
}

# path substring -> skill(s) it implies directly (no parsing needed)
CONFIG_FILE_SKILLS = {
    "dockerfile": ["docker"],
    "docker-compose": ["docker"],
    ".github/workflows/": ["ci/cd"],
    ".gitlab-ci.yml": ["ci/cd"],
    "jenkinsfile": ["ci/cd"],
    "k8s/": ["kubernetes"],
    "kubernetes/": ["kubernetes"],
    ".tf": ["aws", "azure", "gcp"],  # terraform — only weak signal, handled below
}


def _scan_repo_files(username: str, repo_name: str, file_paths: list) -> tuple[list, list]:
    """Returns (dependency_skill_records, config_skill_records) for one repo."""
    dep_records = []
    cfg_records = []

    lower_paths = {p.lower(): p for p in file_paths}

    # dependency files — match on basename
    for path_lower, path_actual in lower_paths.items():
        basename = path_lower.rsplit("/", 1)[-1]
        if basename in DEPENDENCY_PARSERS:
            content = _get_file_content(username, repo_name, path_actual)
            if not content:
                continue
            for raw_token in DEPENDENCY_PARSERS[basename](content):
                skill = match_to_canonical_skill(raw_token)
                if skill:
                    dep_records.append({"skill": skill, "source": "dependency", "repo": repo_name})

    # config files — match on path substring, no parsing needed
    for path_lower, path_actual in lower_paths.items():
        for pattern, implied_skills in CONFIG_FILE_SKILLS.items():
            if pattern in path_lower:
                for skill in implied_skills:
                    if skill in ("aws", "azure", "gcp") and pattern == ".tf":
                        continue  # too ambiguous to credit without content inspection
                    cfg_records.append({"skill": skill, "source": "config_file", "repo": repo_name})

    return dep_records, cfg_records


def _get_readme_text(username: str, repo_name: str) -> str:
    """Raises GithubRateLimitError if GitHub's API is rate-limited."""
    r = _github_get(f"{GITHUB_API}/repos/{username}/{repo_name}/readme")
    if r.status_code != 200:
        return ""
    data = r.json()
    if data.get("encoding") != "base64":
        return ""
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return ""


# -- Per-repo + aggregate analysis ------------------------------------

def analyze_repo(username: str, repo: dict) -> dict:
    repo_name = repo["name"]
    default_branch = repo.get("default_branch", "main")

    languages = _get_languages(username, repo_name)
    file_paths = _get_repo_tree(username, repo_name, default_branch)
    dep_records, cfg_records = _scan_repo_files(username, repo_name, file_paths)

    topic_records = []
    for topic in (repo.get("topics") or []):
        skill = match_to_canonical_skill(topic)
        if skill:
            topic_records.append({"skill": skill, "source": "topic", "repo": repo_name})

    readme_text = _get_readme_text(username, repo_name)
    readme_records = []
    if readme_text:
        # look for skill names mentioned in the README (light touch — one
        # record per skill per repo, not per occurrence)
        seen = set()
        for canonical in SKILL_ALIASES:
            for alias in SKILL_ALIASES[canonical]:
                if re.search(rf"\b{re.escape(alias)}\b", readme_text, re.IGNORECASE):
                    if canonical not in seen:
                        readme_records.append({"skill": canonical, "source": "readme", "repo": repo_name})
                        seen.add(canonical)
                    break

    language_records = []
    for lang in languages:
        skill = match_to_canonical_skill(lang)
        if skill:
            language_records.append({"skill": skill, "source": "language", "repo": repo_name})

    return {
        "repo_name": repo_name,
        "languages": languages,
        "records": dep_records + cfg_records + topic_records + readme_records + language_records,
    }


def _tier_for_sources(sources: set) -> str:
    """implemented = real usage evidence (dependency / config / language).
    declared = only self-tagged (topic / readme) with no usage evidence."""
    if sources & {"dependency", "config_file", "language"}:
        return "implemented"
    return "declared"


def build_profile(username: str) -> dict:
    """Full pipeline: verify -> fetch repos -> analyze each -> aggregate.
    Returns everything needed to populate github_profiles + github_skills.
    Raises GithubRateLimitError if GitHub's API is rate-limited partway
    through — callers should surface that as a 429, not treat a partial
    profile as complete."""
    user = verify_github_user(username)
    if not user:
        return None

    repos = _get_repos(username)

    all_records = []          # flat list of {skill, source, repo}
    language_bytes = defaultdict(int)
    repo_summaries = []

    for repo in repos:
        analysis = analyze_repo(username, repo)
        all_records.extend(analysis["records"])
        for lang, byte_count in analysis["languages"].items():
            language_bytes[lang] += byte_count
        repo_summaries.append({
            "name": repo["name"],
            "stars": repo.get("stargazers_count", 0),
            "desc": repo.get("description") or "",
        })

    # -- tier + dedupe skills (best source per skill across all repos, but
    #    keep one row per (skill, source, repo) for traceability) --
    skill_best_sources = defaultdict(set)
    for rec in all_records:
        skill_best_sources[rec["skill"]].add(rec["source"])

    skill_rows = []
    for rec in all_records:
        tier = _tier_for_sources(skill_best_sources[rec["skill"]])
        skill_rows.append({**rec, "tier": tier})

    # de-duplicate identical (skill, source, repo) rows
    seen = set()
    deduped_rows = []
    for row in skill_rows:
        key = (row["skill"], row["source"], row["repo"])
        if key not in seen:
            seen.add(key)
            deduped_rows.append(row)

    # -- top languages (by total bytes across scanned repos) --
    total_bytes = sum(language_bytes.values()) or 1
    top_languages = [
        {"name": lang, "pct": round(count / total_bytes * 100, 1)}
        for lang, count in sorted(language_bytes.items(), key=lambda x: x[1], reverse=True)[:6]
    ]

    # -- top repos (already sorted by stars/recency from _get_repos) --
    top_repos = sorted(repo_summaries, key=lambda r: r["stars"], reverse=True)[:5]

    # -- summary blurb --
    implemented_skills = sorted({r["skill"] for r in deduped_rows if r["tier"] == "implemented"})
    lang_names = [l["name"] for l in top_languages[:3]]
    summary_parts = []
    if lang_names:
        summary_parts.append(f"Primarily codes in {', '.join(lang_names)}")
    if implemented_skills:
        summary_parts.append(f"with hands-on evidence of {', '.join(implemented_skills[:5])}")
    summary_parts.append(f"across {len(repos)} public repositories")
    summary = " ".join(summary_parts).strip().capitalize() + "."

    return {
        "username": username,
        "summary": summary,
        "top_languages": top_languages,
        "repo_count": user.get("public_repos", len(repos)),
        "top_repos": top_repos,
        "skills": deduped_rows,   # [{skill, source, repo, tier}]
    }