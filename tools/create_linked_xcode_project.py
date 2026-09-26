#!/usr/bin/env python3
"""
Universal Xcode Project Creator for Huxley
Creates Xcode projects that REFERENCE actual source files (no copying)
Ensures all editors (Xcode, Cursor, terminal, Claude Code) work on the same files

Usage:
    python3 create_linked_xcode_project.py <capsule_path> <project_name>
    python3 create_linked_xcode_project.py /path/to/capsule MyApp
"""

import os
import sys
import uuid
import plistlib
import json
from pathlib import Path
import argparse

def generate_uuid():
    """Generate a 24-character hex UUID for Xcode"""
    return uuid.uuid4().hex[:24].upper()

def find_swift_files(src_path):
    """Recursively find all Swift files in the source directory"""
    swift_files = []
    src_path = Path(src_path)
    
    if src_path.exists():
        for swift_file in src_path.rglob("*.swift"):
            relative_path = swift_file.relative_to(src_path)
            swift_files.append({
                'name': swift_file.name,
                'path': str(relative_path),
                'full_path': str(swift_file),
                'uuid': generate_uuid()
            })
    
    return swift_files

def find_asset_catalogs(src_path):
    """Find asset catalogs (.xcassets) in the source directory"""
    assets = []
    src_path = Path(src_path)
    
    if src_path.exists():
        for asset_dir in src_path.rglob("*.xcassets"):
            relative_path = asset_dir.relative_to(src_path)
            assets.append({
                'name': asset_dir.name,
                'path': str(relative_path),
                'full_path': str(asset_dir),
                'uuid': generate_uuid()
            })
    
    return assets

def organize_files_into_groups(swift_files):
    """Organize Swift files into logical groups based on directory structure"""
    groups = {}
    
    for file_info in swift_files:
        path_parts = Path(file_info['path']).parts
        
        if len(path_parts) == 1:
            # Root level file
            if 'Root' not in groups:
                groups['Root'] = {'uuid': generate_uuid(), 'files': []}
            groups['Root']['files'].append(file_info)
        else:
            # File in subdirectory
            group_name = path_parts[0]
            if group_name not in groups:
                groups[group_name] = {'uuid': generate_uuid(), 'files': []}
            groups[group_name]['files'].append(file_info)
    
    return groups

