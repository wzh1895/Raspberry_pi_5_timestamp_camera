#!/usr/bin/env python3
import gi, os, datetime, logging
gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gst, Gtk, GLib, GdkPixbuf

# Configure verbose logging.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

Gst.init(None)

### CAMERA TAB ###
class CameraTab(Gtk.Box):
    def __init__(self):
        # Horizontal box: video on left, controls on right.
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Video preview area on the left.
        self.video_box = Gtk.Box()
        self.pack_start(self.video_box, True, True, 0)

        # Controls area on the right.
        control_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        control_box.set_vexpand(True)
        self.pack_start(control_box, False, False, 0)

        # Vertical box for buttons.
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        button_box.set_vexpand(True)
        control_box.pack_start(button_box, True, True, 0)

        # Create buttons (using symbols – if emoji not available, use text labels).
        self.photo_button  = Gtk.Button(label="📷")
        self.record_button = Gtk.Button(label="⏺")
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

        # Use gtksink if available.
        if Gst.ElementFactory.find("gtksink"):
            self.video_sink_element = "gtksink name=video_sink"
            self.embed_video = True
            logger.debug("CameraTab: using gtksink for video embedding.")
        else:
            self.video_sink_element = "autovideosink"
            self.embed_video = False
            logger.warning("CameraTab: gtksink not found; using autovideosink.")

        # Auto-start preview.
        GLib.idle_add(self.on_preview_clicked, None)

    def choose_encoder(self):
        if Gst.ElementFactory.find("x264enc"):
            logger.debug("CameraTab: Using x264enc as H.264 encoder.")
            return "x264enc"
        elif Gst.ElementFactory.find("openh264enc"):
            logger.debug("CameraTab: Using openh264enc as H.264 encoder.")
            return "openh264enc"
        else:
            logger.error("CameraTab: No H264 encoder found.")
            return "x264enc"

    def build_preview_pipeline(self):
        """
        Preview pipeline:
         - Branch 1: Crosshair + clock overlay + preview sink.
         - Branch 2: Clock overlay for photo capture.
        """
        pipeline_desc = f"""
            libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t
            t. ! queue ! videoscale ! video/x-raw,width=640,height=360 !
                textoverlay name=crosshair_pre1 text="+" halignment=center valignment=center
                    font-desc="Sans,48" color=0xFFFFFF draw-outline=true outline-color=0x000000 !
                clockoverlay name=preview_clock halignment=right valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-format="%Y-%m-%d %H:%M:%S" !
                videoconvert ! {self.video_sink_element}
            t. ! queue !
                clockoverlay name=photo_clock halignment=right valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-format="%Y-%m-%d %H:%M:%S" !
                videoconvert ! jpegenc ! appsink name=photo_sink max-buffers=1 drop=true
        """
        pipeline_desc = " ".join(pipeline_desc.split())
        logger.debug("CameraTab preview pipeline:\n%s", pipeline_desc)
        return Gst.parse_launch(pipeline_desc)

    def build_record_pipeline(self, video_filename):
        """
        Record pipeline:
         - Branch 1: Crosshair + overlays in preview sink.
         - Branch 2: Overlays (real time & elapsed) -> splitmuxsink.
         - Branch 3: Overlays for photo capture.
        """
        encoder = self.choose_encoder()
        pipeline_desc = f"""
            libcamerasrc name=cam ! videoconvert ! video/x-raw,format=NV12,width=1920,height=1080 ! tee name=t
            t. ! queue !
                textoverlay name=crosshair_pre2 text="+" halignment=center valignment=center
                    font-desc="Sans,48" color=0xFFFFFF draw-outline=true outline-color=0x000000 !
                clockoverlay name=video_preview_clock halignment=right valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-format="%Y-%m-%d %H:%M:%S" !
                timeoverlay name=video_preview_elapsed_time halignment=left valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-mode=elapsed-running-time !
                videoconvert ! {self.video_sink_element}
            t. ! queue !
                clockoverlay name=video_clock halignment=right valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-format="%Y-%m-%d %H:%M:%S" !
                timeoverlay name=video_elapsed_time halignment=left valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-mode=elapsed-running-time !
                videoconvert ! {encoder} speed-preset=ultrafast tune=zerolatency !
                splitmuxsink name=splitmux
            t. ! queue !
                clockoverlay name=video_photo_clock halignment=right valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-format="%Y-%m-%d %H:%M:%S" !
                timeoverlay name=video_photo_elapsed_time halignment=left valignment=bottom shaded-background=true
                    font-desc="Sans,20" time-mode=elapsed-running-time !
                videoconvert ! jpegenc ! appsink name=photo_sink max-buffers=1 drop=true
        """
        pipeline_desc = " ".join(pipeline_desc.split())
        logger.debug("CameraTab record pipeline:\n%s", pipeline_desc)
        pipeline = Gst.parse_launch(pipeline_desc)
        splitmux = pipeline.get_by_name("splitmux")
        splitmux.set_property("location", video_filename)
        logger.debug("CameraTab: Recording file -> %s", video_filename)
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
                    logger.debug("CameraTab: Hiding floating video widget window.")
                    toplevel.hide()
                parent = video_widget.get_parent()
                if parent and parent is not self.video_box:
                    logger.debug("CameraTab: Removing video widget from old parent.")
                    parent.remove(video_widget)
                if not video_widget.get_parent():
                    logger.debug("CameraTab: Embedding video widget into main window.")
                    self.video_box.pack_start(video_widget, True, True, 0)
                video_widget.show_all()
        return False

    def on_bus_message(self, bus, message):
        t = message.type
        logger.debug("CameraTab bus message: %s", t)
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error("CameraTab bus ERROR: %s - %s", err, debug)
            self.stop_pipeline()
        else:
            logger.debug("CameraTab other bus message: %s", t)

    def fallback_stop(self):
        if self.mode == "record":
            logger.warning("CameraTab: Forcing pipeline stop; restarting preview.")
            self.stop_pipeline()
            GLib.idle_add(self.on_preview_clicked, None)
        return False

    def stop_pipeline(self):
        if self.pipeline:
            logger.debug("CameraTab: Stopping pipeline (NULL state).")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.mode = None
            self.record_button.set_label("⏺")
            for child in self.video_box.get_children():
                self.video_box.remove(child)

    def on_preview_clicked(self, widget):
        logger.debug("CameraTab: Starting PREVIEW pipeline...")
        self.stop_pipeline()
        self.pipeline = self.build_preview_pipeline()
        self.pipeline.set_state(Gst.State.PLAYING)
        self.mode = "preview"
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)
        if self.embed_video:
            GLib.idle_add(self.embed_video_widget)
        logger.info("CameraTab: Preview started.")

    def on_record_clicked(self, widget):
        if self.mode != "record":
            logger.debug("CameraTab: Starting RECORD pipeline...")
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
            logger.info("CameraTab: Recording started.")
        else:
            logger.debug("CameraTab: Stopping RECORD => sending EOS, waiting 2s fallback.")
            eos_event = Gst.Event.new_eos()
            result = self.pipeline.send_event(eos_event)
            if result:
                logger.info("CameraTab: EOS event sent successfully.")
            else:
                logger.error("CameraTab: Failed to send EOS event.")
            GLib.timeout_add(2000, self.fallback_stop)

    def on_photo_clicked(self, widget):
        if not self.pipeline:
            logger.warning("CameraTab: No active pipeline => cannot capture photo.")
            return
        appsink = self.pipeline.get_by_name("photo_sink")
        if not appsink:
            logger.error("CameraTab: No 'photo_sink' in pipeline => cannot capture photo.")
            return
        logger.debug("CameraTab: Attempting to pull a photo sample...")
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
                logger.info(f"CameraTab: Photo saved to {photo_filename}")
            else:
                logger.error("CameraTab: Failed mapping buffer for reading.")
        else:
            logger.error("CameraTab: No sample pulled for photo; possibly no new frames available.")

