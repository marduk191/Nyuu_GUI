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

    def extract_archive(self, filepath):
        """Extract downloaded archive"""
        extract_dir = self.download_dir / filepath.stem
        extract_dir.mkdir(exist_ok=True)

        if filepath.suffix == '.xz' or '.tar' in filepath.name:
            with tarfile.open(filepath, 'r:xz') as tar:
                tar.extractall(extract_dir)
        elif filepath.suffix == '.7z':
            # Use py7zr library for 7z extraction
            try:
                with py7zr.SevenZipFile(filepath, mode='r') as archive:
                    archive.extractall(path=extract_dir)
            except Exception as e:
                raise Exception(f"7z extraction failed: {str(e)}")

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

        extract_dir = self.extract_archive(filepath)

        # Find executable
        if progress_callback:
            progress_callback("locating", "Locating Nyuu executable...")

        self.nyuu_executable = self.find_nyuu_executable(extract_dir)

        if progress_callback:
            progress_callback("complete", f"Nyuu {version} ready!")

        return self.nyuu_executable


class NyuuGUI:
    """Main GUI application for Nyuu"""

    def __init__(self, root):
        self.root = root
        self.root.title("Nyuu GUI - Usenet Binary Poster")
        self.root.geometry("900x800")

        self.downloader = NyuuDownloader()
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

    def start_upload(self):
        """Start the upload process"""
        try:
            cmd = self.build_command()

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
