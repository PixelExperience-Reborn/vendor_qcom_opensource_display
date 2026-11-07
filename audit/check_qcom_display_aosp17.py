#!/usr/bin/env python3
"""Row 178: AOSP17 Qualcomm display source-only HWC3/Allocator/Mapper gate.

NO Soong build, SELinux/VINTF image assembly, SDM/DRM binary ABI,
physical mondrian panel boot, calibration or graphics VTS are performed.

Usage: checker OLD_VENDOR_HELPERS OLD_SM8450_FULL NEW_SONY_HWC3
               PE_AOSP17_INTERFACES PE_MANIFEST
"""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

OLD_SHA = "9ae1aba2d18b18d07c5a67b616f8e70ed25ca5be"
OLD_TREE = "d37c0e7bd35a233be1d1570d3b8056ca626b05ef"
SM8450_SHA = "734b422bccc9129f2f93e6364137b5c068d7bdaa"
SM8450_TREE = "a0a2728e7461fd5922a78ca6ccde743d721aadb0"
SONY_SM8450_SHA = "4744d4a2ee7c6c0a53fac76b54766b6eb23531d4"
SONY_SM8450_TREE = "c97b019a8cfad9f90aa53690b4683d3b54d2ff4e"
NEW_SHA = "baf61f736e2109522e3f72754ee7cfacbfa2dc6c"
NEW_TREE = "f35e03e1904a346fad8257321233a32650b4ee77"
IFACE_SHA = "735e364cbdd00b0d6e4dc33ea0866dbb6d971a11"
IFACE_TREE = "adad11a145a3ecd709642f720a53f5a923fce754"
OLD_PATH = "vendor/qcom/opensource/display"
OLD_NAME = "vendor_qcom_opensource_display"
NEW_PATH = "hardware/qcom/display"


def require(ok, msg):
    if not ok:
        raise RuntimeError(msg)


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True,
        stderr=subprocess.PIPE).strip()


def pin(repo, ref, commit, tree, desc):
    actual = git(repo, "rev-parse", f"{ref}^{{commit}}")
    require(actual == commit, f"{desc} changed commit: {actual}")
    actual_tree = git(repo, "rev-parse", f"{actual}^{{tree}}")
    require(actual_tree == tree, f"{desc} changed tree: {actual_tree}")
    return actual


def show(repo, ref, filename):
    return git(repo, "show", f"{ref}:{filename}")


def files(repo, ref):
    return git(repo, "ls-tree", "-r", "--name-only", ref).splitlines()


def check_archived_vendor(old):
    sha = pin(old, "refs/remotes/origin/seventeen",
              OLD_SHA, OLD_TREE, "2021 Qualcomm vendor display helpers")
    all_files = files(old, sha)
    require(len(all_files) == 18,
            f"2021 Qualcomm vendor display inventory changed: {len(all_files)}")
    root_bp = show(old, sha, "Android.bp")
    product = show(old, sha, "config/display-product-vendor.mk")
    gralloc = show(old, sha, "gralloc/Android.bp")
    gralloc_cpp = show(old, sha, "gralloc/QtiGralloc.cpp")
    metadata = show(old, sha, "libqdmetadata/Android.bp")
    config = show(old, sha, "services/config/src/Android.bp")
    require('vendor/qcom/opensource/commonsys-intf/display' in root_bp,
            "old Qualcomm vendor display Soong namespace changed")
    for token in ("libqdMetaData", "libgralloc.qti", "libdisplayconfig.qti"):
        require(token in product,
                f"old vendor 2021 product module changed: {token}")
    require('name: "libgralloc.qti"' in gralloc
            and '"android.hardware.graphics.mapper@4.0"' in gralloc
            and '"libhidlbase"' in gralloc
            and "mapper::V4_0::IMapper" in gralloc_cpp
            and "IMapper::getService()" in gralloc_cpp,
            "old vendor helpers no longer HIDL Mapper4")
    require('name: "libqdMetaData"' in metadata
            and '"libgralloc.qti"' in metadata
            and 'name: "libdisplayconfig.qti"' in config
            and '"vendor.display.config@2.0"' in config,
            "old vendor HIDL display metadata/config module changed")
    require(not any(p.startswith("composer/") for p in all_files),
            "old vendor display now contains composer; reevaluate boundary")
    print("PASS: 18-file archived vendor display is HIDL Mapper4/Config2 helper")
    print("PASS: no Composer HAL or standalone SDM in old 2021 vendor helpers")
    print("DECISION: old vendor/qcom/opensource/display not active on AOSP17")


