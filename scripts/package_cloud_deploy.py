import os
import zipfile
import sys

def create_cloud_package():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_zip = os.path.join(root_dir, "kazumi_cloud_deploy.zip")
    
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("[PACKAGE] Packaging Kazumi for Cloud Bot Hosting (Discloud / Bot-Hosting.net)...")
    print(f"[PACKAGE] Root Directory: {root_dir}")
    print(f"[PACKAGE] Output File: {output_zip}")

    exclude_dirs = {
        ".git", ".venv", "venv", "__pycache__", ".pytest_cache", 
        ".agent", ".github", "scratch", "tmp"
    }

    exclude_file_prefixes = ("test_",)
    exclude_file_extensions = (".pyc", ".pyo", ".log", ".bat", ".vbs", ".tmp")
    exclude_files = {"kazumi_supervisor.log", "kazumi.log", "kazumi_cloud_deploy.zip"}

    file_count = 0
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for current_root, dirs, files in os.walk(root_dir):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            rel_root = os.path.relpath(current_root, root_dir)
            if rel_root == ".":
                rel_root = ""

            for file in files:
                # Apply exclusions
                if file in exclude_files:
                    continue
                if any(file.endswith(ext) for ext in exclude_file_extensions):
                    continue
                if file.startswith(exclude_file_prefixes) and file.endswith(".py"):
                    # Exclude unit/integration test files to keep cloud bundle small & fast
                    continue

                abs_path = os.path.join(current_root, file)
                arc_name = os.path.join(rel_root, file) if rel_root else file

                zipf.write(abs_path, arcname=arc_name)
                file_count += 1
                total_uncompressed_bytes += os.path.getsize(abs_path)

        # Ensure logs directory entry exists
        zinfo = zipfile.ZipInfo("logs/")
        zipf.writestr(zinfo, "")
        # Ensure isa_memory directory entry exists
        zinfo_mem = zipfile.ZipInfo("isa_memory/")
        zipf.writestr(zinfo_mem, "")

    zip_size = os.path.getsize(output_zip)
    print(f"[PACKAGE] Packaging complete!")
    print(f"[PACKAGE] Bundled {file_count} files.")
    print(f"[PACKAGE] Archive size: {zip_size / (1024*1024):.2f} MB (Uncompressed: {total_uncompressed_bytes / (1024*1024):.2f} MB)")
    print(f"[PACKAGE] File ready at: {output_zip}")

if __name__ == "__main__":
    create_cloud_package()