### PHOTOS TAB ###
class PhotosTab(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        # Left: a scrolled window with a list of image files.
        self.file_list_store = Gtk.ListStore(str)
        self.treeview = Gtk.TreeView(model=self.file_list_store)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Photos", renderer, text=0)
        self.treeview.append_column(column)
        self.treeview.get_selection().connect("changed", self.on_selection_changed)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.treeview)
        scrolled.set_min_content_width(200)
        self.pack_start(scrolled, False, False, 0)
        
        # Right: an image widget for preview.
        self.image = Gtk.Image()
        self.image.set_hexpand(True)
        self.image.set_vexpand(True)
        # Wrap in an EventBox to catch size allocation.
        self.event_box = Gtk.EventBox()
        self.event_box.add(self.image)
        self.event_box.connect("size-allocate", self.on_image_allocate)
        self.pack_start(self.event_box, True, True, 0)
        
        # Refresh file list when the tab is mapped.
        self.connect("map", lambda w: self.populate_file_list())
        
    def populate_file_list(self):
        pictures_dir = os.path.expanduser("~/Pictures")
        self.file_list_store.clear()
        if os.path.exists(pictures_dir):
            files = sorted(os.listdir(pictures_dir))
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    self.file_list_store.append([f])
                    
    def on_selection_changed(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            filename = model[treeiter][0]
            filepath = os.path.join(os.path.expanduser("~/Pictures"), filename)
            logger.info(f"PhotosTab: Selected {filepath}")
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(filepath)
                alloc = self.event_box.get_allocation()
                scaled = pixbuf.scale_simple(alloc.width, alloc.height, GdkPixbuf.InterpType.BILINEAR)
                self.image.set_from_pixbuf(scaled)
            except Exception as e:
                logger.error(f"PhotosTab: Error scaling image: {e}")
                    
    def on_image_allocate(self, widget, allocation):
        # When the container is resized, re-load the selected image if any.
        selection = self.treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter:
            filename = model[treeiter][0]
            filepath = os.path.join(os.path.expanduser("~/Pictures"), filename)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(filepath)
                scaled = pixbuf.scale_simple(allocation.width, allocation.height, GdkPixbuf.InterpType.BILINEAR)
                self.image.set_from_pixbuf(scaled)
            except Exception as e:
                logger.error(f"PhotosTab: Error scaling image: {e}")

### VIDEOS TAB ###
class VideosTab(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        # Left: list of video files.
        self.file_list_store = Gtk.ListStore(str)
        self.treeview = Gtk.TreeView(model=self.file_list_store)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Videos", renderer, text=0)
        self.treeview.append_column(column)
        self.treeview.get_selection().connect("changed", self.on_selection_changed)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.treeview)
        scrolled.set_min_content_width(200)
        self.pack_start(scrolled, False, False, 0)
        
        # Right: video area with basic controls.
        self.video_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.video_area.set_hexpand(True)
        self.video_area.set_vexpand(True)
        self.pack_start(self.video_area, True, True, 0)
        # Instead of a DrawingArea, use a Box container for video widget.
        self.video_container = Gtk.Box()
        self.video_container.set_hexpand(True)
        self.video_container.set_vexpand(True)
        self.video_area.pack_start(self.video_container, True, True, 0)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.play_button = Gtk.Button(label="▶")
        self.play_button.connect("clicked", self.on_play_pause)
        self.scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.scale.set_range(0, 100)
        self.scale.set_draw_value(False)
        controls.pack_start(self.play_button, False, False, 0)
        controls.pack_start(self.scale, True, True, 0)
        self.video_area.pack_start(controls, False, False, 0)
        
        # GStreamer playbin for video playback.
        self.playbin = Gst.ElementFactory.make("playbin", "playbin")
        video_sink = Gst.ElementFactory.make("gtksink", "gtksink_video")
        if video_sink:
            self.playbin.set_property("video-sink", video_sink)
            GLib.idle_add(self.embed_video)
        self.is_playing = False
        self.duration = Gst.CLOCK_TIME_NONE
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self.on_bus_message)
        GLib.timeout_add(500, self.update_progress)
        
        # Refresh list when tab is mapped.
        self.connect("map", lambda w: self.populate_file_list())
        
    def populate_file_list(self):
        videos_dir = os.path.expanduser("~/Videos")
        self.file_list_store.clear()
        if os.path.exists(videos_dir):
            files = sorted(os.listdir(videos_dir))
            for f in files:
                if f.lower().endswith(('.mp4', '.mkv', '.avi')):
                    self.file_list_store.append([f])
                    
    def on_selection_changed(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            filename = model[treeiter][0]
            filepath = os.path.join(os.path.expanduser("~/Videos"), filename)
            logger.info(f"VideosTab: Selected {filepath}")
            self.playbin.set_state(Gst.State.NULL)
            self.playbin.set_property("uri", "file://" + filepath)
            self.playbin.set_state(Gst.State.PLAYING)
            self.is_playing = True
            self.play_button.set_label("⏸")
            
    def embed_video(self):
        video_sink = self.playbin.get_property("video-sink")
        if video_sink:
            widget = video_sink.props.widget
            if widget:
                # Remove existing widget from container.
                for child in self.video_container.get_children():
                    self.video_container.remove(child)
                self.video_container.add(widget)
                widget.show_all()
        return False

    def on_play_pause(self, button):
        if self.is_playing:
            self.playbin.set_state(Gst.State.PAUSED)
            self.is_playing = False
            button.set_label("▶")
        else:
            self.playbin.set_state(Gst.State.PLAYING)
            self.is_playing = True
            button.set_label("⏸")
            
    def on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            logger.info("VideosTab: EOS received, stopping playback.")
            self.playbin.set_state(Gst.State.NULL)
            self.is_playing = False
            self.play_button.set_label("▶")
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"VideosTab: Bus ERROR: {err} - {debug}")
            self.playbin.set_state(Gst.State.NULL)
            self.is_playing = False
            self.play_button.set_label("▶")
        elif t == Gst.MessageType.DURATION:
            self.duration = self.playbin.query_duration(Gst.Format.TIME)[1]
            
    def update_progress(self):
        if self.is_playing and self.duration != Gst.CLOCK_TIME_NONE:
            ret, pos = self.playbin.query_position(Gst.Format.TIME)
            if ret:
                fraction = pos / self.duration
                self.scale.set_value(fraction * 100)
        return True

    def stop_playback(self):
        self.playbin.set_state(Gst.State.NULL)
        self.is_playing = False
        self.play_button.set_label("▶")

    def on_hide(self):
        self.stop_playback()