def check_old_sm8450(old):
    sha = pin(old, "refs/remotes/origin/seventeen",
              SM8450_SHA, SM8450_TREE, "2023 PE SM8450 full display")
    names = files(old, sha)
    require(len(names) == 379,
            f"old SM8450 display inventory changed: {len(names)}")
    composer = show(old, sha, "composer/Android.bp")
    gralloc = show(old, sha, "gralloc/Android.bp")
    for v in ("2.1", "2.2", "2.3", "2.4"):
        require(f'"android.hardware.graphics.composer@{v}"' in composer,
                f"old SM8450 HIDL Composer {v} linkage changed")
    require('name: "vendor.qti.hardware.display.composer-service"' in composer
            and '"android.hardware.graphics.mapper@4.0"' in gralloc,
            "SM8450 2023 HIDL Composer2/Gralloc4 assumptions changed")
    require(any(p.startswith("sdm/libs/") for p in names)
            and any(p.startswith("sde-drm/") for p in names),
            "old sm8450 display missing historical SDM/DRM sources")
    print("PASS: full old SM8450 379-file tree has SDM/DRM + HIDL Composer2")
    print("WARN: do NOT mix old 2023 SDM with newer HWC3 without exact ABI review")


def check_sony_sm8450_reference(sony):
    # The explicitly SM8450-family source is newer by commit date
    # (February 2026) but still HIDL Composer2.4 and HIDL Mapper4.
    # It has the SDM source absent from the HWC3 repo, yet that does
    # not establish cross-branch ABI compatibility or permit mixing.
    ref = pin(sony, "refs/remotes/origin/aosp/DISPLAY.LA.2.0.r1",
              SONY_SM8450_SHA, SONY_SM8450_TREE,
              "Sony-hosted Qualcomm SM8450 2026 display reference")
    names = files(sony, ref)
    require(len(names) == 376,
            f"Sony SM8450 display source count drift: {len(names)}")
    bp = show(sony, ref, "composer/Android.bp")
    gralloc = show(sony, ref, "gralloc/Android.bp")
    v = ET.fromstring(show(
        sony, ref, "composer/vendor.qti.hardware.display.composer-service.xml"))
    require('"android.hardware.graphics.composer@2.4"' in bp
            and '"vendor.qti.hardware.display.composer@3.1"' in bp,
            "Sony SM8450 2026 HIDL Composer contract changed")
    require('"android.hardware.graphics.mapper@4.0"' in gralloc,
            "Sony SM8450 2026 mapper HAL unexpectedly migrated")
    require(any(n.startswith("sdm/libs/") for n in names)
            and any(n.startswith("sde-drm/") for n in names),
            "Sony SM8450 2026 SDM/DRM source coverage changed")
    require(any(h.get("format") == "hidl"
                and h.findtext("name") == "android.hardware.graphics.composer"
                and h.findtext("version") == "2.4"
                for h in v.findall("hal")),
            "Sony SM8450 2026 composer HIDL2.4 VINTF changed")
    print("PASS: newer-dated 2026 SM8450 display includes real SDM and SDE-DRM")
    print("PASS: that SM8450 line remains Composer HIDL2.4/Mapper HIDL4")
    print("DECISION: DO NOT merge old HIDL SDM or product configs into HWC3")
    print("OPEN: find and ABI-validate matching modern HWC3 SDM/DRM sources")


def vints(xml):
    root = ET.fromstring(xml)
    return {(h.findtext("name"), h.findtext("version"),
             h.findtext("fqname"), h.get("format"))
            for h in root.findall("hal")}


