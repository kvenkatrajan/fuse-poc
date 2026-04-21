"""
Filesystem projector — writes Azure resource data as a local directory tree.

This is the core of the FUSE POC: it takes a list of Azure resources and their
analyzed relationships and projects them onto the filesystem so that standard
tools (find, grep, diff, Get-ChildItem) can be used for analysis.
"""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

from .relationships import friendly_type, resource_key


def _sanitize_path(name: str) -> str:
    """Sanitize a string for use as a Windows/Linux directory or file name."""
    # Replace characters invalid on Windows
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove trailing dots/spaces (Windows restriction)
    sanitized = sanitized.rstrip(". ")
    return sanitized or "_unnamed"


def _short_sub_name(subscription: str) -> str:
    """Shorten subscription name to avoid Windows MAX_PATH issues.

    Long subscription names like 'GithubCopilotForAzure-Testing' blow up path
    lengths on Windows. We keep a recognizable prefix + 6-char hash for
    uniqueness while capping the directory name at 20 characters.
    """
    sanitized = _sanitize_path(subscription)
    if len(sanitized) <= 20:
        return sanitized
    prefix = sanitized[:12].rstrip("-_ ")
    suffix = hashlib.sha256(subscription.encode()).hexdigest()[:6]
    return f"{prefix}-{suffix}"


def project_to_filesystem(
    output_dir: Path,
    subscription: str,
    resources: List[dict],
    edges: List[Tuple[str, str, str]],
    orphans: List[dict],
):
    """
    Write the full filesystem projection.

    Directory structure:
      {output_dir}/
        {short-sub-name}/
          {rg}/
            {resource-type}/
              {resource-name}/
                properties.json
                attached-to.txt       (for attachable resources)
                _CANDIDATE_ORPHAN     (marker file, if orphaned)
                orphan-reason.txt     (if orphaned)
                deps/                 (.ref files — depends-on)
                rdeps/                (.ref files — depended-by)
          _sub_name.txt               (full subscription name)
          orphaned-resources.txt
          dependency-graph.md
    """
    sub_dir = output_dir / _short_sub_name(subscription)

    # Write full subscription name for traceability
    os.makedirs(sub_dir, exist_ok=True)
    with open(sub_dir / "_sub_name.txt", "w", encoding="utf-8") as f:
        f.write(subscription)

    # Build lookup structures
    orphan_keys = {resource_key(o["resource"]) for o in orphans}
    orphan_map = {resource_key(o["resource"]): o for o in orphans}

    # Build depends-on and depended-by maps
    depends_on: Dict[str, List[Tuple[str, str]]] = {}  # key → [(target_key, label)]
    depended_by: Dict[str, List[Tuple[str, str]]] = {}  # key → [(source_key, label)]
    for src, tgt, label in edges:
        depends_on.setdefault(src, []).append((tgt, label))
        depended_by.setdefault(tgt, []).append((src, label))

    # Key-to-resource lookup
    key_to_resource = {resource_key(r): r for r in resources}

    # Project each resource
    for r in resources:
        key = resource_key(r)
        rtype = r["type"].lower()
        type_dir = friendly_type(rtype)
        res_dir = sub_dir / _sanitize_path(r["resourceGroup"]) / type_dir / _sanitize_path(r["name"])

        os.makedirs(res_dir, exist_ok=True)

        # properties.json — compact but readable
        props_file = res_dir / "properties.json"
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump({
                "name": r["name"],
                "type": r["type"],
                "resourceGroup": r["resourceGroup"],
                "location": r.get("location", "unknown"),
                "properties": r.get("properties", {})
            }, f, indent=2)

        # attached-to.txt (for disks, NICs, PIPs)
        if rtype in (
            "microsoft.compute/disks",
            "microsoft.network/networkinterfaces",
            "microsoft.network/publicipaddresses",
        ):
            attached_file = res_dir / "attached-to.txt"
            deps = depends_on.get(key, [])
            if deps:
                targets = [f"{_name_from_key(t)} ({label})" for t, label in deps]
                with open(attached_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(targets))
            elif key in orphan_keys:
                with open(attached_file, "w", encoding="utf-8") as f:
                    f.write("CANDIDATE_ORPHAN")

        # _CANDIDATE_ORPHAN marker + reason
        if key in orphan_keys:
            marker = res_dir / "_CANDIDATE_ORPHAN"
            marker.touch()

            reason_file = res_dir / "orphan-reason.txt"
            info = orphan_map[key]
            with open(reason_file, "w", encoding="utf-8") as f:
                f.write(f"Reason: {info['reason']}\n")
                f.write(f"Confidence: {info['confidence']}\n")
                if info.get("estimated_waste"):
                    f.write(f"Estimated waste: {info['estimated_waste']}\n")

        # depends-on/ directory
        deps = depends_on.get(key, [])
        if deps:
            dep_dir = res_dir / "deps"
            os.makedirs(dep_dir, exist_ok=True)
            for target_key, label in deps:
                target_name = _name_from_key(target_key)
                ref_file = dep_dir / f"{_sanitize_path(target_name)}.ref"
                with open(ref_file, "w", encoding="utf-8") as f:
                    f.write(f"target: {target_key}\n")
                    f.write(f"relationship: {label}\n")

        # depended-by/ directory
        rev_deps = depended_by.get(key, [])
        if rev_deps:
            rev_dir = res_dir / "rdeps"
            os.makedirs(rev_dir, exist_ok=True)
            for source_key, label in rev_deps:
                source_name = _name_from_key(source_key)
                ref_file = rev_dir / f"{_sanitize_path(source_name)}.ref"
                with open(ref_file, "w", encoding="utf-8") as f:
                    f.write(f"source: {source_key}\n")
                    f.write(f"relationship: {label}\n")

    return sub_dir


