#!/usr/bin/env python3
"""
Nyuu GUI - A comprehensive graphical interface for Nyuu Usenet poster
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import json
import subprocess
import threading
import platform
import requests
import tarfile
import zipfile
from pathlib import Path
import shutil
import py7zr


class NyuuDownloader:
    """Handles downloading and managing Nyuu binaries from GitHub releases"""

    GITHUB_API = "https://api.github.com/repos/animetosho/Nyuu/releases/latest"

    def __init__(self, download_dir="nyuu_binaries"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.nyuu_executable = None
        self.seven_zip_url = "https://www.7-zip.org/a/7zr.exe"
        self.local_7z_path = self.download_dir / "7zr.exe"

    def download_7zip_standalone(self, progress_callback=None):
        """Download standalone 7-Zip console binary for Windows"""
        try:
            if progress_callback:
                progress_callback("downloading", "Downloading 7-Zip standalone binary...")

            response = requests.get(self.seven_zip_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(self.local_7z_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size:
                            percent = (downloaded / total_size) * 100
                            progress_callback("downloading", f"Downloading 7-Zip: {percent:.1f}%")

            if progress_callback:
                progress_callback("complete", "7-Zip downloaded successfully!")

            return self.local_7z_path

        except Exception as e:
            # Clean up partial download
            if self.local_7z_path.exists():
                self.local_7z_path.unlink()
            raise Exception(f"Failed to download 7-Zip: {str(e)}")

    def find_7z_executable(self):
        """Find 7z executable on the system"""
        # First check if we have a local copy
        if self.local_7z_path.exists():
            return str(self.local_7z_path)

        # Common 7-Zip installation paths on Windows
        common_paths = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]

        # Try the system PATH
        try:
            result = subprocess.run(['7z', '--help'],
                                  capture_output=True,
                                  timeout=2)
            return '7z'  # Found in PATH
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check common installation paths (Windows)
        if sys.platform == 'win32':
            for path in common_paths:
                if os.path.exists(path):
                    return path

        return None

    def get_latest_release_info(self):
        """Fetch latest release information from GitHub API"""
        try:
            response = requests.get(self.GITHUB_API, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to fetch release info: {str(e)}")

    def get_asset_for_os(self, release_info, os_type):
        """Get the appropriate asset URL for the specified OS"""
        assets = release_info.get('assets', [])

        asset_map = {
            'Linux x64': 'linux-amd64',
            'Linux ARM64': 'linux-aarch64',
            'macOS x64': 'macos-x64',
            'Windows 32-bit': 'win32'
        }

        search_term = asset_map.get(os_type)
        if not search_term:
            raise Exception(f"Unknown OS type: {os_type}")

        for asset in assets:
            if search_term in asset['name']:
                return asset['browser_download_url'], asset['name']

        raise Exception(f"No asset found for {os_type}")

    def download_file(self, url, filename, progress_callback=None):
        """Download file with progress reporting"""
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        filepath = self.download_dir / filename
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        progress_callback(downloaded, total_size)

        return filepath

    def extract_archive(self, filepath, progress_callback=None):
        """Extract downloaded archive"""
        extract_dir = self.download_dir / filepath.stem
        extract_dir.mkdir(exist_ok=True)

        if filepath.suffix == '.xz' or '.tar' in filepath.name:
            with tarfile.open(filepath, 'r:xz') as tar:
                tar.extractall(extract_dir)
        elif filepath.suffix == '.7z':
            # First try py7zr library for 7z extraction
            extraction_successful = False
            py7zr_error = None

            try:
                with py7zr.SevenZipFile(filepath, mode='r') as archive:
                    archive.extractall(path=extract_dir)
                extraction_successful = True
            except Exception as e:
                py7zr_error = str(e)
                # py7zr failed, likely due to unsupported compression filter (BCJ2)

            # If py7zr failed, try system 7z command as fallback
            if not extraction_successful:
                seven_zip_path = self.find_7z_executable()

                # If no 7z found, try downloading it automatically (Windows only)
                if not seven_zip_path and sys.platform == 'win32':
                    try:
                        if progress_callback:
                            progress_callback("downloading", "7-Zip not found. Downloading standalone version...")

                        self.download_7zip_standalone(progress_callback)
                        seven_zip_path = self.find_7z_executable()

                        if progress_callback:
                            progress_callback("extracting", "7-Zip downloaded. Extracting archive...")
                    except Exception as download_error:
                        raise Exception(
                            f"Failed to download 7-Zip automatically: {download_error}\n"
                            "Please manually install 7-Zip from https://www.7-zip.org/\n\n"
                            f"Original extraction error: {py7zr_error}"
                        )

                if seven_zip_path:
                    try:
                        # Try 7z command (works on Windows if 7-Zip is installed)
                        result = subprocess.run(
                            [seven_zip_path, 'x', str(filepath), f'-o{extract_dir}', '-y'],
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        extraction_successful = True
                    except subprocess.CalledProcessError as e:
                        raise Exception(
                            f"7z extraction failed with both py7zr and system 7z command. "
                            f"py7zr error: {py7zr_error}. "
                            f"7z command error: {e.stderr}"
                        )
                else:
                    # 7z command still not found after download attempt
                    raise Exception(
                        "7z extraction failed with py7zr (unsupported BCJ2 compression filter). "
                        "Could not find or download 7-Zip.\n"
                        "Please manually install 7-Zip from https://www.7-zip.org/\n\n"
                        f"Technical details - py7zr error: {py7zr_error}"
                    )

        return extract_dir

    def find_nyuu_executable(self, extract_dir):
        """Find the Nyuu executable in extracted directory"""
        # Look for nyuu or nyuu.exe
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if file.lower() in ['nyuu', 'nyuu.exe']:
                    exe_path = Path(root) / file
                    # Make executable on Unix-like systems
                    if sys.platform != 'win32':
                        os.chmod(exe_path, 0o755)
                    return exe_path

        raise Exception("Nyuu executable not found in extracted files")

    def download_and_setup(self, os_type, progress_callback=None):
        """Complete download and setup process"""
        # Get release info
        release_info = self.get_latest_release_info()
        version = release_info.get('tag_name', 'unknown')

        # Get download URL
        url, filename = self.get_asset_for_os(release_info, os_type)

        # Download
        if progress_callback:
            progress_callback("downloading", f"Downloading {filename}...")

        def download_progress(downloaded, total):
            if progress_callback:
                percent = (downloaded / total) * 100
                progress_callback("downloading", f"Downloading: {percent:.1f}%")

        filepath = self.download_file(url, filename, download_progress)

        # Extract
        if progress_callback:
            progress_callback("extracting", "Extracting archive...")

        extract_dir = self.extract_archive(filepath, progress_callback)

        # Find executable
        if progress_callback:
            progress_callback("locating", "Locating Nyuu executable...")

        self.nyuu_executable = self.find_nyuu_executable(extract_dir)

        if progress_callback:
            progress_callback("complete", f"Nyuu {version} ready!")

        return self.nyuu_executable


class FileProcessor:
    """Handles file splitting and PAR2 creation"""

    def __init__(self, work_dir="processed_files"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(exist_ok=True)
        self.par2_url = "https://github.com/Parchive/par2cmdline/releases/download/v1.0.0/par2cmdline-1.0.0-win-x64.zip"
        self.local_par2_dir = self.work_dir / "par2cmdline"
        self.local_par2_path = self.local_par2_dir / "par2.exe"

    def split_file(self, filepath, chunk_size_mb, output_dir=None, progress_callback=None):
        """Split a file into chunks of specified size"""
        filepath = Path(filepath)
        if output_dir is None:
            output_dir = self.work_dir / f"{filepath.stem}_split"
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(exist_ok=True)

        chunk_size = chunk_size_mb * 1024 * 1024  # Convert MB to bytes
        file_size = filepath.stat().st_size

        if file_size <= chunk_size:
            # File is smaller than chunk size, no need to split
            if progress_callback:
                progress_callback("complete", f"File is smaller than {chunk_size_mb}MB, no splitting needed")
            return [filepath]

        chunks = []
        part_num = 1

        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    # Create output filename: original.ext.001, original.ext.002, etc.
                    output_file = output_dir / f"{filepath.name}.{part_num:03d}"

                    with open(output_file, 'wb') as out:
                        out.write(chunk)

                    chunks.append(output_file)

                    if progress_callback:
                        percent = (f.tell() / file_size) * 100
                        progress_callback("splitting", f"Splitting: {percent:.1f}% (Part {part_num})")

                    part_num += 1

            if progress_callback:
                progress_callback("complete", f"Split into {len(chunks)} parts")

            return chunks

        except Exception as e:
            raise Exception(f"Failed to split file: {str(e)}")

    def download_par2_standalone(self, progress_callback=None):
        """Download standalone par2cmdline binary for Windows"""
        try:
            if progress_callback:
                progress_callback("downloading", "Downloading par2cmdline standalone binary...")

            response = requests.get(self.par2_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            # Download to temp file
            zip_path = self.work_dir / "par2cmdline.zip"

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size:
                            percent = (downloaded / total_size) * 100
                            progress_callback("downloading", f"Downloading par2cmdline: {percent:.1f}%")

            # Extract ZIP file
            if progress_callback:
                progress_callback("extracting", "Extracting par2cmdline...")

            self.local_par2_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.local_par2_dir)

            # Clean up zip file
            zip_path.unlink()

            # Find par2.exe in extracted files
            for root, dirs, files in os.walk(self.local_par2_dir):
                for file in files:
                    if file.lower() == 'par2.exe':
                        exe_path = Path(root) / file
                        # Move to expected location if in subdirectory
                        if exe_path != self.local_par2_path:
                            shutil.move(str(exe_path), str(self.local_par2_path))
                        break

            if progress_callback:
                progress_callback("complete", "par2cmdline downloaded successfully!")

            return self.local_par2_path

        except Exception as e:
            # Clean up on failure
            if zip_path.exists():
                zip_path.unlink()
            if self.local_par2_dir.exists():
                shutil.rmtree(self.local_par2_dir)
            raise Exception(f"Failed to download par2cmdline: {str(e)}")

    def find_par2_executable(self):
        """Find par2 executable on the system"""
        # First check if we have a local copy
        if self.local_par2_path.exists():
            return str(self.local_par2_path)

        # Check if par2 or par2create is in PATH
        for cmd in ['par2', 'par2create', 'par2.exe']:
            try:
                result = subprocess.run([cmd, '-h'],
                                      capture_output=True,
                                      timeout=2)
                return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        # Check common installation paths on Windows
        if sys.platform == 'win32':
            common_paths = [
                r"C:\Program Files\par2cmdline\par2.exe",
                r"C:\Program Files (x86)\par2cmdline\par2.exe",
            ]
            for path in common_paths:
                if os.path.exists(path):
                    return path

        return None

    def create_par2(self, files, redundancy=10, output_dir=None, progress_callback=None):
        """Create PAR2 recovery files for given files

        Args:
            files: List of file paths or single file path
            redundancy: Redundancy percentage (default 10%)
            output_dir: Output directory for PAR2 files
            progress_callback: Callback function for progress updates
        """
        if isinstance(files, (str, Path)):
            files = [files]

        files = [Path(f) for f in files]

        if not files:
            raise ValueError("No files provided for PAR2 creation")

        # Find par2 executable
        par2_cmd = self.find_par2_executable()

        # If no par2 found, try downloading it automatically (Windows only)
        if not par2_cmd and sys.platform == 'win32':
            try:
                if progress_callback:
                    progress_callback("downloading", "par2cmdline not found. Downloading standalone version...")

                self.download_par2_standalone(progress_callback)
                par2_cmd = self.find_par2_executable()

                if progress_callback:
                    progress_callback("creating", "par2cmdline downloaded. Creating PAR2 files...")
            except Exception as download_error:
                raise Exception(
                    f"Failed to download par2cmdline automatically: {download_error}\n\n"
                    "Please manually install par2cmdline from:\n"
                    "https://github.com/Parchive/par2cmdline/releases"
                )

        if not par2_cmd:
            raise Exception(
                "PAR2 command-line tool not found.\n\n"
                "Please install par2cmdline:\n"
                "- Linux: sudo apt-get install par2 (or yum install par2cmdline)\n"
                "- macOS: brew install par2\n"
                "- Windows: Download from https://github.com/Parchive/par2cmdline/releases"
            )

        # Determine output directory
        if output_dir is None:
            output_dir = files[0].parent
        else:
            output_dir = Path(output_dir)

        # Create PAR2 file name based on first file or directory name
        if len(files) == 1:
            par2_name = output_dir / f"{files[0].stem}.par2"
        else:
            # Use common directory name or generic name
            par2_name = output_dir / "recovery.par2"

        try:
            if progress_callback:
                progress_callback("creating", "Creating PAR2 recovery files...")

            # Build par2 command
            # Format: par2 create -r<redundancy> output.par2 file1 file2 ...
            cmd = [
                par2_cmd,
                'create',
                f'-r{redundancy}',
                str(par2_name)
            ] + [str(f) for f in files]

            # Run par2 command
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=str(output_dir)
            )

            # Monitor output
            for line in process.stdout:
                if progress_callback:
                    # Try to extract progress from par2 output
                    if '%' in line:
                        progress_callback("creating", f"Creating PAR2: {line.strip()}")
                    else:
                        progress_callback("creating", "Creating PAR2 recovery files...")

            process.wait()

            if process.returncode == 0:
                # Find created PAR2 files
                par2_files = list(output_dir.glob(f"{par2_name.stem}*.par2"))

                if progress_callback:
                    progress_callback("complete", f"Created {len(par2_files)} PAR2 file(s)")

                return par2_files
            else:
                raise Exception(f"PAR2 creation failed with exit code {process.returncode}")

        except Exception as e:
            raise Exception(f"Failed to create PAR2 files: {str(e)}")


class NyuuGUI:
    """Main GUI application for Nyuu"""

    def __init__(self, root):
        self.root = root
        self.root.title("Nyuu GUI - Usenet Binary Poster")
        self.root.geometry("900x800")

        self.downloader = NyuuDownloader()
        self.file_processor = FileProcessor()
        self.nyuu_process = None
        self.config = {}

        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        """Setup the user interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Setup tabs
        self.setup_download_tab()
        self.setup_server_tab()
        self.setup_posting_tab()
        self.setup_nzb_tab()
        self.setup_files_tab()
        self.setup_file_prep_tab()
        self.setup_advanced_tab()
        self.setup_console_tab()

        # Control buttons at bottom
        self.setup_controls()

    def setup_download_tab(self):
        """Setup Nyuu download and management tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Nyuu Setup")

        # Download section
        download_frame = ttk.LabelFrame(frame, text="Download Nyuu", padding=10)
        download_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(download_frame, text="Operating System:").grid(row=0, column=0, sticky=tk.W, pady=5)

        self.os_var = tk.StringVar(value="Linux x64")
        os_options = ["Linux x64", "Linux ARM64", "macOS x64", "Windows 32-bit"]
        os_combo = ttk.Combobox(download_frame, textvariable=self.os_var,
                                values=os_options, state="readonly", width=30)
        os_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        self.download_btn = ttk.Button(download_frame, text="Download Latest Release",
                                       command=self.download_nyuu)
        self.download_btn.grid(row=1, column=0, columnspan=2, pady=10)

        self.download_status = ttk.Label(download_frame, text="No Nyuu binary downloaded",
                                         foreground="red")
        self.download_status.grid(row=2, column=0, columnspan=2, pady=5)

        # Manual path section
        manual_frame = ttk.LabelFrame(frame, text="Or Use Existing Nyuu", padding=10)
        manual_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(manual_frame, text="Nyuu Executable:").grid(row=0, column=0, sticky=tk.W, pady=5)

        self.nyuu_path_var = tk.StringVar()
        ttk.Entry(manual_frame, textvariable=self.nyuu_path_var, width=50).grid(row=0, column=1, padx=5)

        ttk.Button(manual_frame, text="Browse", command=self.browse_nyuu).grid(row=0, column=2)

        # Info section
        info_frame = ttk.LabelFrame(frame, text="About Nyuu", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        info_text = """Nyuu is a command-line Usenet binary poster.

