#!/usr/bin/env python3
"""Check manifests, install rules, launch references, and description assets."""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

RESOURCE_DIRS = ("config", "launch", "mesh", "models", "param", "urdf", "worlds")
ROS_FIND_RE = re.compile(r"\$\(find\s+([A-Za-z0-9_]+)\)")
PACKAGE_URI_RE = re.compile(r"package://([A-Za-z0-9_]+)/([^\s'\"<>)]+)")
DAE_IMAGE_RE = re.compile(r"<init_from>([^<]+\.(?:jpe?g|png|tga|bmp))</init_from>", re.IGNORECASE)
CMAKE_PROJECT_RE = re.compile(r"\bproject\s*\(\s*([^\s)]+)", re.IGNORECASE)


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def add_error(errors, path, message):
    errors.append("{}: {}".format(path, message))


def package_index(root, errors):
    packages = {}
    for manifest in sorted(root.rglob("package.xml")):
        if ".git" in manifest.parts:
            continue
        try:
            xml_root = ET.parse(str(manifest)).getroot()
        except ET.ParseError as exc:
            add_error(errors, manifest, "invalid XML ({})".format(exc))
            continue
        name_element = xml_root.find("name")
        if name_element is None or not (name_element.text or "").strip():
            add_error(errors, manifest, "manifest has no package name")
            continue
        name = name_element.text.strip()
        if name in packages:
            add_error(errors, manifest, "duplicate package name {!r}".format(name))
        packages[name] = manifest.parent
    return packages


def check_manifest(package_name, package_dir, errors):
    manifest = package_dir / "package.xml"
    try:
        root = ET.parse(str(manifest)).getroot()
    except ET.ParseError:
        return

    required = ("version", "description", "maintainer", "license")
    for tag in required:
        element = root.find(tag)
        if element is None or not "".join(element.itertext()).strip():
            add_error(errors, manifest, "missing or empty <{}>".format(tag))

    cmake = package_dir / "CMakeLists.txt"
    if not cmake.is_file():
        add_error(errors, package_dir, "missing CMakeLists.txt")
        return
    match = CMAKE_PROJECT_RE.search(cmake.read_text(errors="replace"))
    if not match:
        add_error(errors, cmake, "missing project()")
    elif match.group(1) != package_name:
        add_error(
            errors,
            cmake,
            "project name {!r} does not match manifest {!r}".format(match.group(1), package_name),
        )


def check_install_rules(package_dir, errors):
    cmake = package_dir / "CMakeLists.txt"
    if not cmake.is_file():
        return
    cmake_text = cmake.read_text(errors="replace")
    if "install(" not in cmake_text:
        add_error(errors, cmake, "package has no install() rule")
        return
    for resource_dir in RESOURCE_DIRS:
        path = package_dir / resource_dir
        if path.is_dir() and not re.search(r"\b{}\b".format(re.escape(resource_dir)), cmake_text):
            add_error(
                errors,
                cmake,
                "{} resources exist but are not mentioned by an install rule".format(resource_dir),
            )


def manifest_dependencies(package_dir):
    root = ET.parse(str(package_dir / "package.xml")).getroot()
    dependency_tags = {
        "build_depend",
        "build_export_depend",
        "depend",
        "exec_depend",
    }
    return {
        (element.text or "").strip()
        for element in root
        if local_name(element.tag) in dependency_tags and (element.text or "").strip()
    }


def check_resource_dependencies(package_name, package_dir, errors):
    dependencies = manifest_dependencies(package_dir)
    references = set()
    launch_dir = package_dir / "launch"
    if launch_dir.is_dir() and "roslaunch" not in dependencies:
        add_error(errors, package_dir / "package.xml", "launch resources require an exec_depend on roslaunch")

    for resource_dir in RESOURCE_DIRS:
        directory = package_dir / resource_dir
        if not directory.is_dir():
            continue
        for source in directory.rglob("*"):
            if not source.is_file() or source.suffix not in (".launch", ".urdf", ".xacro", ".xml", ".dae"):
                continue
            text = source.read_text(errors="replace")
            references.update(ROS_FIND_RE.findall(text))
            references.update(package for package, unused in PACKAGE_URI_RE.findall(text))
            if source.suffix == ".launch":
                try:
                    launch_root = ET.parse(str(source)).getroot()
                except ET.ParseError:
                    continue
                for node in launch_root.iter("node"):
                    node_package = node.attrib.get("pkg", "")
                    if re.match(r"^[A-Za-z0-9_]+$", node_package):
                        references.add(node_package)

    references.discard(package_name)
    for reference in sorted(references - dependencies):
        add_error(
            errors,
            package_dir / "package.xml",
            "resource reference to {!r} has no package dependency".format(reference),
        )