def create_pbxproj_with_linked_files(project_name, src_path, swift_files, assets):
    """Create the project.pbxproj file that references actual source files"""
    
    # Generate UUIDs for main components
    project_uuid = generate_uuid()
    target_uuid = generate_uuid()
    build_config_debug_uuid = generate_uuid()
    build_config_release_uuid = generate_uuid()
    config_list_uuid = generate_uuid()
    target_config_list_uuid = generate_uuid()
    sources_build_phase_uuid = generate_uuid()
    resources_build_phase_uuid = generate_uuid()
    frameworks_build_phase_uuid = generate_uuid()
    main_group_uuid = generate_uuid()
    products_group_uuid = generate_uuid()
    app_product_uuid = generate_uuid()
    root_group_uuid = generate_uuid()
    
    # Organize files into groups
    file_groups = organize_files_into_groups(swift_files)
    
    # Build PBXBuildFile section
    build_files_section = []
    for file_info in swift_files:
        build_files_section.append(
            f"\t\t{file_info['uuid']}1 /* {file_info['name']} in Sources */ = {{isa = PBXBuildFile; fileRef = {file_info['uuid']} /* {file_info['name']} */; }};"
        )
    
    for asset_info in assets:
        build_files_section.append(
            f"\t\t{asset_info['uuid']}1 /* {asset_info['name']} in Resources */ = {{isa = PBXBuildFile; fileRef = {asset_info['uuid']} /* {asset_info['name']} */; }};"
        )
    
    # Build PBXFileReference section
    file_references_section = []
    file_references_section.append(
        f"\t\t{app_product_uuid} /* {project_name}.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = {project_name}.app; sourceTree = BUILT_PRODUCTS_DIR; }};"
    )
    
    for file_info in swift_files:
        file_references_section.append(
            f"\t\t{file_info['uuid']} /* {file_info['name']} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; name = {file_info['name']}; path = {file_info['path']}; sourceTree = \"<group>\"; }};"
        )
    
    for asset_info in assets:
        file_references_section.append(
            f"\t\t{asset_info['uuid']} /* {asset_info['name']} */ = {{isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; name = {asset_info['name']}; path = {asset_info['path']}; sourceTree = \"<group>\"; }};"
        )
    
    # Build PBXGroup section
    groups_section = []
    
    # Root group
    main_group_children = []
    for group_name, group_info in file_groups.items():
        if group_name == 'Root':
            for file_info in group_info['files']:
                main_group_children.append(f"\t\t\t\t{file_info['uuid']} /* {file_info['name']} */,")
        else:
            main_group_children.append(f"\t\t\t\t{group_info['uuid']} /* {group_name} */,")
    
    # Add assets to main group
    for asset_info in assets:
        main_group_children.append(f"\t\t\t\t{asset_info['uuid']} /* {asset_info['name']} */,")
    
    groups_section.append(f"""\\t\\t{root_group_uuid} = {{
\\t\\t\\tisa = PBXGroup;
\\t\\t\\tchildren = (
\\t\\t\\t\\t{main_group_uuid} /* {project_name} */,
\\t\\t\\t\\t{products_group_uuid} /* Products */,
\\t\\t\\t);
\\t\\t\\tsourceTree = \"<group>\";
\\t\\t}};""")
    
    groups_section.append(f"""\\t\\t{products_group_uuid} /* Products */ = {{
\\t\\t\\tisa = PBXGroup;
\\t\\t\\tchildren = (
\\t\\t\\t\\t{app_product_uuid} /* {project_name}.app */,
\\t\\t\\t);
\\t\\t\\tname = Products;
\\t\\t\\tsourceTree = \"<group>\";
\\t\\t}};""")
    
    groups_section.append(f"""\\t\\t{main_group_uuid} /* {project_name} */ = {{
\\t\\t\\tisa = PBXGroup;
\\t\\t\\tchildren = (
{chr(10).join(main_group_children)}
\\t\\t\\t);
\\t\\t\\tname = {project_name};
\\t\\t\\tsourceTree = \"<group>\";
\\t\\t}};""")
    
    # Add subgroups
    for group_name, group_info in file_groups.items():
        if group_name != 'Root':
            group_children = []
            for file_info in group_info['files']:
                group_children.append(f"\t\t\t\t{file_info['uuid']} /* {file_info['name']} */,")
            
            groups_section.append(f"""\\t\\t{group_info['uuid']} /* {group_name} */ = {{
\\t\\t\\tisa = PBXGroup;
\\t\\t\\tchildren = (
{chr(10).join(group_children)}
\\t\\t\\t);
\\t\\t\\tname = {group_name};
\\t\\t\\tsourceTree = \"<group>\";
\\t\\t}};""")
    
    # Build Sources phase
    source_files_in_build = []
    for file_info in swift_files:
        source_files_in_build.append(f"\t\t\t\t{file_info['uuid']}1 /* {file_info['name']} in Sources */,")
    
    # Build Resources phase  
    resource_files_in_build = []
    for asset_info in assets:
        resource_files_in_build.append(f"\t\t\t\t{asset_info['uuid']}1 /* {asset_info['name']} in Resources */,")
    
    # Target config UUIDs
    target_debug_uuid = generate_uuid()
    target_release_uuid = generate_uuid()
    
    pbxproj_content = f"""// !$*UTF8*$!
{{
\tarchiveVersion = 1;
\tclasses = {{}};
\tobjectVersion = 56;
\tobjects = {{

/* Begin PBXBuildFile section */
{chr(10).join(build_files_section)}
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
{chr(10).join(file_references_section)}
/* End PBXFileReference section */

/* Begin PBXFrameworksBuildPhase section */
\t\t{frameworks_build_phase_uuid} /* Frameworks */ = {{
\t\t\tisa = PBXFrameworksBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
{chr(10).join(groups_section)}
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
\t\t{target_uuid} /* {project_name} */ = {{
\t\t\tisa = PBXNativeTarget;
\t\t\tbuildConfigurationList = {target_config_list_uuid} /* Build configuration list for PBXNativeTarget "{project_name}" */;
\t\t\tbuildPhases = (
\t\t\t\t{sources_build_phase_uuid} /* Sources */,
\t\t\t\t{frameworks_build_phase_uuid} /* Frameworks */,
\t\t\t\t{resources_build_phase_uuid} /* Resources */,
\t\t\t);
\t\t\tbuildRules = (
\t\t\t);
\t\t\tdependencies = (
\t\t\t);
\t\t\tname = {project_name};
\t\t\tproductName = {project_name};
\t\t\tproductReference = {app_product_uuid} /* {project_name}.app */;
\t\t\tproductType = "com.apple.product-type.application";
\t\t}};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
\t\t{project_uuid} /* Project object */ = {{
\t\t\tisa = PBXProject;
\t\t\tattributes = {{
\t\t\t\tBuildIndependentTargetsInParallel = 1;
\t\t\t\tLastSwiftUpdateCheck = 1500;
\t\t\t\tLastUpgradeCheck = 1500;
\t\t\t\tTargetAttributes = {{
\t\t\t\t\t{target_uuid} = {{
\t\t\t\t\t\tCreatedOnToolsVersion = 15.0;
\t\t\t\t\t}};
\t\t\t\t}};
\t\t\t}};
\t\t\tbuildConfigurationList = {config_list_uuid} /* Build configuration list for PBXProject "{project_name}" */;
\t\t\tcompatibilityVersion = "Xcode 14.0";
\t\t\tdevelopmentRegion = en;
\t\t\thasScannedForEncodings = 0;
\t\t\tknownRegions = (
\t\t\t\ten,
\t\t\t\tBase,
\t\t\t);
\t\t\tmainGroup = {root_group_uuid};
\t\t\tproductRefGroup = {products_group_uuid} /* Products */;
\t\t\tprojectDirPath = "";
\t\t\tprojectRoot = "";
\t\t\ttargets = (
\t\t\t\t{target_uuid} /* {project_name} */,
\t\t\t);
\t\t}};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
\t\t{resources_build_phase_uuid} /* Resources */ = {{
\t\t\tisa = PBXResourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
{chr(10).join(resource_files_in_build)}
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
\t\t{sources_build_phase_uuid} /* Sources */ = {{
\t\t\tisa = PBXSourcesBuildPhase;
\t\t\tbuildActionMask = 2147483647;
\t\t\tfiles = (
{chr(10).join(source_files_in_build)}
\t\t\t);
\t\t\trunOnlyForDeploymentPostprocessing = 0;
\t\t}};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
\t\t{build_config_debug_uuid} /* Debug */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;
\t\t\t\tCLANG_ANALYZER_NONNULL = YES;
\t\t\t\tCLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
\t\t\t\tCLANG_ENABLE_MODULES = YES;
\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;
\t\t\t\tCLANG_WARN_BOOL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_CONSTANT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
\t\t\t\tCLANG_WARN_DOCUMENTATION_COMMENTS = YES;
\t\t\t\tCLANG_WARN_EMPTY_BODY = YES;
\t\t\t\tCLANG_WARN_ENUM_CONVERSION = YES;
\t\t\t\tCLANG_WARN_INT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
\t\t\t\tCLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
\t\t\t\tCOPY_PHASE_STRIP = NO;
\t\t\t\tDEBUG_INFORMATION_FORMAT = dwarf;
\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;
\t\t\t\tENABLE_TESTABILITY = YES;
\t\t\t\tGCC_C_LANGUAGE_STANDARD = gnu11;
\t\t\t\tGCC_DYNAMIC_NO_PIC = NO;
\t\t\t\tGCC_NO_COMMON_BLOCKS = YES;
\t\t\t\tGCC_OPTIMIZATION_LEVEL = 0;
\t\t\t\tGCC_PREPROCESSOR_DEFINITIONS = (
\t\t\t\t\t"DEBUG=1",
\t\t\t\t\t"$(inherited)",
\t\t\t\t);
\t\t\t\tGCC_WARN_64_TO_32_BIT_CONVERSION = YES;
\t\t\t\tGCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
\t\t\t\tGCC_WARN_UNDECLARED_SELECTOR = YES;
\t\t\t\tGCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
\t\t\t\tGCC_WARN_UNUSED_FUNCTION = YES;
\t\t\t\tGCC_WARN_UNUSED_VARIABLE = YES;
\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;
\t\t\t\tMTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;
\t\t\t\tMTL_FAST_MATH = YES;
\t\t\t\tONLY_ACTIVE_ARCH = YES;
\t\t\t\tSDKROOT = iphoneos;
\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;
\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = "-Onone";
\t\t\t}};
\t\t\tname = Debug;
\t\t}};
\t\t{build_config_release_uuid} /* Release */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;
\t\t\t\tCLANG_ANALYZER_NONNULL = YES;
\t\t\t\tCLANG_CXX_LANGUAGE_STANDARD = "gnu++20";
\t\t\t\tCLANG_ENABLE_MODULES = YES;
\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;
\t\t\t\tCLANG_WARN_BOOL_CONVERSION = YES;
\t\t\t\tCLANG_WARN_CONSTANT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_DIRECT_OBJC_ISA_USAGE = YES_ERROR;
\t\t\t\tCLANG_WARN_DOCUMENTATION_COMMENTS = YES;
\t\t\t\tCLANG_WARN_EMPTY_BODY = YES;
\t\t\t\tCLANG_WARN_ENUM_CONVERSION = YES;
\t\t\t\tCLANG_WARN_INT_CONVERSION = YES;
\t\t\t\tCLANG_WARN_OBJC_ROOT_CLASS = YES_ERROR;
\t\t\t\tCLANG_WARN_UNGUARDED_AVAILABILITY = YES_AGGRESSIVE;
\t\t\t\tCOPY_PHASE_STRIP = NO;
\t\t\t\tDEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
\t\t\t\tENABLE_NS_ASSERTIONS = NO;
\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;
\t\t\t\tGCC_C_LANGUAGE_STANDARD = gnu11;
\t\t\t\tGCC_NO_COMMON_BLOCKS = YES;
\t\t\t\tGCC_WARN_64_TO_32_BIT_CONVERSION = YES;
\t\t\t\tGCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;
\t\t\t\tGCC_WARN_UNDECLARED_SELECTOR = YES;
\t\t\t\tGCC_WARN_UNINITIALIZED_AUTOS = YES_AGGRESSIVE;
\t\t\t\tGCC_WARN_UNUSED_FUNCTION = YES;
\t\t\t\tGCC_WARN_UNUSED_VARIABLE = YES;
\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 17.0;
\t\t\t\tMTL_ENABLE_DEBUG_INFO = NO;
\t\t\t\tMTL_FAST_MATH = YES;
\t\t\t\tSDKROOT = iphoneos;
\t\t\t\tSWIFT_COMPILATION_MODE = wholemodule;
\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = "-O";
\t\t\t\tVALIDATE_PRODUCT = YES;
\t\t\t}};
\t\t\tname = Release;
\t\t}};
\t\t{target_debug_uuid} /* Debug */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
\t\t\t\tASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tDEVELOPMENT_ASSET_PATHS = "\\"{project_name}/Preview Content\\"";
\t\t\t\tENABLE_PREVIEWS = YES;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tINFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
\t\t\t\tINFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;
\t\t\t\tINFOPLIST_KEY_UILaunchScreen_Generation = YES;
\t\t\t\tINFOPLIST_KEY_UISupportedInterfaceOrientations_iPad = "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
\t\t\t\tINFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (
\t\t\t\t\t"$(inherited)",
\t\t\t\t\t"@executable_path/Frameworks",
\t\t\t\t);
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.example.{project_name.lower()};
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;
\t\t\t\tSWIFT_VERSION = 6.0;
\t\t\t\tTARGETED_DEVICE_FAMILY = "1,2";
\t\t\t}};
\t\t\tname = Debug;
\t\t}};
\t\t{target_release_uuid} /* Release */ = {{
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {{
\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
\t\t\t\tASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tDEVELOPMENT_ASSET_PATHS = "\\"{project_name}/Preview Content\\"";
\t\t\t\tENABLE_PREVIEWS = YES;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tINFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
\t\t\t\tINFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;
\t\t\t\tINFOPLIST_KEY_UILaunchScreen_Generation = YES;
\t\t\t\tINFOPLIST_KEY_UISupportedInterfaceOrientations_iPad = "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
\t\t\t\tINFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (
\t\t\t\t\t"$(inherited)",
\t\t\t\t\t"@executable_path/Frameworks",
\t\t\t\t);
\t\t\t\tMARKETING_VERSION = 1.0;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.example.{project_name.lower()};
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;
\t\t\t\tSWIFT_VERSION = 6.0;
\t\t\t\tTARGETED_DEVICE_FAMILY = "1,2";
\t\t\t}};
\t\t\tname = Release;
\t\t}};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
\t\t{config_list_uuid} /* Build configuration list for PBXProject "{project_name}" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t{build_config_debug_uuid} /* Debug */,
\t\t\t\t{build_config_release_uuid} /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};
\t\t{target_config_list_uuid} /* Build configuration list for PBXNativeTarget "{project_name}" */ = {{
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\t{target_debug_uuid} /* Debug */,
\t\t\t\t{target_release_uuid} /* Release */,
\t\t\t);
\t\t\tdefaultConfigurationIsVisible = 0;
\t\t\tdefaultConfigurationName = Release;
\t\t}};
/* End XCConfigurationList section */
\t}};
\trootObject = {project_uuid} /* Project object */;
}}
"""
    return pbxproj_content