def write_orphan_summary(sub_dir: Path, orphans: List[dict]):
    """Write the orphaned-resources.txt summary file."""
    summary_file = sub_dir / "orphaned-resources.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("  CANDIDATE ORPHANED RESOURCES\n")
        f.write("=" * 70 + "\n")
        f.write(f"\n  Found {len(orphans)} candidate orphan(s)\n")
        f.write("  NOTE: These are candidates — verify before deleting.\n\n")

        for i, o in enumerate(orphans, 1):
            r = o["resource"]
            f.write(f"  [{i}] {r['name']}\n")
            f.write(f"      Type:       {friendly_type(r['type'])}\n")
            f.write(f"      RG:         {r['resourceGroup']}\n")
            f.write(f"      Reason:     {o['reason']}\n")
            f.write(f"      Confidence: {o['confidence']}\n")
            if o.get("estimated_waste"):
                f.write(f"      Waste:      {o['estimated_waste']}\n")
            f.write("\n")

        f.write("-" * 70 + "\n")
        f.write("  To find these on the filesystem:\n")
        f.write("    PowerShell:  Get-ChildItem -Recurse -Filter '_CANDIDATE_ORPHAN'\n")
        f.write("    Bash:        find . -name '_CANDIDATE_ORPHAN'\n")
        f.write("-" * 70 + "\n")


def write_dependency_graph(sub_dir: Path, mermaid: str):
    """Write the dependency-graph.md file."""
    graph_file = sub_dir / "dependency-graph.md"
    with open(graph_file, "w", encoding="utf-8") as f:
        f.write("# Resource Dependency Graph\n\n")
        f.write("Visualize this diagram at https://mermaid.live or in any Mermaid-compatible viewer.\n\n")
        f.write("```mermaid\n")
        f.write(mermaid)
        f.write("\n```\n\n")
        f.write("## How to read this graph\n\n")
        f.write("- Arrows show dependency direction: **source** depends on **target**\n")
        f.write("- Edge labels describe the relationship type\n")
        f.write("- Resources with no incoming edges are leaf dependencies (safe to keep)\n")
        f.write("- Resources with many incoming `depended-by` edges are critical (risky to delete)\n\n")
        f.write("## Impact analysis\n\n")
        f.write("To check what depends on a specific resource:\n")
        f.write("```powershell\n")
        f.write("Get-ChildItem -Path '.\\<rg>\\<type>\\<name>\\rdeps\\' -Filter '*.ref'\n")
        f.write("```\n")


def _name_from_key(key: str) -> str:
    """Extract resource name from a resource key like 'rg/type/name'."""
    return key.rsplit("/", 1)[-1] if "/" in key else key
