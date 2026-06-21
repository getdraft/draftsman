#!/usr/bin/env python3
"""
Onboarding helper script to automate setting up DRAFT commands and rules
in AI-assisted IDEs (Claude Code, Cursor, Windsurf, GitHub Copilot).
"""
import os
import sys
import shutil
from pathlib import Path

def print_step(message: str):
    print(f"\n=> {message}")

def link_or_write(src_path: Path, dst_path: Path, replace_draft_path: bool = False):
    """
    Attempts to create a relative symlink from dst_path to src_path.
    If replace_draft_path is True, or if symlinking fails, it copies and modifies the file content.
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing file/symlink to avoid conflicts
    if dst_path.exists() or dst_path.is_symlink():
        if dst_path.is_dir() and not dst_path.is_symlink():
            shutil.rmtree(dst_path)
        else:
            dst_path.unlink()

    # If we need to replace the DRAFT path, we must copy and write modified content
    if replace_draft_path:
        try:
            content = src_path.read_text(encoding="utf-8")
            # Replace '.draft/framework/' with 'framework/'
            content = content.replace(".draft/framework/", "framework/")
            # Also handle any '../.draft/framework/' to '../framework/'
            content = content.replace("../.draft/framework/", "../framework/")
            dst_path.write_text(content, encoding="utf-8")
            print(f"  Created modified file: {dst_path}")
            return
        except Exception as e:
            print(f"  Error writing modified file to {dst_path}: {e}")
            # Fallback to copy/symlink of unmodified if possible
            pass

    # Try creating a relative symlink
    try:
        relative_target = os.path.relpath(src_path, dst_path.parent)
        os.symlink(relative_target, dst_path)
        print(f"  Created symlink: {dst_path} -> {relative_target}")
    except OSError:
        # Fallback to direct file copy
        try:
            shutil.copy2(src_path, dst_path)
            print(f"  Copied file (symlink fallback): {dst_path}")
        except Exception as e:
            print(f"  Error setting up {dst_path}: {e}")

def setup_ide():
    cwd = Path.cwd()
    
    # 1. Detect if we are in a DRAFT workspace or the upstream framework repo
    is_company_workspace = (cwd / ".draft").is_dir()
    
    if is_company_workspace:
        framework_dir = cwd / ".draft" / "framework"
        print("Detected DRAFT company workspace.")
    elif (cwd / "framework").is_dir() and (cwd / "draft-framework.yaml").is_file():
        framework_dir = cwd / "framework"
        print("Detected DRAFT upstream framework development repo.")
    else:
        print("Error: Run this script from the root of a DRAFT workspace or DRAFT framework repository.")
        sys.exit(1)

    replace_path = not is_company_workspace

    # 2. Setup Claude Code (/draft command dispatcher)
    print_step("Setting up Claude Code...")
    claude_cmd_src = framework_dir / "commands" / "draft.md"
    claude_cmd_dst = cwd / ".claude" / "commands" / "draft.md"
    if claude_cmd_src.is_file():
        link_or_write(claude_cmd_src, claude_cmd_dst, replace_draft_path=replace_path)
    else:
        print(f"  Warning: Claude command source not found at {claude_cmd_src}")

    # 3. Setup Cursor Rules
    print_step("Setting up Cursor...")
    cursor_rules_src = framework_dir / "integrations" / "cursor" / "draftsman.mdc"
    cursor_rules_dst = cwd / ".cursor" / "rules" / "draftsman.mdc"
    if cursor_rules_src.is_file():
        link_or_write(cursor_rules_src, cursor_rules_dst, replace_draft_path=replace_path)
    else:
        print(f"  Warning: Cursor rules source not found at {cursor_rules_src}")

    # 4. Setup Windsurf
    print_step("Setting up Windsurf...")
    windsurf_src = framework_dir / "integrations" / "windsurf" / "draftsman.md"
    windsurf_dst = cwd / ".windsurfrules"

    if windsurf_src.is_file():
        windsurf_content = windsurf_src.read_text(encoding="utf-8")
        if replace_path:
            windsurf_content = windsurf_content.replace(".draft/framework/", "framework/")

        if windsurf_dst.exists():
            # If the file already exists, check if it contains the draftsman rule
            existing_content = windsurf_dst.read_text(encoding="utf-8")
            if "DRAFT Draftsman" in existing_content or "draftsman.md" in existing_content:
                print(f"  Windsurf rules already configured in {windsurf_dst}")
            else:
                try:
                    with open(windsurf_dst, "a", encoding="utf-8") as f:
                        f.write("\n\n" + windsurf_content)
                    print(f"  Appended Draftsman rules to {windsurf_dst}")
                except Exception as e:
                    print(f"  Error appending to {windsurf_dst}: {e}")
        else:
            # If it does not exist, write the content directly
            try:
                windsurf_dst.write_text(windsurf_content, encoding="utf-8")
                print(f"  Created Windsurf rules: {windsurf_dst}")
            except Exception as e:
                print(f"  Error creating {windsurf_dst}: {e}")
    else:
        print(f"  Warning: Windsurf rules source not found at {windsurf_src}")

    # 5. Setup GitHub Copilot Instructions
    print_step("Setting up GitHub Copilot...")
    copilot_dst = cwd / ".github" / "copilot-instructions.md"
    if is_company_workspace:
        copilot_tmpl = cwd / ".draft" / "templates" / "workspace" / ".github" / "copilot-instructions.md.tmpl"
        if not copilot_tmpl.is_file():
            copilot_tmpl = framework_dir / "templates" / "workspace" / ".github" / "copilot-instructions.md.tmpl"
    else:
        copilot_tmpl = cwd / "templates" / "workspace" / ".github" / "copilot-instructions.md.tmpl"

    # Define the generic block to insert if the file already exists
    copilot_block = (
        "\n\nWhen the user invokes `/draft <verb>` (for example `/draft guide`, "
        "`/draft audit`, or `/draft validate`), read "
        "`.draft/framework/commands/draft.md` (or `framework/commands/draft.md`), "
        "resolve the verb to its action file under the framework's `draft-actions/` directory, "
        "and follow that file's instructions exactly."
    )

    if copilot_dst.exists():
        existing_content = copilot_dst.read_text(encoding="utf-8")
        if "/draft" in existing_content:
            print(f"  Copilot instructions already configured in {copilot_dst}")
        else:
            try:
                with open(copilot_dst, "a", encoding="utf-8") as f:
                    f.write(copilot_block)
                print(f"  Appended Draftsman block to {copilot_dst}")
            except Exception as e:
                print(f"  Error appending to {copilot_dst}: {e}")
    else:
        if copilot_tmpl.is_file():
            try:
                content = copilot_tmpl.read_text(encoding="utf-8")
                if replace_path:
                    content = content.replace(".draft/framework/", "framework/")
                copilot_dst.parent.mkdir(parents=True, exist_ok=True)
                copilot_dst.write_text(content, encoding="utf-8")
                print(f"  Created Copilot instructions from template: {copilot_dst}")
            except Exception as e:
                print(f"  Error copying Copilot template: {e}")
        else:
            # Fallback to writing the standalone block
            try:
                copilot_dst.parent.mkdir(parents=True, exist_ok=True)
                copilot_dst.write_text(f"# Copilot Instructions\n\n{copilot_block.strip()}", encoding="utf-8")
                print(f"  Created Copilot instructions: {copilot_dst}")
            except Exception as e:
                print(f"  Error creating Copilot instructions: {e}")

    print("\n✓ DRAFT IDE setup completed successfully!")

if __name__ == "__main__":
    setup_ide()
