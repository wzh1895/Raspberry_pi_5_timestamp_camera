#!/usr/bin/env python3
import gi
import os
import datetime
import logging

gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gst, Gtk, GLib

# Configure verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

Gst.init(None)

class CameraApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Camera Controller")
        self.set_default_size(1000, 600)

        # Main container: horizontal box splitting window into two parts.
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(main_box)

        # Video preview area on the left.
        self.video_box = Gtk.Box()
        main_box.pack_start(self.video_box, True, True, 0)

        # Controls area on the right with no extra spacing.
        control_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        control_box.set_vexpand(True)
        main_box.pack_start(control_box, False, False, 0)

        # Vertical box for buttons to take equal space, no spacing.
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        button_box.set_vexpand(True)
        control_box.pack_start(button_box, True, True, 0)

        # Create buttons with symbols.
        self.photo_button  = Gtk.Button(label="📷")
        self.record_button = Gtk.Button(label="⏺")
        # Set each button to expand and fill half of the available height.
        self.photo_button.set_hexpand(True)
        self.photo_button.set_vexpand(True)
        self.record_button.set_hexpand(True)
        self.record_button.set_vexpand(True)
        button_box.pack_start(self.photo_button, True, True, 0)
        button_box.pack_start(self.record_button, True, True, 0)


        self.photo_button.connect("clicked", self.on_photo_clicked)
        self.record_button.connect("clicked", self.on_record_clicked)

        self.pipeline = None
        self.mode = None  # "preview" or "record"

        # Use gtksink if available, otherwise fall back.
        if Gst.ElementFactory.find("gtksink"):
            self.video_sink_element = "gtksink name=video_sink"
            self.embed_video = True
            logger.debug("Using gtksink for video embedding.")
        else:
            self.video_sink_element = "autovideosink"
            self.embed_video = False
            logger.warning("gtksink not found; using autovideosink => floating preview window.")

        # Start the preview automatically.
        GLib.idle_add(self.on_preview_clicked, None)

    def choose_encoder(self):
        if Gst.ElementFactory.find("x264enc"):
            logger.debug("Using x264enc as H.264 encoder.")
            return "x264enc"
        elif Gst.ElementFactory.find("openh264enc"):
            logger.debug("Using openh264enc as H.264 encoder.")
            return "openh264enc"
        else:
            logger.error("No H264 encoder found. Install gstreamer1.0-plugins-ugly or similar.")
            return "x264enc"

    def build_preview_pipeline(self):
        """
        Preview pipeline branches into:
          1) Crosshair + final preview sink with clock overlay.
          2) Crosshair + bottom-right date/time for photo capture.
        """
        pipeline_desc = f"""
            libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t
            t. ! queue ! videoscale ! video/x-raw,width=640,height=360 !
                textoverlay name=crosshair_pre1
                    text="+"
                    halignment=center
                    valignment=center
                    font-desc="Sans,48"
                    color=0xFFFFFF
                    draw-outline=true
                    outline-color=0x000000 !
                clockoverlay name=preview_clock
                    halignment=right
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-format="%Y-%m-%d %H:%M:%S" !
                videoconvert !
                {self.video_sink_element}
            t. ! queue !
                clockoverlay name=photo_clock
                    halignment=right
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-format="%Y-%m-%d %H:%M:%S" !
                videoconvert !
                jpegenc !
                appsink name=photo_sink max-buffers=1 drop=true
        """
        pipeline_desc = " ".join(pipeline_desc.split())
        logger.debug("Preview pipeline:\n%s", pipeline_desc)
        return Gst.parse_launch(pipeline_desc)

    def build_record_pipeline(self, video_filename):
        """
        Record pipeline branches into:
          1) Crosshair => show in preview sink with overlays.
          2) Crosshair => real date/time and elapsed time => splitmuxsink.
          3) Crosshair => real date/time for photo capture.
        """
        encoder = self.choose_encoder()
        pipeline_desc = f"""
            libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t
            t. ! queue !
                textoverlay name=crosshair_pre2
                    text="+"
                    halignment=center
                    valignment=center
                    font-desc="Sans,48"
                    color=0xFFFFFF
                    draw-outline=true
                    outline-color=0x000000 !
                clockoverlay name=video_preview_clock
                    halignment=right
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-format="%Y-%m-%d %H:%M:%S" !
                timeoverlay name=video_preview_elapsed_time
                    halignment=left
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-mode=elapsed-running-time !
                videoconvert !
                {self.video_sink_element}
            t. ! queue !
                clockoverlay name=video_clock
                    halignment=right
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-format="%Y-%m-%d %H:%M:%S" !
                timeoverlay name=video_elapsed_time
                    halignment=left
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-mode=elapsed-running-time !
                videoconvert ! {encoder} speed-preset=ultrafast tune=zerolatency ! splitmuxsink name=splitmux
            t. ! queue !
                clockoverlay name=video_photo_clock
                    halignment=right
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-format="%Y-%m-%d %H:%M:%S" !
                timeoverlay name=video_photo_elapsed_time
                    halignment=left
                    valignment=bottom
                    shaded-background=true
                    font-desc="Sans,20"
                    time-mode=elapsed-running-time !
                videoconvert ! jpegenc ! appsink name=photo_sink max-buffers=1 drop=true
        """
        pipeline_desc = " ".join(pipeline_desc.split())
        logger.debug("Record pipeline:\n%s", pipeline_desc)
        pipeline = Gst.parse_launch(pipeline_desc)
        splitmux = pipeline.get_by_name("splitmux")
        splitmux.set_property("location", video_filename)
        logger.debug("Recording file -> %s", video_filename)
        return pipeline

    def embed_video_widget(self):
        """Embed the video sink widget into our GTK layout."""
        if not self.pipeline or not self.embed_video:
            return False
        gtksink = self.pipeline.get_by_name("video_sink")
        if gtksink:
            video_widget = gtksink.props.widget
            if video_widget:
                toplevel = video_widget.get_toplevel()
                if isinstance(toplevel, Gtk.Window) and toplevel is not self:
                    logger.debug("Hiding floating window of video widget.")
                    toplevel.hide()
                parent = video_widget.get_parent()
                if parent and parent is not self.video_box:
                    logger.debug("Removing video widget from old parent.")
                    parent.remove(video_widget)
                if not video_widget.get_parent():
                    logger.debug("Embedding video widget into main window.")
                    self.video_box.pack_start(video_widget, True, True, 0)
                video_widget.show_all()
        return False

    def on_bus_message(self, bus, message):
        """Handle bus messages for logging and error handling."""
        t = message.type
        logger.debug("Bus message: %s", t)
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error("Bus ERROR: %s - %s", err, debug)
            self.stop_pipeline()
        else:
            logger.debug("Other bus message: %s", t)

    def fallback_stop(self):
        """If EOS not seen, forcibly stop the pipeline."""
        if self.mode == "record":
            logger.warning("Forcing pipeline stop; restarting preview.")
            self.stop_pipeline()
            GLib.idle_add(self.on_preview_clicked, None)
        return False

    def stop_pipeline(self):
        if self.pipeline:
            logger.debug("Stopping pipeline => NULL state.")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.mode = None
            self.record_button.set_label("⏺")
            for child in self.video_box.get_children():
                self.video_box.remove(child)

    def on_preview_clicked(self, widget):
        """ Start the preview pipeline. """
        logger.debug("Starting PREVIEW pipeline...")
        self.stop_pipeline()
        self.pipeline = self.build_preview_pipeline()
        self.pipeline.set_state(Gst.State.PLAYING)
        self.mode = "preview"
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        if self.embed_video:
            GLib.idle_add(self.embed_video_widget)
        logger.info("Preview started.")

    def on_record_clicked(self, widget):
        if self.mode != "record":
            logger.debug("Starting RECORD pipeline...")
            self.stop_pipeline()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = os.path.expanduser(f"~/Videos/video_{timestamp}.mp4")
            self.pipeline = self.build_record_pipeline(video_filename)
            self.pipeline.set_state(Gst.State.PLAYING)
            self.mode = "record"
            self.record_button.set_label("⏹")
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            if self.embed_video:
                GLib.idle_add(self.embed_video_widget)
            logger.info("Recording started.")
        else:
            logger.debug("Stopping RECORD => sending EOS, waiting 2s, then fallback.")
            eos_event = Gst.Event.new_eos()
            result = self.pipeline.send_event(eos_event)
            if result:
                logger.info("EOS event sent successfully.")
            else:
                logger.error("Failed to send EOS event.")
            # Wait 2 seconds, then forcibly stop.
            GLib.timeout_add(2000, self.fallback_stop)

    def on_photo_clicked(self, widget):
        """
        Capture a photo from the 'photo_sink' branch.
        The branch has a clockoverlay in the bottom-right.
        """
        if not self.pipeline:
            logger.warning("No active pipeline => cannot capture photo.")
            return
        appsink = self.pipeline.get_by_name("photo_sink")
        if not appsink:
            logger.error("No 'photo_sink' in pipeline => cannot capture photo.")
            return

        logger.debug("Attempting to pull a photo sample...")
        sample = appsink.emit("try-pull-sample", 1 * Gst.SECOND)
        if sample:
            buf = sample.get_buffer()
            ok, mapinfo = buf.map(Gst.MapFlags.READ)
            if ok:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                photo_filename = os.path.expanduser(f"~/Pictures/photo_{timestamp}.jpg")
                with open(photo_filename, "wb") as f:
                    f.write(mapinfo.data)
                buf.unmap(mapinfo)
                logger.info(f"Photo saved to {photo_filename}")
            else:
                logger.error("Failed mapping buffer for reading.")
        else:
            logger.error("No sample pulled for photo; possibly no new frames available.")

def main():
    os.makedirs(os.path.expanduser("~/Pictures"), exist_ok=True)
    os.makedirs(os.path.expanduser("~/Videos"), exist_ok=True)
    app = CameraApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
