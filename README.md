# Nyuu GUI - Comprehensive Usenet Binary Poster Interface

A full-featured graphical user interface for [Nyuu](https://github.com/animetosho/Nyuu), the high-performance Usenet binary posting tool. Built with Python and tkinter, this GUI makes posting to Usenet simple and accessible.

![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

### 🚀 Automatic Nyuu Management
- **One-click download** of Nyuu binaries from GitHub releases
- **Multi-platform support**: Linux (x64, ARM64), macOS, Windows
- **Automatic tool downloads** on Windows: 7-Zip and par2cmdline downloaded automatically when needed
- **Zero manual configuration** - works out of the box
- **Or use your own** existing Nyuu installation

### 📡 Server Configuration
- NNTP server settings (host, port, SSL/TLS)
- Authentication (username/password)
- Multi-connection support for faster uploads
- SSL certificate validation options

### 📮 Posting Options
- Configurable article size
- Custom subject/comment
- From field customization
- Multiple newsgroup support
- Post verification with configurable retry logic

### 📄 NZB Generation
- Automatic NZB file creation
- NZB metadata support (title, category, tags, password)
- Overwrite protection

### 📁 File Management
- Add individual files or entire directories
- Recursive directory processing
- Visual file list management
- Drag-and-drop support (planned)

### 🔧 File Preparation
- **File Splitting**: Automatically split large files into smaller chunks
- **PAR2 Recovery**: Create parity files for data recovery (auto-downloads par2cmdline on Windows!)
- Configurable split size and redundancy percentage
- Automatic processing before upload

### ⚙️ Advanced Features
- Error handling configuration
- Quiet mode
- Custom Nyuu arguments
- Configuration save/load (JSON)
- Real-time console output
- Command preview

## Installation

### Prerequisites

- Python 3.6 or higher
- pip (Python package installer)
- **Windows users**: Both 7-Zip and par2cmdline will be downloaded automatically if needed!
- **Linux/macOS users** (optional for PAR2):
  - Linux: `sudo apt-get install par2` or `sudo yum install par2cmdline`
  - macOS: `brew install par2`

### Setup

1. Clone this repository:
```bash
git clone https://github.com/marduk191/Nyuu_GUI.git
cd Nyuu_GUI
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python nyuu_gui.py
```

Or make it executable:
```bash
chmod +x nyuu_gui.py
./nyuu_gui.py
```

## Usage

### Quick Start

1. **Download Nyuu**:
   - Go to the "Nyuu Setup" tab
   - Select your operating system
   - Click "Download Latest Release"
   - Wait for the download and extraction to complete

2. **Configure Server**:
   - Go to the "Server Config" tab
   - Enter your NNTP server details
   - Configure SSL if required
   - Set the number of connections

3. **Configure Posting**:
   - Go to the "Posting Options" tab
   - Set article size (default: 700K)
   - Enter newsgroups (comma-separated)
   - Add subject/comment if desired

4. **Add Files**:
   - Go to the "Files" tab
   - Add files or directories to upload
   - Enable "Include Subdirectories" if needed

5. **(Optional) Configure File Preparation**:
   - Go to the "File Preparation" tab
   - Enable file splitting if needed (splits large files into chunks)
   - Enable PAR2 creation for data recovery (requires par2cmdline)
   - Files will be automatically processed before upload

6. **Configure NZB Output**:
   - Go to the "NZB Output" tab
   - Set output file path
   - Add metadata if desired

7. **Start Upload**:
   - Click "Start Upload" button
   - Monitor progress in the "Console" tab

### Configuration Management

#### Save Configuration
1. Configure all settings as desired
2. Go to "Advanced" tab
3. Click "Save Current Settings"
4. Choose a location for your JSON config file

#### Load Configuration
1. Go to "Advanced" tab
2. Click "Load Settings"
3. Select your previously saved JSON config file

The application also auto-saves the Nyuu path to `nyuu_gui_config.json` for convenience.

## Detailed Features

### Server Configuration Tab

| Setting | Description | Default |
|---------|-------------|---------|
| Host | NNTP server address | - |
| Port | Server port | 119 (563 for SSL) |
| Use SSL/TLS | Enable encrypted connection | Off |
| Ignore SSL Cert Errors | Skip certificate validation | Off |
| Username | Server authentication username | - |
| Password | Server authentication password | - |
| Connections | Number of simultaneous connections | 3 |

### Posting Options Tab

**Article Settings:**
- **Article Size**: Target size per post (e.g., 700K, 1M)
- **Comment/Subject**: Prepended to post subject
- **From**: Sender identity
- **Newsgroups**: Comma-separated list (required)

**Post Verification:**
- Enable automatic post checking
- Configure retry attempts and delays
- Re-posting for failed articles

### File Preparation Tab

**File Splitting:**
- Enable/disable automatic file splitting
- Set split size in MB (e.g., 100MB chunks)
- Custom output directory for split files
- Files larger than split size are automatically split before upload

**PAR2 Recovery Files:**
- Enable/disable PAR2 creation
- Set redundancy percentage (1-100%, default 10%)
- Check PAR2 installation status
- Automatically creates recovery files for all uploaded content

**Benefits:**
- **Splitting**: Helpful for servers with file size limits, easier downloads
- **PAR2**: Essential for Usenet - allows recovery of missing/corrupted data
- **Automatic**: Files are processed before upload with no manual steps

### NZB Output Tab

**File Settings:**
- Output path for NZB file
- Overwrite protection option

**Metadata:**
- Title
- Category
- Tag
- Password (for encrypted posts)

### Advanced Options

**Error Handling:**
- Skip errors and continue processing

**UI Options:**
- Quiet mode (minimal console output)

**Configuration:**
- Save/Load settings to/from JSON
- Reusable configurations for different scenarios

**Custom Arguments:**
- Pass additional Nyuu command-line arguments
- For advanced users and special use cases

## Supported Nyuu Versions

The GUI is compatible with Nyuu v0.4.2 and later. It automatically downloads the latest release from the [official GitHub repository](https://github.com/animetosho/Nyuu).

### Supported Platforms

- **Linux x64** (amd64)
- **Linux ARM64** (aarch64)
- **macOS x64**
- **Windows 32-bit**

## Troubleshooting

### Cannot Download Nyuu

**Problem**: Download fails or times out

**Solutions**:
- Check your internet connection
- Try again later (GitHub may be temporarily unavailable)
- Manually download from [Nyuu releases](https://github.com/animetosho/Nyuu/releases) and use "Browse" to select it

### Extraction Failed

**Problem**: Archive extraction fails

**Solutions**:
- Ensure you have installed all dependencies: `pip install -r requirements.txt`
- **For Windows users**: The application automatically downloads a standalone 7-Zip binary if needed (no manual installation required!)
- If automatic download fails, manually install [7-Zip](https://www.7-zip.org/)
- For Linux/macOS .tar.xz files, Python's built-in tarfile module is used (no additional tools needed)
- Check that you have write permissions in the application directory
- Verify the downloaded file isn't corrupted by re-downloading

### Upload Fails Immediately

**Problem**: Upload stops right after starting

**Solutions**:
- Verify server credentials
- Check newsgroup names (must exist on server)
- Review console output for specific errors
- Test server connection with standalone Nyuu

### SSL Certificate Errors

**Problem**: SSL connection fails

**Solutions**:
- Enable "Ignore SSL Certificate Errors" option
- Update Python's SSL certificates
- Contact your server provider

## Building from Source

If you want to create a standalone executable:

### Using PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name="NyuuGUI" nyuu_gui.py
```

The executable will be in the `dist/` directory.

## Dependencies

- **requests**: For downloading Nyuu binaries from GitHub
- **py7zr**: For extracting .7z archives (Windows builds)
- **tkinter**: GUI framework (included with Python)

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Acknowledgments

- [Nyuu](https://github.com/animetosho/Nyuu) by animetosho - The excellent Usenet posting tool this GUI wraps
- Python tkinter community for GUI guidance

## Support

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/marduk191/Nyuu_GUI/issues)
- Check [Nyuu documentation](https://github.com/animetosho/Nyuu) for Nyuu-specific questions

## Disclaimer

This tool is for legitimate Usenet usage only. Users are responsible for ensuring their usage complies with their Usenet provider's terms of service and applicable laws.

## Roadmap

- [x] File splitting
- [x] PAR2 recovery file creation
- [x] Automatic PAR2 download (similar to 7-Zip)
- [x] Automatic 7-Zip download for Windows
- [ ] Drag-and-drop file support
- [ ] Upload queue management
- [ ] Upload presets/profiles
- [ ] Dark mode theme
- [ ] Upload history
- [ ] Bandwidth throttling
- [ ] Multi-language support
- [ ] System tray integration

---

**Made with ❤️ for the Usenet community**