def resolve_reference(package, relative, packages):
    if package not in packages:
        return None
    relative_path = PurePosixPath(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    return packages[package].joinpath(*relative_path.parts)


def check_references(source, packages, errors):
    text = source.read_text(errors="replace")

    for package, relative in PACKAGE_URI_RE.findall(text):
        target = resolve_reference(package, relative, packages)
        if package in packages and (target is None or not target.exists()):
            add_error(
                errors,
                source,
                "missing package URI target package://{}/{}".format(package, relative),
            )

    if source.suffix == ".dae":
        for relative in DAE_IMAGE_RE.findall(text):
            target = source.parent / relative
            if not target.exists():
                add_error(errors, source, "missing COLLADA texture {}".format(relative))

    # Resolve $(find package)/literal/path references. Stop before XML, shell, or
    # substitution delimiters so launch arguments remain intentionally dynamic.
    for package in packages:
        pattern = re.compile(
            r"\$\(find\s+{}\)/([^\s'\"<>)$]+)".format(re.escape(package))
        )
        for relative in pattern.findall(text):
            if "$(" in relative:
                continue
            target = resolve_reference(package, relative, packages)
            if target is None or not target.exists():
                add_error(
                    errors,
                    source,
                    "missing $(find {}) resource {}".format(package, relative),
                )


def check_xml(path, errors):
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError as exc:
        add_error(errors, path, "invalid XML ({})".format(exc))
        return
    if path.suffix == ".launch" and local_name(root.tag) != "launch":
        add_error(errors, path, "launch file root must be <launch>")
    if ".urdf" in path.name and local_name(root.tag) != "robot":
        add_error(errors, path, "URDF root must be <robot>")


def repository_checkout_paths(root):
    repos_file = root / "build_depends.repos"
    if not repos_file.is_file():
        return set()
    return set(
        re.findall(r"^  ([^\s:#]+):\s*$", repos_file.read_text(errors="replace"), re.MULTILINE)
    )


def external_repo_for_link(package_dir, candidate, link_target, checkout_paths):
    resolved_target = (candidate.parent / link_target).resolve(strict=False)
    workspace_roots = (package_dir.parent, package_dir.parent.parent.parent)
    for workspace_root in workspace_roots:
        for checkout_path in checkout_paths:
            checkout_root = (workspace_root / checkout_path).resolve(strict=False)
            try:
                resolved_target.relative_to(checkout_root)
                return checkout_path
            except ValueError:
                pass
    return None


def check_symlinks(root, packages, errors):
    checkout_paths = repository_checkout_paths(root)
    for package_dir in packages.values():
        for resource_dir in RESOURCE_DIRS:
            path = package_dir / resource_dir
            if not path.is_dir():
                continue
            for directory, dirnames, filenames in os.walk(str(path), followlinks=False):
                for name in dirnames + filenames:
                    candidate = Path(directory) / name
                    if not candidate.is_symlink() or candidate.exists():
                        continue
                    link_target = candidate.readlink()
                    external_repo = external_repo_for_link(
                        package_dir, candidate, link_target, checkout_paths
                    )
                    if external_repo is not None:
                        continue
                    add_error(errors, candidate, "broken symbolic link")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1]),
        help="visualization repository root (default: repository containing this script)",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors = []

    packages = package_index(root, errors)
    for name, directory in sorted(packages.items()):
        check_manifest(name, directory, errors)
        check_install_rules(directory, errors)
        check_resource_dependencies(name, directory, errors)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix in (".launch", ".urdf", ".xacro", ".xml"):
            check_xml(path, errors)
        if path.suffix in (".launch", ".urdf", ".xacro", ".xml", ".dae"):
            check_references(path, packages, errors)

    check_symlinks(root, packages, errors)

    if errors:
        print("Package coherence check failed ({} problem{}):".format(len(errors), "" if len(errors) == 1 else "s"))
        for error in errors:
            print("  - {}".format(error))
        return 1

    print("Package coherence check passed for {} ROS packages.".format(len(packages)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