def check_new_source(modern):
    sha = pin(modern, "refs/remotes/origin/aosp/DISPLAY.LA.5.0.r1",
              NEW_SHA, NEW_TREE, "Sony-hosted Qualcomm DISPLAY.LA.5.0.r1")
    names = files(modern, sha)
    require(len(names) == 231,
            f"newer Sony-hosted Qualcomm display inventory changed: {len(names)}")
    composer = show(modern, sha, "composer/Android.bp")
    composer_rc = show(
        modern, sha, "composer/vendor.qti.hardware.display.composer-service.rc")
    service = show(modern, sha, "composer/service.cpp")
    gralloc = show(modern, sha, "gralloc/Android.bp")
    product = show(modern, sha, "config/display-product.mk")
    modules = show(modern, sha, "config/display-modules.mk")
    for token in (
        'name: "vendor.qti.hardware.display.composer-service"',
        '"android.hardware.graphics.composer3-V3-ndk"',
        '"android.hardware.graphics.composer3-V2-ndk"',
        'vintf_fragments: ["vendor.qti.hardware.display.composer-service3_v3.xml"]',
        'vintf_fragments: ["vendor.qti.hardware.display.composer-service3_v2.xml"]',
        '"libsdmcore"', '"libsdmclient"', '"libsdmutils"',
        '"android.hardware.graphics.allocator-V2-ndk"',
    ):
        require(token in composer,
                f"newer Qualcomm Composer source dependency changed: {token}")
    require('AServiceManager_addService(' in service
            and "AidlComposer" in service
            and "Registering DisplayConfig AIDL" in service,
            "newer Qualcomm composer3 service registration changed")
    require("onrestart restart surfaceflinger" in composer_rc
            and "group graphics drmrpc" in composer_rc,
            "newer Qualcomm display init/permissions changed")
    v3 = vints(show(
        modern, sha, "composer/vendor.qti.hardware.display.composer-service3_v3.xml"))
    v2 = vints(show(
        modern, sha, "composer/vendor.qti.hardware.display.composer-service3_v2.xml"))
    require(("android.hardware.graphics.composer3", "3",
             "IComposer/default", "aidl") in v3
            and ("android.hardware.graphics.composer3", "2",
                 "IComposer/default", "aidl") in v2,
            "newer Qualcomm HWC3 V3/V2 VINTF versions changed")
    require(("vendor.qti.hardware.display.config", "12",
             "IDisplayConfig/default", "aidl") in v3
            and ("vendor.qti.hardware.display.config", "11",
                 "IDisplayConfig/default", "aidl") in v2,
            "newer Qualcomm vendor display config V12/V11 changed")
    require('name: "vendor.qti.hardware.display.allocator-service"' in gralloc
            and '"android.hardware.graphics.allocator-V2-ndk"' in gralloc
            and 'name: "mapper.qti"' in gralloc
            and '"libimapper_stablec"' in gralloc,
            "newer Qualcomm Allocator V2/Mapper5 source changed")
    allocator = ET.fromstring(show(
        modern, sha, "gralloc/vendor.qti.hardware.display.allocator-service.xml"))
    alloc_hal = allocator.find("hal")
    require(alloc_hal is not None and alloc_hal.get("format") == "aidl"
            and alloc_hal.findtext("name") == "android.hardware.graphics.allocator"
            and alloc_hal.findtext("version") == "2"
            and alloc_hal.find("interface/name").text == "IAllocator",
            "newer Qualcomm Allocator AIDL V2 manifest changed")
    mapper = ET.fromstring(show(modern, sha, "gralloc/mapper.qti.xml"))
    map_hal = mapper.find("hal")
    require(map_hal is not None and map_hal.get("format") == "native"
            and map_hal.findtext("name") == "mapper"
            and map_hal.findtext("version") == "5.0"
            and map_hal.find("interface/instance").text == "qti",
            "newer native Stable-C Mapper5 VINTF changed")
    require("SOONG_CONFIG_qtidisplay_composer_version := v3" in product
            and "composer_version: {" in composer
            and "v3_3:" in composer
            and "conditions_default:" in composer,
            "composer Soong V3/V2 selection assumptions changed")
    print("PASS: Qualcomm-derived Composer3 AIDL V2/V3 and vendor config V11/V12")
    print("PASS: Allocator AIDL V2 and Native Stable-C Mapper V5")
    print("WARN: composer v3 configuration does not by itself select v3_3 branch")
    require("DISPLAY_MODULES_HARDWARE" in modules
            and "vendor.qti.hardware.display.composer-service" in modules
            and "vendor.qti.hardware.display.allocator-service" in modules,
            "newer product modules list changed")
    for marker in ("visionox", "Sharp", "sony_amoled",
                   "backlight_calib", "ro.surface_flinger.has_HDR_display"):
        require(marker in product,
                "Sony-hosted sample panel properties/calibration changed: " + marker)
    require(not any(p.startswith("sdm/libs/") or p.startswith("sde-drm/")
                    for p in names),
            "newer source now includes SDM/DRM: reconsider incomplete classification")
    require("libsdmcore" not in names
            and "sdm/libs/core/Android.bp" not in names,
            "newer SDM source coverage changed")
    print("BLOCKER: SDM/DRM source modules are absent from this Git checkout")
    print("BLOCKER: do not import Sony/Sharp/Visionox panel calibration to mondrian")
    print("NOT TESTED: dependency-closure, Qualcomm DRM/SDM vendor ABI or display boot")


