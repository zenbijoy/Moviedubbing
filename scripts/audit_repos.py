"""Audit script to fetch metadata and core repository files for the 41 primary dubbing repos."""

import json
import os
import time
import urllib.error
import urllib.request

REPOS = [
    # A1. Pipelines & apps
    "liuzhao1225/YouDub-webui",
    "kadirb4rut/video-dubbing-translator",
    "langswap-app/langswap",
    "jianchang512/pyvideotrans",
    "zast57/ZastTranslate",
    "DjebrilSVN/Ai-Vedio-Dubbing",
    "stronghamjji/PersoDub",
    "johunsang/kekedubing",
    "shyhirt/AutoDub",
    "mazzasaverio/youtube-auto-dub",
    "timoncool/dub-studio",
    "R3gm/SoniTranslate",
    "jsfan3/autodub-local",
    "akshinmrv/Voxa",
    "lukaszliniewicz/Subdub",
    "lukaszliniewicz/Pandrator",
    "medahmedkrichen/ViDubb",
    "yaranbarzi/aigolden-dubbing",
    "Badri467/DubFlow",
    "xiesx123/CreatorBox",
    "Supan-Roy/Jupiter-Player",
    "Nik-Kras/voice_ukr_to_eng",
    "Amankumar321/AI-Dubber",
    "DablewCodes/voicevoyage.ai",
    "g33k0b1/Dubbing-World",
    "sahandghavidel/ai-video-editor",
    # A2. Lip-sync / research-style
    "Syedjunaid30/Video_Dubbing_with_ML_driven_Lip_Synchronization",
    "M-SRIKAR-VARDHAN/speech-to-speech-with-lipsync",
    "grayhatdevelopers/deepdub",
    "NISHAKAR06/VoiceFusionAi-ML",
    "ElsebaiyMohamed/Modablag",
    "Shirajuki/cuddly-journey",
    # A3. Components & APIs
    "facebookresearch/demucs",
    "TencentARC/AudioStory",
    "google-marketing-solutions/ariel",
    "allvoicelab/allvoicelab",
    "allvoicelab/AllVoiceLab-MCP",
    "perso-ai/perso-dubbing-plugin",
    "cr2007/cambai-python",
    # A4. Adjacent
    "koesan/ReManga_web",
    "koesan/Evoars",
]

OUTPUT_DIR = "dubbing-research/data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

headers = {
    "User-Agent": "Antigravity-Research-Auditor/1.0",
    "Accept": "application/vnd.github.v3+json",
}

results = {}

for repo in REPOS:
    slug = repo.replace("/", "__")
    repo_file = os.path.join(OUTPUT_DIR, f"{slug}.json")
    print(f"Auditing {repo}...")

    repo_info = {"repo": repo, "status": "ok"}
    try:
        # Fetch GitHub repo metadata
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            repo_info["stars"] = data.get("stargazers_count", 0)
            repo_info["updated_at"] = data.get("updated_at", "")
            repo_info["pushed_at"] = data.get("pushed_at", "")
            repo_info["license"] = (
                data.get("license", {}).get("spdx_id") if data.get("license") else "None"
            )
            repo_info["archived"] = data.get("archived", False)
            repo_info["open_issues"] = data.get("open_issues_count", 0)
            repo_info["description"] = data.get("description", "")
            default_branch = data.get("default_branch", "main")
            repo_info["default_branch"] = default_branch
    except urllib.error.HTTPError as e:
        repo_info["status"] = f"HTTP {e.code}"
        print(f"  Error fetching metadata: {e}")
        default_branch = "main"
    except Exception as e:
        repo_info["status"] = str(e)
        print(f"  Error: {e}")
        default_branch = "main"

    # Fetch README
    readme_content = ""
    for b in [default_branch, "main", "master"]:
        for name in ["README.md", "README.en.md", "readme.md"]:
            url = f"https://raw.githubusercontent.com/{repo}/{b}/{name}"
            try:
                r = urllib.request.Request(url, headers={"User-Agent": "Antigravity"})
                with urllib.request.urlopen(r, timeout=8) as resp:
                    readme_content = resp.read().decode("utf-8", errors="ignore")
                    break
            except Exception:
                continue
        if readme_content:
            break
    repo_info["readme"] = readme_content[:15000]

    with open(repo_file, "w", encoding="utf-8") as f:
        json.dump(repo_info, f, indent=2)

    time.sleep(0.4)

print("Audit data collection finished!")