def create_xcode_workspace_files(project_dir, project_name):
    """Create the workspace and supporting files"""
    
    # Create project.xcworkspace
    workspace_dir = project_dir / "project.xcworkspace"
    workspace_dir.mkdir(exist_ok=True)
    
    # Create contents.xcworkspacedata
    workspace_contents = """<?xml version="1.0" encoding="UTF-8"?>
<Workspace
   version = "1.0">
   <FileRef
      location = "self:">
   </FileRef>
</Workspace>
"""
    with open(workspace_dir / "contents.xcworkspacedata", 'w') as f:
        f.write(workspace_contents)
    
    # Create xcshareddata
    shared_dir = workspace_dir / "xcshareddata"
    shared_dir.mkdir(exist_ok=True)
    
    # Create IDEWorkspaceChecks.plist
    workspace_checks = {'IDEDidComputeMac32BitWarning': True}
    with open(shared_dir / "IDEWorkspaceChecks.plist", 'wb') as f:
        plistlib.dump(workspace_checks, f)

def create_minimal_assets_if_needed(src_path, project_name):
    """Create minimal asset catalogs if they don't exist"""
    src_path = Path(src_path)
    
    # Check if we need to create basic Assets.xcassets
    assets_dir = src_path / "Assets.xcassets"
    if not assets_dir.exists():
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Create Contents.json for Assets
        assets_contents = {"info": {"author": "xcode", "version": 1}}
        with open(assets_dir / "Contents.json", 'w') as f:
            json.dump(assets_contents, f, indent=2)
        
        # Create AppIcon.appiconset
        appicon_dir = assets_dir / "AppIcon.appiconset"
        appicon_dir.mkdir(exist_ok=True)
        
        appicon_contents = {
            "images": [{"idiom": "universal", "platform": "ios", "size": "1024x1024"}],
            "info": {"author": "xcode", "version": 1}
        }
        with open(appicon_dir / "Contents.json", 'w') as f:
            json.dump(appicon_contents, f, indent=2)
        
        # Create AccentColor.colorset
        accent_dir = assets_dir / "AccentColor.colorset"
        accent_dir.mkdir(exist_ok=True)
        
        accent_contents = {
            "colors": [{
                "color": {
                    "color-space": "srgb",
                    "components": {"alpha": "1.000", "blue": "1.000", "green": "0.478", "red": "0.000"}
                },
                "idiom": "universal"
            }],
            "info": {"author": "xcode", "version": 1}
        }
        with open(accent_dir / "Contents.json", 'w') as f:
            json.dump(accent_contents, f, indent=2)
        
        print(f"✅ Created minimal Assets.xcassets at: {assets_dir}")