def check_aosp17_interfaces(repo):
    sha = pin(repo, "refs/remotes/origin/port/a17-hardware-interfaces-pe-20261103",
              IFACE_SHA, IFACE_TREE, "PE-selected AOSP17 hardware/interfaces")
    composer = show(repo, sha, "graphics/composer/aidl/Android.bp")
    allocator = show(repo, sha, "graphics/allocator/aidl/Android.bp")
    mapper = show(repo, sha, "graphics/mapper/stable-c/Android.bp")
    require('name: "android.hardware.graphics.composer3"' in composer
            and 'name: "android.hardware.graphics.allocator"' in allocator
            and 'frozen: true' in composer and 'frozen: true' in allocator,
            "AOSP17 frozen Composer3/Allocator source owners changed")
    for v in ("1", "2", "3", "4", "5"):
        require(f'version: "{v}"' in composer,
                f"actual PE AOSP17 Composer3 version V{v} missing")
    for v in ("1", "2", "3"):
        require(f'version: "{v}"' in allocator,
                f"actual PE AOSP17 Allocator version V{v} missing")
    require('name: "libimapper_stablec"' in mapper
            and "android.hardware.graphics.allocator-V3-ndk" in mapper,
            "selected AOSP17 Stable-C Mapper owner/version changed")
    print("PASS: actual PE AOSP17 already has frozen Composer3 V1..V5")
    print("PASS: selected AOSP17 already has Allocator AIDL V1..V3 and Stable-C")
    print("WARN: HWC3 V3 and Allocator V2 require Android17 FCM/SurfaceFlinger tests")


def manifest(root):
    root = Path(root)
    entry = ET.parse(root / "default.xml").getroot()
    require(len(entry) == 1 and entry[0].tag == "include"
            and entry[0].get("name") == "aosp17_pe_p2_kernel_configs.xml",
            "safe default.xml unexpectedly activated HWC3 preview")
    bootstrap = ET.parse(root / "aosp17_pe_bootstrap.xml").getroot()
    owners = {p.get("path"): p.get("name") for p in bootstrap.findall("project")}
    require(owners.get("hardware/interfaces") == "platform/hardware/interfaces"
            or owners.get("hardware/interfaces") == "hardware_interfaces",
            "official AOSP17 graphics source owner not present")
    require(OLD_PATH not in owners and OLD_NAME not in owners.values(),
            "old HIDL Qualcomm vendor display was activated")
    candidate = ET.parse(
        root / "aosp17_pe_p2_qcom_display_aidl_candidate.xml").getroot()
    nodes = list(candidate)
    expected = {
        "path": NEW_PATH, "name": "hardware-qcom-display",
        "remote": "sony-qcom-display-review",
        "revision": NEW_SHA,
        "upstream": "refs/heads/aosp/DISPLAY.LA.5.0.r1",
        "groups": "device",
    }
    require(candidate.tag == "manifest"
            and [n.tag for n in nodes] == ["include", "remote", "project"]
            and nodes[0].attrib
                == {"name": "aosp17_pe_p2_kernel_configs.xml"}
            and nodes[1].attrib == {
                "name": "sony-qcom-display-review",
                "fetch": "https://github.com/sonyxperiadev",
            }
            and nodes[2].attrib == expected,
            "modern Qualcomm HWC3 candidate source identity is not pinned")
    validator = (root / "tools/validate_aosp17_base_profiles.py").read_text()
    tests = (root / "tools/test_aosp17_manifest_entrypoint.py").read_text()
    require(f'if "{OLD_PATH}" in projects:' in validator
            and f'"{OLD_NAME}"' in validator,
            "row178 archived display deny-list missing")
    for method in (
        "test_archived_qualcomm_hidl_display_helpers_not_active",
        "test_archived_qualcomm_display_cannot_replace_aosp17_graphics",
        "test_qualcomm_hwc3_candidate_requires_exact_git_commit",
        "test_qualcomm_hwc3_candidate_cannot_become_default",
        "test_qualcomm_hwc3_candidate_cannot_add_vendor_display",
    ):
        require(f"def {method}(" in tests,
                "row178 source-ownership regression missing: " + method)
    subprocess.run(
        [sys.executable, str(root / "tools/validate_aosp17_base_profiles.py")],
        cwd=root, check=True)
    print("PASS: 25 AOSP17 profiles, official graphics owner and nondefault HWC3")
    print("PASS: old HIDL source path/name denied; modern SHA+remote pinned")


def main():
    require(len(sys.argv) == 7,
            "usage: checker OLD_VENDOR OLD_SM8450 SONY_SM8450_REF NEW_HWC3 PE_AOSP17_IFACE MANIFEST")
    roots = [Path(x).resolve() for x in sys.argv[1:]]
    require(all(x.is_dir() for x in roots), "source checkout missing")
    check_archived_vendor(roots[0])
    check_old_sm8450(roots[1])
    check_sony_sm8450_reference(roots[2])
    check_new_source(roots[3])
    check_aosp17_interfaces(roots[4])
    manifest(roots[5])
    print("PASS: row178 Qualcomm display source-only AIDL modernization boundary")
    print("NOT TESTED: Soong, SDM/DRM vendor ABI, VINTF, SELinux, panel, CTS/VTS")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, ET.ParseError,
            subprocess.CalledProcessError, AttributeError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
