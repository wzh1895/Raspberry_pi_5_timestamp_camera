#!/usr/bin/env python3
import gi
import os
import datetime
import logging

gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gst, Gtk, GLib

# Set up verbose logging.
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
        self.set_default_size(800, 600)

        # Main container: video preview area on top, buttons at bottom.
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(self.vbox)

        # Video preview area.
        self.video_box = Gtk.Box()
        self.vbox.pack_start(self.video_box, True, True, 0)

        # Button area (only Photo and Record buttons).
        button_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        self.vbox.pack_start(button_box, False, False, 0)
        self.photo_button  = Gtk.Button(label="Photo")
        self.record_button = Gtk.Button(label="Record")
        button_box.pack_start(self.photo_button, True, True, 0)
        button_box.pack_start(self.record_button, True, True, 0)
        self.photo_button.connect("clicked", self.on_photo_clicked)
        self.record_button.connect("clicked", self.on_record_clicked)

        self.pipeline = None
        self.mode = None  # Either "preview" or "record"

        # Use gtksink if available.
        if Gst.ElementFactory.find("gtksink") is not None:
            self.video_sink_element = "gtksink name=video_sink"
            self.embed_video = True
            logger.debug("Using gtksink for video embedding.")
        else:
            self.video_sink_element = "autovideosink"
            self.embed_video = False
            logger.warning("gtksink not found. Using autovideosink; preview will open in a separate window.")

        # Auto-start preview.
        GLib.idle_add(self.on_preview_clicked, None)

    def choose_encoder(self):
        if Gst.ElementFactory.find("x264enc"):
            logger.debug("Using x264enc as H264 encoder.")
            return "x264enc"
        elif Gst.ElementFactory.find("openh264enc"):
            logger.debug("Using openh264enc as H264 encoder.")
            return "openh264enc"
        else:
            logger.error("No H264 encoder available. Install gstreamer1.0-plugins-ugly or similar.")
            return "x264enc"  # May trigger a parse error.

    def build_preview_pipeline(self):
        pipeline_desc = (
            "libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t "
            "t. ! queue ! videoscale ! video/x-raw,width=640,height=360 ! videoconvert ! " + self.video_sink_element + " "
            "t. ! queue ! videoconvert ! jpegenc ! appsink name=photo_sink max-buffers=1 drop=true"
        )
        logger.debug("Building preview pipeline:\n%s", pipeline_desc)
        return Gst.parse_launch(pipeline_desc)

    def build_record_pipeline(self, video_filename):
        encoder = self.choose_encoder()
        # splitmuxsink finalizes the file on EOS.
        pipeline_desc = (
            "libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t "
            "t. ! queue ! videoconvert ! " + self.video_sink_element + " "  # Preview branch.
            "t. ! queue ! videoconvert ! " + encoder + " speed-preset=ultrafast tune=zerolatency ! splitmuxsink name=splitmux "  # Recording branch.
            "t. ! queue ! videoconvert ! jpegenc ! appsink name=photo_sink max-buffers=1 drop=true"   # Photo branch.
        )
        logger.debug("Building record pipeline:\n%s", pipeline_desc)
        pipeline = Gst.parse_launch(pipeline_desc)
        splitmux = pipeline.get_by_name("splitmux")
        splitmux.set_property("location", video_filename)
        logger.debug("Recording file will be saved to: %s", video_filename)
        return pipeline

    def embed_video_widget(self):
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
                    logger.debug("Removing video widget from its old parent.")
                    parent.remove(video_widget)
                if not video_widget.get_parent():
                    logger.debug("Embedding video widget into main window.")
                    self.video_box.pack_start(video_widget, True, True, 0)
                video_widget.show_all()
        return False

    def on_bus_message(self, bus, message):
        t = message.type
        logger.debug("Bus message received: %s", t)
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error("Bus ERROR: %s, %s", err, debug)
            self.stop_pipeline()
        # We don't rely on EOS since splitmuxsink may not propagate it.
        else:
            logger.debug("Other bus message: %s", t)

    def restart_preview(self):
        logger.debug("Restarting preview...")
        self.stop_pipeline()
        self.on_preview_clicked(None)
        return False

    def fallback_handler(self):
        if self.mode == "record":
            logger.warning("Fallback: forcing pipeline stop and restarting preview.")
            self.restart_preview()
        return False

    def stop_pipeline(self):
        if self.pipeline:
            logger.debug("Stopping pipeline and setting state to NULL.")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.mode = None
            self.record_button.set_label("Record")
            for child in self.video_box.get_children():
                self.video_box.remove(child)

    def on_preview_clicked(self, widget):
        logger.debug("Starting preview pipeline...")
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
            logger.debug("Starting recording pipeline...")
            self.stop_pipeline()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = os.path.expanduser(f"~/Videos/video_{timestamp}.mp4")
            self.pipeline = self.build_record_pipeline(video_filename)
            self.pipeline.set_state(Gst.State.PLAYING)
            self.mode = "record"
            self.record_button.set_label("Stop")
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self.on_bus_message)
            if self.embed_video:
                GLib.idle_add(self.embed_video_widget)
            logger.info("Recording started.")
        else:
            logger.debug("Stopping recording... sending EOS event and waiting for finalization.")
            eos_event = Gst.Event.new_eos()
            result = self.pipeline.send_event(eos_event)
            if result:
                logger.info("EOS event sent successfully.")
            else:
                logger.error("Failed to send EOS event.")
            # Force a pipeline stop after 5000 ms.
            GLib.timeout_add(5000, self.fallback_handler)

    def on_photo_clicked(self, widget):
        if not self.pipeline:
            logger.warning("No active pipeline; cannot capture photo.")
            return
        appsink = self.pipeline.get_by_name("photo_sink")
        if not appsink:
            logger.error("Photo branch not found in pipeline!")
            return
        logger.debug("Capturing photo sample...")
        sample = appsink.emit("try-pull-sample", 1 * Gst.SECOND)
        if sample:
            buf = sample.get_buffer()
            result, mapinfo = buf.map(Gst.MapFlags.READ)
            if result:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                photo_filename = os.path.expanduser(f"~/Pictures/photo_{timestamp}.jpg")
                with open(photo_filename, "wb") as f:
                    f.write(mapinfo.data)
                logger.info("Photo saved to %s", photo_filename)
                buf.unmap(mapinfo)
            else:
                logger.error("Failed to map buffer for reading.")
        else:
            logger.error("No photo sample captured.")

def main():
    os.makedirs(os.path.expanduser("~/Pictures"), exist_ok=True)
    os.makedirs(os.path.expanduser("~/Videos"), exist_ok=True)
    app = CameraApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