def create_linked_xcode_project(capsule_path, project_name, xcode_dir=None):
    """Create Xcode project that references actual source files (no copying)"""
    
    capsule_path = Path(capsule_path)
    if not capsule_path.exists():
        raise ValueError(f"Capsule path does not exist: {capsule_path}")
    
    # Try to find source directory
    possible_src_paths = [
        capsule_path / "src" / "ios",
        capsule_path / "src" / "swift", 
        capsule_path / "src",
        capsule_path / "ios",
        capsule_path / "swift",
        capsule_path
    ]
    
    src_path = None
    for path in possible_src_paths:
        if path.exists() and list(path.rglob("*.swift")):
            src_path = path
            break
    
    if not src_path:
        raise ValueError(f"No Swift source files found in: {capsule_path}")
    
    # Determine Xcode project location
    if xcode_dir:
        xcode_base = Path(xcode_dir)
    else:
        xcode_base = src_path.parent if src_path.name in ['ios', 'swift'] else src_path
    
    project_dir = xcode_base / f"{project_name}.xcodeproj"
    project_dir.mkdir(exist_ok=True)
    
    # Find Swift files and assets
    swift_files = find_swift_files(src_path)
    assets = find_asset_catalogs(src_path)
    
    if not swift_files:
        raise ValueError(f"No Swift files found in: {src_path}")
    
    # Create minimal assets if needed
    create_minimal_assets_if_needed(src_path, project_name)
    # Re-scan for assets after creation
    assets = find_asset_catalogs(src_path)
    
    # Create project.pbxproj with file references
    pbxproj_path = project_dir / "project.pbxproj"
    with open(pbxproj_path, 'w') as f:
        f.write(create_pbxproj_with_linked_files(project_name, src_path, swift_files, assets))
    
    # Create workspace files
    create_xcode_workspace_files(project_dir, project_name)
    
    print(f"✅ Linked Xcode project created at: {project_dir}")
    print(f"📁 Project references these actual files (NO COPIES):")
    
    for file_info in swift_files:
        full_path = src_path / file_info['path']
        status = "✅" if full_path.exists() else "❌ MISSING"
        print(f"   {status} {file_info['path']}")
    
    for asset_info in assets:
        full_path = src_path / asset_info['path']
        status = "✅" if full_path.exists() else "❌ MISSING"
        print(f"   {status} {asset_info['path']}")
    
    print(f"\\n🚀 Open in Xcode: open '{project_dir}'")
    print(f"📝 All files are linked - edit in Xcode, Cursor, or terminal - they're all the same files!")
    
    return str(project_dir)

def main():
    parser = argparse.ArgumentParser(
        description="Create linked Xcode project for Huxley capsules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create project for capsule with auto-detected source path
  python3 create_linked_xcode_project.py /path/to/capsule MyApp
  
  # Create project with specific Xcode output directory  
  python3 create_linked_xcode_project.py /path/to/capsule MyApp --xcode-dir /custom/path
"""
    )
    
    parser.add_argument("capsule_path", help="Path to the capsule directory")
    parser.add_argument("project_name", help="Name for the Xcode project")
    parser.add_argument("--xcode-dir", help="Directory where .xcodeproj should be created")
    
    args = parser.parse_args()
    
    try:
        project_path = create_linked_xcode_project(
            args.capsule_path, 
            args.project_name,
            args.xcode_dir
        )
        
        print(f"\\n✅ SUCCESS: Linked Xcode project created")
        print(f"📁 Location: {project_path}")
        print(f"🔗 Source files are REFERENCED, not copied")
        print(f"🛠️  Edit in any editor - changes sync everywhere!")
        
        return 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())