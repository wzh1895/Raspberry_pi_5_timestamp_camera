#!/usr/bin/env python3
import gi
import os
import datetime

gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gst, Gtk, GLib

Gst.init(None)

class CameraApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Camera Controller")
        self.set_default_size(800, 600)

        # Main container: video preview on top, buttons at bottom.
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(self.vbox)

        # Video preview area.
        self.video_box = Gtk.Box()
        self.vbox.pack_start(self.video_box, True, True, 0)

        # Button area.
        button_box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.HORIZONTAL)
        self.vbox.pack_start(button_box, False, False, 0)

        self.preview_button = Gtk.Button(label="Preview")
        self.photo_button   = Gtk.Button(label="Photo")
        self.record_button  = Gtk.Button(label="Record")
        button_box.pack_start(self.preview_button, True, True, 0)
        button_box.pack_start(self.photo_button, True, True, 0)
        button_box.pack_start(self.record_button, True, True, 0)

        self.preview_button.connect("clicked", self.on_preview_clicked)
        self.photo_button.connect("clicked", self.on_photo_clicked)
        self.record_button.connect("clicked", self.on_record_clicked)

        self.pipeline = None
        self.mode = None  # "preview" or "record"

        # Check if gtksink is available; if not, fall back to autovideosink.
        if Gst.ElementFactory.find("gtksink") is not None:
            self.video_sink_element = "gtksink name=video_sink"
            self.embed_video = True
        else:
            self.video_sink_element = "autovideosink"
            self.embed_video = False
            print("Warning: gtksink not found. Using autovideosink; preview will open in a separate window.")

    def choose_encoder(self):
        # Try to use x264enc if available; otherwise try openh264enc.
        if Gst.ElementFactory.find("x264enc") is not None:
            return "x264enc"
        elif Gst.ElementFactory.find("openh264enc") is not None:
            return "openh264enc"
        else:
            print("Error: No H264 encoder available. Please install gstreamer1.0-plugins-ugly or an alternative encoder.")
            return "x264enc"  # This will likely trigger a parse error.

    def build_preview_pipeline(self):
        pipeline_desc = (
            "libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t "
            "t. ! queue ! videoscale ! video/x-raw,width=640,height=360 ! videoconvert ! " + self.video_sink_element + " "
            "t. ! queue ! videoconvert ! jpegenc ! appsink name=photo_sink max-buffers=1 drop=true"
        )
        return Gst.parse_launch(pipeline_desc)

    def build_record_pipeline(self, video_filename):
        encoder = self.choose_encoder()
        pipeline_desc = (
            "libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t "
            "t. ! queue ! videoscale ! video/x-raw,width=640,height=360 ! videoconvert ! " + self.video_sink_element + " "
            "t. ! queue ! videoconvert ! " + encoder + " speed-preset=ultrafast tune=zerolatency ! mp4mux ! filesink name=file_sink "
            "t. ! queue ! videoconvert ! jpegenc ! appsink name=photo_sink max-buffers=1 drop=true"
        )
        pipeline = Gst.parse_launch(pipeline_desc)
        file_sink = pipeline.get_by_name("file_sink")
        file_sink.set_property("location", video_filename)
        return pipeline

    def embed_video_widget(self):
        """
        Ensure the gtksink widget is reparented into our video_box.
        If the widget is floating in its own top-level window, we hide that window and reparent it.
        """
        if self.pipeline is None or not self.embed_video:
            return False
        gtksink = self.pipeline.get_by_name("video_sink")
        if gtksink is not None:
            video_widget = gtksink.props.widget
            if video_widget is not None:
                # If the widget is currently in a toplevel window different from our main window, hide that window.
                toplevel = video_widget.get_toplevel()
                if isinstance(toplevel, Gtk.Window) and toplevel is not self:
                    toplevel.hide()
                # Reparent the widget if needed.
                parent = video_widget.get_parent()
                if parent is not None and parent is not self.video_box:
                    parent.remove(video_widget)
                if video_widget.get_parent() is None:
                    self.video_box.pack_start(video_widget, True, True, 0)
                video_widget.show_all()
        return False  # Stop idle callback.

    def on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            print("EOS received. Finalizing recording.")
            self.stop_pipeline()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print("Error:", err, debug)
            self.stop_pipeline()

    def stop_pipeline(self):
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.mode = None
            self.record_button.set_label("Record")
            # Remove any embedded video widget.
            if self.embed_video:
                for child in self.video_box.get_children():
                    self.video_box.remove(child)

    def on_preview_clicked(self, widget):
        self.stop_pipeline()
        self.pipeline = self.build_preview_pipeline()
        self.pipeline.set_state(Gst.State.PLAYING)
        self.mode = "preview"
        # Add a bus watch (for errors) even in preview mode.
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        if self.embed_video:
            GLib.idle_add(self.embed_video_widget)
        print("Preview started.")

    def on_record_clicked(self, widget):
        if self.mode != "record":
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
            print("Recording started.")
        else:
            print("Stopping recording... sending EOS")
            self.pipeline.send_event(Gst.Event.new_eos())
            # The EOS message from the bus will call stop_pipeline() once the file is finalized.

    def on_photo_clicked(self, widget):
        if self.pipeline is None:
            print("No active pipeline. Please start preview or recording first.")
            return
        appsink = self.pipeline.get_by_name("photo_sink")
        if appsink is None:
            print("Appsink not found in the pipeline!")
            return
        sample = appsink.emit("try-pull-sample", 1 * Gst.SECOND)
        if sample:
            buf = sample.get_buffer()
            result, mapinfo = buf.map(Gst.MapFlags.READ)
            if result:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                photo_filename = os.path.expanduser(f"~/Pictures/photo_{timestamp}.jpg")
                with open(photo_filename, "wb") as f:
                    f.write(mapinfo.data)
                print(f"Photo saved to {photo_filename}")
                buf.unmap(mapinfo)
            else:
                print("Could not map buffer for reading.")
        else:
            print("Failed to capture photo sample.")

def main():
    os.makedirs(os.path.expanduser("~/Pictures"), exist_ok=True)
    os.makedirs(os.path.expanduser("~/Videos"), exist_ok=True)

    app = CameraApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
