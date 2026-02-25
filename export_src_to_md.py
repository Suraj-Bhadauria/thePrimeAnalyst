"""
Script to export all Python source files from src/ into a folder as Markdown files.
Each .md file contains the original code wrapped in a Python code block.
"""

import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SCRIPT_DIR, "src")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "src_markdown")


def export_src_to_markdown():
    # Remove existing output folder and recreate it
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    count = 0
    for root, dirs, files in os.walk(SRC_DIR):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for filename in files:
            if not filename.endswith(".py"):
                continue

            src_path = os.path.join(root, filename)
            rel_path = os.path.relpath(src_path, SRC_DIR)

            # Mirror the directory structure inside the output folder
            rel_dir = os.path.dirname(rel_path)
            out_dir = os.path.join(OUTPUT_DIR, rel_dir)
            os.makedirs(out_dir, exist_ok=True)

            # Change extension from .py to .md
            md_filename = os.path.splitext(filename)[0] + ".md"
            md_path = os.path.join(out_dir, md_filename)

            with open(src_path, "r", encoding="utf-8") as f:
                code = f.read()

            # Write as markdown with a heading and fenced code block
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# {rel_path}\n\n")
                f.write("```python\n")
                f.write(code)
                if not code.endswith("\n"):
                    f.write("\n")
                f.write("```\n")

            count += 1
            print(f"  {rel_path} -> {os.path.relpath(md_path, SCRIPT_DIR)}")

    print(f"\nDone! Exported {count} files to '{os.path.relpath(OUTPUT_DIR, SCRIPT_DIR)}/'")


if __name__ == "__main__":
    export_src_to_markdown()