Features:
• Fast yEnc encoding with CRC32 calculation
• Multi-connection uploading
• SSL/TLS support for secure connections
• Automatic post verification
• NZB file generation
• High reliability with automatic retries

This GUI provides an easy interface to all Nyuu features."""

        info_label = tk.Label(info_frame, text=info_text, justify=tk.LEFT, anchor=tk.W)
        info_label.pack(fill=tk.BOTH, expand=True)

    def setup_server_tab(self):
        """Setup server configuration tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Server Config")

        # Server details
        server_frame = ttk.LabelFrame(frame, text="NNTP Server", padding=10)
        server_frame.pack(fill=tk.X, padx=10, pady=5)

        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar(value="119")
        self.ssl_var = tk.BooleanVar(value=False)
        self.ignore_cert_var = tk.BooleanVar(value=False)
        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.connections_var = tk.StringVar(value="3")

        row = 0
        ttk.Label(server_frame, text="Host:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(server_frame, textvariable=self.host_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(server_frame, text="Port:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(server_frame, textvariable=self.port_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Checkbutton(server_frame, text="Use SSL/TLS", variable=self.ssl_var,
                       command=self.toggle_ssl).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)

        row += 1
        ttk.Checkbutton(server_frame, text="Ignore SSL Certificate Errors",
                       variable=self.ignore_cert_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)

        row += 1
        ttk.Separator(server_frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=10)

        row += 1
        ttk.Label(server_frame, text="Username:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(server_frame, textvariable=self.user_var, width=40).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(server_frame, text="Password:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(server_frame, textvariable=self.password_var, show="*", width=40).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(server_frame, text="Connections:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(server_frame, textvariable=self.connections_var, from_=1, to=50,
                   width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

    def setup_posting_tab(self):
        """Setup posting options tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Posting Options")

        # Article options
        article_frame = ttk.LabelFrame(frame, text="Article Settings", padding=10)
        article_frame.pack(fill=tk.X, padx=10, pady=5)

        self.article_size_var = tk.StringVar(value="700K")
        self.comment_var = tk.StringVar()
        self.from_var = tk.StringVar()
        self.groups_var = tk.StringVar()

        row = 0
        ttk.Label(article_frame, text="Article Size:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(article_frame, textvariable=self.article_size_var, width=15).grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Label(article_frame, text="(e.g., 700K, 1M)").grid(row=row, column=2, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(article_frame, text="Comment/Subject:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(article_frame, textvariable=self.comment_var, width=50).grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(article_frame, text="From:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(article_frame, textvariable=self.from_var, width=50).grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(article_frame, text="Newsgroups:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(article_frame, textvariable=self.groups_var, width=50).grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(article_frame, text="(comma separated)").grid(row=row, column=3, sticky=tk.W, pady=5)

        # Verification options
        verify_frame = ttk.LabelFrame(frame, text="Post Verification", padding=10)
        verify_frame.pack(fill=tk.X, padx=10, pady=5)

        self.check_enabled_var = tk.BooleanVar(value=False)
        self.check_connections_var = tk.StringVar(value="1")
        self.check_tries_var = tk.StringVar(value="2")
        self.check_delay_var = tk.StringVar(value="5s")
        self.check_retry_delay_var = tk.StringVar(value="30s")
        self.check_post_tries_var = tk.StringVar(value="1")

        row = 0
        ttk.Checkbutton(verify_frame, text="Enable Post Verification",
                       variable=self.check_enabled_var).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(verify_frame, text="Check Connections:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(verify_frame, textvariable=self.check_connections_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(verify_frame, text="Check Tries:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(verify_frame, textvariable=self.check_tries_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(verify_frame, text="Initial Check Delay:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(verify_frame, textvariable=self.check_delay_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(verify_frame, text="Retry Delay:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(verify_frame, textvariable=self.check_retry_delay_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(verify_frame, text="Re-post Tries:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(verify_frame, textvariable=self.check_post_tries_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)

    def setup_nzb_tab(self):
        """Setup NZB output options tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="NZB Output")

        # NZB file
        nzb_frame = ttk.LabelFrame(frame, text="NZB File", padding=10)
        nzb_frame.pack(fill=tk.X, padx=10, pady=5)

        self.nzb_output_var = tk.StringVar()
        self.nzb_overwrite_var = tk.BooleanVar(value=False)

        row = 0
        ttk.Label(nzb_frame, text="Output File:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(nzb_frame, textvariable=self.nzb_output_var, width=50).grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Button(nzb_frame, text="Browse", command=self.browse_nzb_output).grid(row=row, column=2, padx=5)

        row += 1
        ttk.Checkbutton(nzb_frame, text="Overwrite Existing NZB",
                       variable=self.nzb_overwrite_var).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Metadata
        meta_frame = ttk.LabelFrame(frame, text="NZB Metadata (Optional)", padding=10)
        meta_frame.pack(fill=tk.X, padx=10, pady=5)

        self.nzb_title_var = tk.StringVar()
        self.nzb_category_var = tk.StringVar()
        self.nzb_tag_var = tk.StringVar()
        self.nzb_password_var = tk.StringVar()

        row = 0
        ttk.Label(meta_frame, text="Title:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(meta_frame, textvariable=self.nzb_title_var, width=50).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(meta_frame, text="Category:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(meta_frame, textvariable=self.nzb_category_var, width=50).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(meta_frame, text="Tag:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(meta_frame, textvariable=self.nzb_tag_var, width=50).grid(row=row, column=1, sticky=tk.W, pady=5)

        row += 1
        ttk.Label(meta_frame, text="Password:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(meta_frame, textvariable=self.nzb_password_var, width=50).grid(row=row, column=1, sticky=tk.W, pady=5)

    def setup_files_tab(self):
        """Setup file/directory selection tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Files")

        # File selection
        files_frame = ttk.LabelFrame(frame, text="Files to Post", padding=10)
        files_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Buttons
        btn_frame = ttk.Frame(files_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="Add Files", command=self.add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Add Directory", command=self.add_directory).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_files).pack(side=tk.LEFT, padx=2)

        self.recursive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(btn_frame, text="Include Subdirectories",
                       variable=self.recursive_var).pack(side=tk.LEFT, padx=10)

        # File list
        list_frame = ttk.Frame(files_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.files_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.files_listbox.yview)

        # Delete selected
        ttk.Button(files_frame, text="Remove Selected",
                  command=self.remove_selected_files).pack(pady=5)

    def setup_file_prep_tab(self):
        """Setup file preparation tab (splitting and PAR2)"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="File Preparation")

        # File Splitting section
        split_frame = ttk.LabelFrame(frame, text="File Splitting", padding=10)
        split_frame.pack(fill=tk.X, padx=10, pady=5)

        self.enable_split_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(split_frame, text="Enable File Splitting",
                       variable=self.enable_split_var,
                       command=self.toggle_split_options).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)

        ttk.Label(split_frame, text="Split Size (MB):").grid(row=1, column=0, sticky=tk.W, pady=5, padx=(20, 5))

        self.split_size_var = tk.StringVar(value="100")
        self.split_size_entry = ttk.Spinbox(split_frame, textvariable=self.split_size_var,
                                           from_=1, to=10000, width=10, state=tk.DISABLED)
        self.split_size_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(split_frame, text="(Files larger than this will be split)").grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)

        ttk.Label(split_frame, text="Output Directory:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=(20, 5))

        self.split_output_var = tk.StringVar()
        self.split_output_entry = ttk.Entry(split_frame, textvariable=self.split_output_var,
                                           width=40, state=tk.DISABLED)
        self.split_output_entry.grid(row=2, column=1, sticky=tk.W, pady=5)

        self.split_browse_btn = ttk.Button(split_frame, text="Browse",
                                          command=self.browse_split_output, state=tk.DISABLED)
        self.split_browse_btn.grid(row=2, column=2, padx=5)

        ttk.Label(split_frame, text="(Leave empty to use 'processed_files' directory)").grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=2)

        # PAR2 section
        par2_frame = ttk.LabelFrame(frame, text="PAR2 Recovery Files", padding=10)
        par2_frame.pack(fill=tk.X, padx=10, pady=5)

        self.enable_par2_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(par2_frame, text="Create PAR2 Recovery Files",
                       variable=self.enable_par2_var,
                       command=self.toggle_par2_options).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)

        ttk.Label(par2_frame, text="Redundancy %:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=(20, 5))

        self.par2_redundancy_var = tk.StringVar(value="10")
        self.par2_redundancy_entry = ttk.Spinbox(par2_frame, textvariable=self.par2_redundancy_var,
                                                from_=1, to=100, width=10, state=tk.DISABLED)
        self.par2_redundancy_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(par2_frame, text="(10% = 10% recovery data)").grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)

        # Status
        self.par2_status = ttk.Label(par2_frame, text="PAR2 tool not checked", foreground="gray")
        self.par2_status.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5, padx=(20, 5))

        ttk.Button(par2_frame, text="Check PAR2 Installation",
                  command=self.check_par2).grid(row=3, column=0, columnspan=3, pady=5, padx=(20, 5))

        # Info section
        info_frame = ttk.LabelFrame(frame, text="About File Preparation", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        info_text = """File Splitting:
Splits large files into smaller chunks for easier posting and downloading.
Useful when your Usenet provider has file size limits.

PAR2 Recovery Files:
Creates parity files that allow recovery of missing or corrupted data.
Essential for Usenet posts to ensure data integrity.
Requires par2cmdline to be installed on your system.

Workflow:
1. Add files in the Files tab
2. Enable splitting/PAR2 here as needed
3. Files will be processed before upload when you click "Start Upload"
"""

        info_label = tk.Label(info_frame, text=info_text, justify=tk.LEFT, anchor=tk.NW)
        info_label.pack(fill=tk.BOTH, expand=True)

    def setup_advanced_tab(self):
        """Setup advanced options tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Advanced")

        # Error handling
        error_frame = ttk.LabelFrame(frame, text="Error Handling", padding=10)
        error_frame.pack(fill=tk.X, padx=10, pady=5)

        self.skip_errors_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(error_frame, text="Skip Errors and Continue",
                       variable=self.skip_errors_var).pack(anchor=tk.W, pady=5)

        # UI Options
        ui_frame = ttk.LabelFrame(frame, text="UI Options", padding=10)
        ui_frame.pack(fill=tk.X, padx=10, pady=5)

        self.quiet_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ui_frame, text="Quiet Mode (minimal output)",
                       variable=self.quiet_var).pack(anchor=tk.W, pady=5)

        # Config file
        config_frame = ttk.LabelFrame(frame, text="Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(config_frame, text="Save Current Settings",
                  command=self.save_config).pack(pady=5)
        ttk.Button(config_frame, text="Load Settings",
                  command=self.load_config_file).pack(pady=5)

        # Custom arguments
        custom_frame = ttk.LabelFrame(frame, text="Custom Arguments", padding=10)
        custom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        ttk.Label(custom_frame, text="Additional Nyuu arguments:").pack(anchor=tk.W, pady=5)

        self.custom_args_var = tk.StringVar()
        ttk.Entry(custom_frame, textvariable=self.custom_args_var, width=70).pack(fill=tk.X, pady=5)

    def setup_console_tab(self):
        """Setup console output tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Console")

        # Console output
        self.console_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=30)
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Clear button
        ttk.Button(frame, text="Clear Console", command=self.clear_console).pack(pady=5)

    def setup_controls(self):
        """Setup control buttons"""
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        self.start_btn = ttk.Button(control_frame, text="Start Upload",
                                    command=self.start_upload, style="Success.TButton")
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="Stop Upload",
                                   command=self.stop_upload, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="View Command",
                  command=self.view_command).pack(side=tk.LEFT, padx=5)

        # Status
        self.status_label = ttk.Label(control_frame, text="Ready", foreground="green")
        self.status_label.pack(side=tk.RIGHT, padx=5)

    # Event handlers
    def toggle_ssl(self):
        """Update port when SSL is toggled"""
        if self.ssl_var.get():
            if self.port_var.get() == "119":
                self.port_var.set("563")
        else:
            if self.port_var.get() == "563":
                self.port_var.set("119")

    def download_nyuu(self):
        """Download Nyuu from GitHub"""
        os_type = self.os_var.get()

        def download_thread():
            try:
                self.download_btn.config(state=tk.DISABLED)
                self.log_message(f"Starting download for {os_type}...")

                def progress_callback(status, message):
                    self.root.after(0, lambda: self.download_status.config(text=message))
                    self.log_message(message)

                exe_path = self.downloader.download_and_setup(os_type, progress_callback)

                self.root.after(0, lambda: self.nyuu_path_var.set(str(exe_path)))
                self.root.after(0, lambda: self.download_status.config(
                    text=f"✓ Nyuu ready at: {exe_path}", foreground="green"))
                self.log_message(f"Successfully downloaded and extracted Nyuu to: {exe_path}")

            except Exception as e:
                self.root.after(0, lambda: self.download_status.config(
                    text=f"✗ Error: {str(e)}", foreground="red"))
                self.log_message(f"Error downloading Nyuu: {str(e)}")
            finally:
                self.root.after(0, lambda: self.download_btn.config(state=tk.NORMAL))

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def browse_nyuu(self):
        """Browse for existing Nyuu executable"""
        filename = filedialog.askopenfilename(
            title="Select Nyuu executable",
            filetypes=[("Executables", "nyuu*"), ("All files", "*.*")]
        )
        if filename:
            self.nyuu_path_var.set(filename)
            self.download_status.config(text=f"✓ Using: {filename}", foreground="green")

    def browse_nzb_output(self):
        """Browse for NZB output file"""
        filename = filedialog.asksaveasfilename(
            title="Save NZB file as",
            defaultextension=".nzb",
            filetypes=[("NZB files", "*.nzb"), ("All files", "*.*")]
        )
        if filename:
            self.nzb_output_var.set(filename)

    def add_files(self):
        """Add files to upload list"""
        filenames = filedialog.askopenfilenames(title="Select files to upload")
        for filename in filenames:
            self.files_listbox.insert(tk.END, filename)

    def add_directory(self):
        """Add directory to upload list"""
        dirname = filedialog.askdirectory(title="Select directory to upload")
        if dirname:
            self.files_listbox.insert(tk.END, dirname)

    def clear_files(self):
        """Clear all files from list"""
        self.files_listbox.delete(0, tk.END)

    def remove_selected_files(self):
        """Remove selected files from list"""
        selection = self.files_listbox.curselection()
        for index in reversed(selection):
            self.files_listbox.delete(index)

    def toggle_split_options(self):
        """Enable/disable split options based on checkbox"""
        if self.enable_split_var.get():
            self.split_size_entry.config(state=tk.NORMAL)
            self.split_output_entry.config(state=tk.NORMAL)
            self.split_browse_btn.config(state=tk.NORMAL)
        else:
            self.split_size_entry.config(state=tk.DISABLED)
            self.split_output_entry.config(state=tk.DISABLED)
            self.split_browse_btn.config(state=tk.DISABLED)

    def toggle_par2_options(self):
        """Enable/disable PAR2 options based on checkbox"""
        if self.enable_par2_var.get():
            self.par2_redundancy_entry.config(state=tk.NORMAL)
        else:
            self.par2_redundancy_entry.config(state=tk.DISABLED)

    def browse_split_output(self):
        """Browse for split files output directory"""
        dirname = filedialog.askdirectory(title="Select output directory for split files")
        if dirname:
            self.split_output_var.set(dirname)

    def check_par2(self):
        """Check if PAR2 is installed"""
        par2_cmd = self.file_processor.find_par2_executable()
        if par2_cmd:
            self.par2_status.config(text=f"✓ PAR2 found: {par2_cmd}", foreground="green")
            self.log_message(f"PAR2 found: {par2_cmd}")
        else:
            self.par2_status.config(text="✗ PAR2 not found", foreground="red")
            messagebox.showwarning("PAR2 Not Found",
                "PAR2 command-line tool not found.\n\n"
                "Please install par2cmdline:\n"
                "- Windows: Download from https://github.com/Parchive/par2cmdline/releases\n"
                "- Linux: sudo apt-get install par2 (or yum install par2cmdline)\n"
                "- macOS: brew install par2"
            )

    def build_command(self):
        """Build the Nyuu command from GUI settings"""
        nyuu_path = self.nyuu_path_var.get()
        if not nyuu_path or not os.path.exists(nyuu_path):
            raise ValueError("Nyuu executable not found. Please download or select a valid Nyuu executable.")

        cmd = [nyuu_path]

        # Server options
        if self.host_var.get():
            cmd.extend(["-h", self.host_var.get()])
        else:
            raise ValueError("Server host is required")

        if self.port_var.get():
            cmd.extend(["-P", self.port_var.get()])

        if self.ssl_var.get():
            cmd.append("-S")

        if self.ignore_cert_var.get():
            cmd.append("--ignore-cert")

        if self.user_var.get():
            cmd.extend(["-u", self.user_var.get()])

        if self.password_var.get():
            cmd.extend(["-p", self.password_var.get()])

        if self.connections_var.get():
            cmd.extend(["-n", self.connections_var.get()])

        # Article options
        if self.article_size_var.get():
            cmd.extend(["-a", self.article_size_var.get()])

        if self.comment_var.get():
            cmd.extend(["-t", self.comment_var.get()])

        if self.from_var.get():
            cmd.extend(["-f", self.from_var.get()])

        if self.groups_var.get():
            cmd.extend(["-g", self.groups_var.get()])
        else:
            raise ValueError("At least one newsgroup is required")

        # Check options
        if self.check_enabled_var.get():
            cmd.append(f"--check-connections={self.check_connections_var.get()}")
            cmd.extend(["--check-tries", self.check_tries_var.get()])
            cmd.extend(["--check-delay", self.check_delay_var.get()])
            cmd.extend(["--check-retry-delay", self.check_retry_delay_var.get()])
            cmd.extend(["--check-post-tries", self.check_post_tries_var.get()])

        # NZB output
        if self.nzb_output_var.get():
            cmd.extend(["-o", self.nzb_output_var.get()])

        if self.nzb_overwrite_var.get():
            cmd.append("-O")

        if self.nzb_title_var.get():
            cmd.extend(["--nzb-title", self.nzb_title_var.get()])

        if self.nzb_category_var.get():
            cmd.extend(["--nzb-category", self.nzb_category_var.get()])

        if self.nzb_tag_var.get():
            cmd.extend(["--nzb-tag", self.nzb_tag_var.get()])

        if self.nzb_password_var.get():
            cmd.extend(["--nzb-password", self.nzb_password_var.get()])

        # Advanced options
        if self.skip_errors_var.get():
            cmd.extend(["-e", "all"])

        if self.quiet_var.get():
            cmd.append("-q")

        if self.recursive_var.get():
            cmd.extend(["-r", "keep"])

        # Custom arguments
        if self.custom_args_var.get():
            cmd.extend(self.custom_args_var.get().split())

        # Files
        files = list(self.files_listbox.get(0, tk.END))
        if not files:
            raise ValueError("No files selected for upload")

        cmd.extend(files)

        return cmd

    def view_command(self):
        """Display the command that would be executed"""
        try:
            cmd = self.build_command()
            # Mask password in display
            display_cmd = cmd.copy()
            if "-p" in display_cmd:
                pwd_index = display_cmd.index("-p") + 1
                display_cmd[pwd_index] = "****"

            command_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in display_cmd)
            messagebox.showinfo("Command", f"Command to execute:\n\n{command_str}")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def process_files_before_upload(self):
        """Process files (split and create PAR2) before upload"""
        files = list(self.files_listbox.get(0, tk.END))
        if not files:
            return files

        processed_files = []

        try:
            # File splitting
            if self.enable_split_var.get():
                self.log_message("="*80)
                self.log_message("Processing files: Splitting enabled")
                split_size = int(self.split_size_var.get())
                split_output = self.split_output_var.get() or None

                for filepath in files:
                    if os.path.isfile(filepath):
                        self.log_message(f"Checking file: {filepath}")

                        def progress_callback(status, message):
                            self.log_message(f"  {message}")

                        chunks = self.file_processor.split_file(
                            filepath, split_size, split_output, progress_callback
                        )
                        processed_files.extend(chunks)
                    else:
                        # Directory - add as is
                        processed_files.append(filepath)
            else:
                processed_files = files

            # PAR2 creation
            if self.enable_par2_var.get():
                self.log_message("="*80)
                self.log_message("Creating PAR2 recovery files...")
                redundancy = int(self.par2_redundancy_var.get())

                def progress_callback(status, message):
                    self.log_message(f"  {message}")

                # Create PAR2 for all files
                par2_files = self.file_processor.create_par2(
                    processed_files, redundancy, progress_callback=progress_callback
                )

                # Add PAR2 files to upload list
                processed_files.extend(par2_files)
                self.log_message(f"Added {len(par2_files)} PAR2 files to upload")

            return processed_files

        except Exception as e:
            raise Exception(f"File processing failed: {str(e)}")

    def start_upload(self):
        """Start the upload process"""
        try:
            # First, process files if needed
            processed_files = None
            if self.enable_split_var.get() or self.enable_par2_var.get():
                self.log_message("="*80)
                self.log_message("Pre-processing files...")
                self.status_label.config(text="Processing files...", foreground="blue")

                try:
                    processed_files = self.process_files_before_upload()
                except Exception as e:
                    messagebox.showerror("Processing Error", str(e))
                    self.log_message(f"✗ Processing failed: {str(e)}")
                    return

            # Build command with processed files
            cmd = self.build_command()

            # Replace file arguments with processed files if any
            if processed_files:
                # Find where files start in command (after all the options)
                original_files = list(self.files_listbox.get(0, tk.END))
                for orig_file in original_files:
                    if orig_file in cmd:
                        idx = cmd.index(orig_file)
                        cmd.pop(idx)

                # Add processed files
                cmd.extend([str(f) for f in processed_files])

            self.log_message("="*80)
            self.log_message("Starting upload...")
            self.log_message(f"Command: {' '.join(cmd[:3])}... (truncated for security)")
            self.log_message("="*80)

            # Start process in thread
            def run_process():
                try:
                    self.nyuu_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1
                    )

                    # Read output
                    for line in self.nyuu_process.stdout:
                        self.root.after(0, lambda l=line: self.log_message(l.rstrip()))

                    # Wait for completion
                    self.nyuu_process.wait()

                    if self.nyuu_process.returncode == 0:
                        self.root.after(0, lambda: self.log_message("\n✓ Upload completed successfully!"))
                        self.root.after(0, lambda: self.status_label.config(
                            text="Upload Complete", foreground="green"))
                    else:
                        self.root.after(0, lambda: self.log_message(
                            f"\n✗ Upload failed with exit code {self.nyuu_process.returncode}"))
                        self.root.after(0, lambda: self.status_label.config(
                            text="Upload Failed", foreground="red"))

                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"\n✗ Error: {str(e)}"))
                    self.root.after(0, lambda: self.status_label.config(
                        text="Error", foreground="red"))
                finally:
                    self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                    self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
                    self.nyuu_process = None

            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_label.config(text="Uploading...", foreground="blue")

            thread = threading.Thread(target=run_process, daemon=True)
            thread.start()

        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def stop_upload(self):
        """Stop the upload process"""
        if self.nyuu_process:
            self.nyuu_process.terminate()
            self.log_message("\n⚠ Upload stopped by user")
            self.status_label.config(text="Stopped", foreground="orange")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def log_message(self, message):
        """Add message to console"""
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)

    def clear_console(self):
        """Clear console output"""
        self.console_text.delete(1.0, tk.END)

    def save_config(self):
        """Save current settings to JSON file"""
        config = {
            'server': {
                'host': self.host_var.get(),
                'port': self.port_var.get(),
                'ssl': self.ssl_var.get(),
                'ignore_cert': self.ignore_cert_var.get(),
                'user': self.user_var.get(),
                'password': self.password_var.get(),
                'connections': self.connections_var.get()
            },
            'posting': {
                'article_size': self.article_size_var.get(),
                'comment': self.comment_var.get(),
                'from': self.from_var.get(),
                'groups': self.groups_var.get()
            },
            'verification': {
                'enabled': self.check_enabled_var.get(),
                'connections': self.check_connections_var.get(),
                'tries': self.check_tries_var.get(),
                'delay': self.check_delay_var.get(),
                'retry_delay': self.check_retry_delay_var.get(),
                'post_tries': self.check_post_tries_var.get()
            },
            'nzb': {
                'output': self.nzb_output_var.get(),
                'overwrite': self.nzb_overwrite_var.get(),
                'title': self.nzb_title_var.get(),
                'category': self.nzb_category_var.get(),
                'tag': self.nzb_tag_var.get(),
                'password': self.nzb_password_var.get()
            },
            'advanced': {
                'skip_errors': self.skip_errors_var.get(),
                'quiet': self.quiet_var.get(),
                'recursive': self.recursive_var.get(),
                'custom_args': self.custom_args_var.get()
            },
            'nyuu_path': self.nyuu_path_var.get()
        }

        filename = filedialog.asksaveasfilename(
            title="Save configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            with open(filename, 'w') as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Success", "Configuration saved successfully!")

    def load_config_file(self):
        """Load settings from JSON file"""
        filename = filedialog.askopenfilename(
            title="Load configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)

                # Load server settings
                if 'server' in config:
                    s = config['server']
                    self.host_var.set(s.get('host', ''))
                    self.port_var.set(s.get('port', '119'))
                    self.ssl_var.set(s.get('ssl', False))
                    self.ignore_cert_var.set(s.get('ignore_cert', False))
                    self.user_var.set(s.get('user', ''))
                    self.password_var.set(s.get('password', ''))
                    self.connections_var.set(s.get('connections', '3'))

                # Load posting settings
                if 'posting' in config:
                    p = config['posting']
                    self.article_size_var.set(p.get('article_size', '700K'))
                    self.comment_var.set(p.get('comment', ''))
                    self.from_var.set(p.get('from', ''))
                    self.groups_var.set(p.get('groups', ''))

                # Load verification settings
                if 'verification' in config:
                    v = config['verification']
                    self.check_enabled_var.set(v.get('enabled', False))
                    self.check_connections_var.set(v.get('connections', '1'))
                    self.check_tries_var.set(v.get('tries', '2'))
                    self.check_delay_var.set(v.get('delay', '5s'))
                    self.check_retry_delay_var.set(v.get('retry_delay', '30s'))
                    self.check_post_tries_var.set(v.get('post_tries', '1'))

                # Load NZB settings
                if 'nzb' in config:
                    n = config['nzb']
                    self.nzb_output_var.set(n.get('output', ''))
                    self.nzb_overwrite_var.set(n.get('overwrite', False))
                    self.nzb_title_var.set(n.get('title', ''))
                    self.nzb_category_var.set(n.get('category', ''))
                    self.nzb_tag_var.set(n.get('tag', ''))
                    self.nzb_password_var.set(n.get('password', ''))

                # Load advanced settings
                if 'advanced' in config:
                    a = config['advanced']
                    self.skip_errors_var.set(a.get('skip_errors', False))
                    self.quiet_var.set(a.get('quiet', False))
                    self.recursive_var.set(a.get('recursive', False))
                    self.custom_args_var.set(a.get('custom_args', ''))

                # Load Nyuu path
                if 'nyuu_path' in config:
                    self.nyuu_path_var.set(config['nyuu_path'])

                messagebox.showinfo("Success", "Configuration loaded successfully!")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")

    def load_config(self):
        """Load config from default file if it exists"""
        config_file = Path("nyuu_gui_config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)

                if 'nyuu_path' in config:
                    self.nyuu_path_var.set(config['nyuu_path'])
                    if os.path.exists(config['nyuu_path']):
                        self.download_status.config(
                            text=f"✓ Using: {config['nyuu_path']}",
                            foreground="green")
            except:
                pass


def main():
    root = tk.Tk()
    app = NyuuGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