### MAIN WINDOW WITH NOTEBOOK ###
class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Media Controller")
        self.set_default_size(800, 480)
        self.connect("delete-event", Gtk.main_quit)
        notebook = Gtk.Notebook()
        self.add(notebook)
        self.camera_tab = CameraTab()
        notebook.append_page(self.camera_tab, Gtk.Label(label="Camera"))
        self.photos_tab = PhotosTab()
        notebook.append_page(self.photos_tab, Gtk.Label(label="Photos"))
        self.videos_tab = VideosTab()
        notebook.append_page(self.videos_tab, Gtk.Label(label="Videos"))
        notebook.connect("switch-page", self.on_switch_page)
        
    def on_switch_page(self, notebook, page, page_num):
        # Refresh lists when switching to Photos or Videos tab.
        label = notebook.get_tab_label_text(page)
        if label == "Photos" and hasattr(self.photos_tab, "populate_file_list"):
            self.photos_tab.populate_file_list()
        if label == "Videos" and hasattr(self.videos_tab, "populate_file_list"):
            self.videos_tab.populate_file_list()
        # When leaving Videos tab, stop playback.
        if label != "Videos" and hasattr(self, "videos_tab"):
            self.videos_tab.stop_playback()

def main():
    os.makedirs(os.path.expanduser("~/Pictures"), exist_ok=True)
    os.makedirs(os.path.expanduser("~/Videos"), exist_ok=True)
    win = MainWindow()
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
