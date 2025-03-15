# Raspberry Pi 5 Camera

Raspberry Pi 5 Camera is a utility designed for industrial applications and process monitoring. It provides both photo capture and video recording capabilities with embedded timestamp overlays, ensuring that every moment is precisely logged. Ideal for recording machine operations, industrial processes, and other scenarios where accurate timekeeping is essential.

## Features

- **Dual Functionality:**  
  Capture high-resolution still images and record high-quality videos from a Raspberry Pi 5 camera module.

- **Timestamp Overlays:**  
  Automatically embeds current date/time information on photos and videos. In video recordings, it displays both the current timestamp and elapsed recording time.

- **Live Preview:**  
  Displays a real-time video preview with a crosshair overlay to assist in framing the subject accurately.

- **User-Friendly Interface:**  
  A tabbed interface allows you to switch between the Camera, Photos, and Videos views.  
  - **Camera Tab:** Preview live video, capture photos, and record videos.
  - **Photos Tab:** Browse through captured images, with dynamic scaling to fit the display area.
  - **Videos Tab:** Browse and play back recorded videos with basic controls (play, pause, seek, and progress display).

- **Recording:**  
  Utilizes GStreamer pipelines and splitmuxsink to ensure videos are finalized correctly even under industrial conditions.

- **Automatic Startup:**  
  Easily configure the utility to start automatically on Raspberry Pi desktop login.

## System Requirements

- **Hardware:**  
  Raspberry Pi 5 with a compatible camera module (e.g., OV5467, OV5647, etc.) and a display (preferrably a touch screen such as XPT2046 for easier operation).

- **Software:**  
  - Raspberry Pi OS (Bullseye or later recommended)  
  - GStreamer 1.0 and associated plugins (`gstreamer1.0-plugins-base`, `gstreamer1.0-plugins-good`, `gstreamer1.0-plugins-bad`, `gstreamer1.0-plugins-ugly`)
  - Python 3 with PyGObject

## Installation

1. **Install Required Packages:**  
   Update your package lists and install GStreamer and Python GObject packages:
   ```bash
   sudo apt-get update
   sudo apt-get install python3-gi gir1.2-gtk-3.0 gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly fonts-noto-color-emoji
   ```

2. **Download the Project:**  
   Clone or download the project repository to your Raspberry Pi.

3. **Make the Script Executable:**  
   Navigate to the project directory and run:
   ```bash
   chmod +x camera.py
   ```

4. **Autostart Setup (Optional):**  
   Create a `.desktop` file in `~/.config/autostart/` with the following content (adjust the Exec path):
   ```ini
   [Desktop Entry]
   Type=Application
   Name=Raspberry Pi 5 Camera
   Exec=/full/path/to/camera.py
   X-GNOME-Autostart-enabled=true
   Comment=Start the Raspberry Pi 5 Camera utility on login.
   ```

## Usage

- **Camera Tab:**  
  The live preview window displays a real-time feed with crosshair and timestamp overlays.  
  - Click the **Photo** button (📷) to capture a still image.
  - Click the **Record** button (⏺) to begin recording. The button toggles to a stop symbol (⏹) during recording. Timestamps and elapsed time are overlaid on the video.
  
- **Photos Tab:**  
  Browse and view captured images. The file list refreshes automatically when switching to this tab, and images are scaled dynamically to fit the display area.

- **Videos Tab:**  
  Browse and play back recorded videos. Use the play/pause button and progress bar with time labels to control playback. Video playback is embedded within the tab and stops automatically when you leave the tab.

## Troubleshooting

- **Video Playback Issues:**  
  If the video playback window appears separately, ensure that all GStreamer plugins are installed and that the system is running an updated version of Raspberry Pi OS.
  
- **Autostart Problems:**  
  Check the `~/.xsession-errors` file or use `journalctl --user -b` to review autostart errors.
  
- **Emoji Not Displaying:**  
  Install an emoji font such as [Noto Color Emoji](https://www.google.com/get/noto/#emoji) using `sudo apt-get install fonts-noto-color-emoji`.

## Contributing

Contributions and suggestions are welcome! Please open issues or submit pull requests if you have improvements or bug fixes.

## License

This project is open-source and available under the [MIT License](LICENSE).
