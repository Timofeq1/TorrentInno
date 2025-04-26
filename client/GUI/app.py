from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ListProperty, StringProperty, NumericProperty
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
import random

# Mock data for torrent files
MOCK_FILES = [
    {
        'name': 'example.txt',
        'size': '1.23 kb',
        'type': 'txt',
        'download_speed': '1kb/s',
        'upload_speed': '0kb/s',
        'blocks': [0] * 20  # 0 means not downloaded, 1 means downloaded
    },
    {
        'name': 'music.mp3',
        'size': '2.03 mb',
        'type': 'mp3',
        'download_speed': '2mb/s',
        'upload_speed': '1mb/s',
        'blocks': [0] * 20
    },
    {
        'name': 'video.mp4',
        'size': '12.7 mb',
        'type': 'mp4',
        'download_speed': '1mb/s',
        'upload_speed': '1mb/s',
        'blocks': [0] * 20
    },
    {
        'name': 'unknown',
        'size': '1.097 Gb',
        'type': 'unknown',
        'download_speed': '3mb/s',
        'upload_speed': '2 mb/s',
        'blocks': [0] * 20
    }
]

# Mock function to update download progress
def update_download_progress(files):
    """Simulate download progress by randomly updating blocks"""
    for file in files:
        # Randomly select a block to mark as downloaded
        if 0 in file['blocks']:  # If there are still blocks to download
            zero_indices = [i for i, x in enumerate(file['blocks']) if x == 0]
            if zero_indices:  # If there are blocks that are not downloaded yet
                # Randomly select 1-3 blocks to mark as downloaded
                num_blocks = min(random.randint(1, 3), len(zero_indices))
                for _ in range(num_blocks):
                    if zero_indices:  # Check again in case we've used all indices
                        idx = random.choice(zero_indices)
                        file['blocks'][idx] = 1
                        zero_indices.remove(idx)
        
        # Update download and upload speeds randomly
        download_value = float(file['download_speed'].split('mb/s')[0].split('kb/s')[0].strip())
        upload_value = float(file['upload_speed'].split('mb/s')[0].split('kb/s')[0].strip())
        
        # Randomly adjust speeds
        download_value += random.uniform(-0.5, 0.5)
        upload_value += random.uniform(-0.3, 0.3)
        
        # Ensure speeds don't go below 0.1
        download_value = max(0.1, download_value)
        upload_value = max(0.1, upload_value)
        
        # Update the speed values
        if 'kb/s' in file['download_speed']:
            file['download_speed'] = f"{download_value:.1f}kb/s"
        else:
            file['download_speed'] = f"{download_value:.1f}mb/s"
            
        if 'kb/s' in file['upload_speed']:
            file['upload_speed'] = f"{upload_value:.1f}kb/s"
        else:
            file['upload_speed'] = f"{upload_value:.1f}mb/s"
    
    return files

class TorrentFileItem(MDBoxLayout):
    """Class representing a single torrent file in the list"""
    file_name = StringProperty('')
    file_size = StringProperty('')
    file_type = StringProperty('')
    download_speed = StringProperty('')
    upload_speed = StringProperty('')
    blocks = ListProperty([])
    index = NumericProperty(-1)  # Store the index of this item in the files list
    
    def __init__(self, **kwargs):
        # Initialize blocks properly to avoid shared list issue
        blocks_data = kwargs.pop('blocks', [0] * 20)
        self.index = kwargs.pop('index', -1)  # Get the index from kwargs
        super(TorrentFileItem, self).__init__(**kwargs)
        self.blocks = blocks_data
        # Variables for double click detection
        self.last_click_time = 0
        self.double_click_timeout = 0.3  # 300ms for double click detection
        
    def on_touch_down(self, touch):
        """Handle touch down event"""
        if self.collide_point(*touch.pos):
            # Start a clock to detect long press
            touch.ud['long_press'] = Clock.schedule_once(lambda dt: self.on_long_press(touch), 0.5)  # 500ms for long press
            
            # Double click detection
            current_time = Clock.get_time()
            if current_time - self.last_click_time < self.double_click_timeout:
                # This is a double click
                self.on_double_click()
                # Cancel the long press detection since we've detected a double click
                if 'long_press' in touch.ud:
                    Clock.unschedule(touch.ud['long_press'])
            self.last_click_time = current_time
            
        return super(TorrentFileItem, self).on_touch_down(touch)
    
    def on_touch_up(self, touch):
        """Handle touch up event"""
        if 'long_press' in touch.ud:
            # Cancel the long press clock if touch is released
            Clock.unschedule(touch.ud['long_press'])
        return super(TorrentFileItem, self).on_touch_up(touch)
        
    def on_double_click(self):
        """Handle double click event"""
        # Show the same options dialog as for long press
        self.show_options_dialog()
    
    def on_long_press(self, touch):
        """Handle long press event"""
        if self.collide_point(*touch.pos):
            self.show_options_dialog()
    
    def show_options_dialog(self):
        """Show options dialog for the torrent file"""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        
        self.dialog = MDDialog(
            title=f"Действия с {self.file_name}",
            text="Выберите действие:",
            buttons=[
                MDFlatButton(
                    text="Удалить",
                    on_release=lambda x: self.delete_item()
                ),
                MDFlatButton(
                    text="Назад",
                    on_release=lambda x: self.dialog.dismiss()
                ),
            ],
        )
        self.dialog.open()
    
    def delete_item(self):
        """Delete this item"""
        # Close the dialog
        self.dialog.dismiss()
        # Call the remove_torrent method of MainScreen
        app = MDApp.get_running_app()
        main_screen = app.root.get_screen('main')
        main_screen.remove_torrent(self.index)

class MainScreen(Screen):
    """Main screen of the application showing the list of torrent files"""
    files = ListProperty([])
    
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        # Create a deep copy of MOCK_FILES to avoid modifying the original
        self.files = []
        for file in MOCK_FILES:
            self.files.append(file.copy())
        # Start the clock to update download progress every second
        Clock.schedule_interval(self.update_progress, 1)
    
    def on_kv_post(self, base_widget):
        """Called after the kv file is loaded"""
        self.update_file_list()
    
    def update_progress(self, dt):
        """Update the download progress of files"""
        self.files = update_download_progress(self.files)
        self.update_file_list()
    
    def update_file_list(self):
        """Update the file list with current data"""
        file_list = self.ids.file_list
        file_list.clear_widgets()
        
        for i, file in enumerate(self.files):
            item = TorrentFileItem(
                file_name=file['name'],
                file_size=file['size'],
                file_type=file['type'],
                download_speed=file['download_speed'],
                upload_speed=file['upload_speed'],
                blocks=file['blocks'].copy(),  # Use a copy to prevent reference issues
                index=i  # Pass the index to the item
            )
            
            # Create progress blocks
            progress_container = item.ids.progress_container
            progress_container.clear_widgets()
            
            # Use item.blocks instead of file['blocks'] to avoid duplication
            for i, block in enumerate(item.blocks):
                block_widget = MDBoxLayout(size_hint_x=1/len(item.blocks))
                if block == 1:  # Downloaded block
                    block_widget.md_bg_color = (0.3, 0.8, 0.3, 1)  # Green
                else:  # Not downloaded block
                    block_widget.md_bg_color = (1, 1, 1, 1)  # White
                
                progress_container.add_widget(block_widget)
            
            file_list.add_widget(item)
    
    def on_back_pressed(self):
        """Handle back button press"""
        pass  # this would navigate back
    
    def show_info(self):
        """Show app information"""
        pass  # this would show an info dialog
    
    def show_menu(self):
        """Show app menu"""
        pass  # this would show a menu
    
    def add_torrent(self):
        """Add a new torrent"""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.filemanager import MDFileManager
        from kivy.core.window import Window
        from os.path import expanduser
        import os
        
        # Create a custom content for the dialog
        self.dialog_content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            adaptive_height=True
        )
        
        # Add a text field for torrent URL
        self.url_field = MDTextField(
            hint_text="Введите торрент-ссылку",
            helper_text="Например: magnet:?xt=urn:btih:...",
            helper_text_mode="on_focus",
            size_hint_y=None,
            height=dp(48)
        )
        self.dialog_content.add_widget(self.url_field)
        
        # Create the dialog
        self.add_dialog = MDDialog(
            title="Добавить торрент",
            type="custom",
            content_cls=self.dialog_content,
            buttons=[
                MDFlatButton(
                    text="ВЫБРАТЬ ФАЙЛ",
                    on_release=self.open_file_manager
                ),
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x: self.add_dialog.dismiss()
                ),
                MDFlatButton(
                    text="ДОБАВИТЬ",
                    on_release=self.process_torrent_url
                ),
            ],
        )
        
        # Initialize file manager
        self.file_manager = MDFileManager(
            exit_manager=self.exit_file_manager,
            select_path=self.select_torrent_file,
            preview=True,
        )
        
        # Show the dialog
        self.add_dialog.open()
    
    def open_file_manager(self, *args):
        """Open file manager to select a torrent file"""
        # Set the starting path to user's home directory
        home_dir = expanduser("~")
        self.file_manager.show(home_dir)
        
    def exit_file_manager(self, *args):
        """Close the file manager"""
        self.file_manager.close()
        
    def select_torrent_file(self, path):
        """Handle torrent file selection"""
        self.file_manager.close()
        # Check if the file is a torrent file
        if path.endswith('.torrent'):
            self.show_torrent_content_dialog(path)
        else:
            from kivymd.toast import toast
            toast("Выбранный файл не является торрент-файлом")
    
    def process_torrent_url(self, *args):
        """Process the torrent URL entered by the user"""
        url = self.url_field.text.strip()
        if url.startswith('magnet:') or url.endswith('.torrent'):
            self.add_dialog.dismiss()
            self.show_torrent_content_dialog(url)
        else:
            from kivymd.toast import toast
            toast("Введите корректную торрент-ссылку")
    
    def show_torrent_content_dialog(self, source):
        """Show dialog with torrent content for selection"""
        # Mock data for torrent content
        mock_content = [
            {"name": "file1.mp4", "size": "1.2 GB", "selected": True},
            {"name": "file2.txt", "size": "15 KB", "selected": True},
            {"name": "file3.mp3", "size": "5.7 MB", "selected": True}
        ]
        
        from kivymd.uix.list import MDList, OneLineAvatarIconListItem, IconLeftWidget, IconRightWidget
        from kivymd.uix.selectioncontrol import MDCheckbox
        
        # Create content for the dialog
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(300)
        )
        
        # Add a label for save path
        save_path_box = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(48)
        )
        
        from kivymd.uix.label import MDLabel
        save_path_label = MDLabel(
            text="Путь сохранения:",
            size_hint_x=0.3
        )
        
        self.save_path_field = MDTextField(
            text=expanduser("~/Downloads"),
            size_hint_x=0.7
        )
        
        save_path_box.add_widget(save_path_label)
        save_path_box.add_widget(self.save_path_field)
        content.add_widget(save_path_box)
        
        # Create a list for files
        file_list = MDList()
        
        # Add files to the list
        for file in mock_content:
            item = OneLineAvatarIconListItem(text=f"{file['name']} ({file['size']})")
            
            # Add file icon based on extension
            file_ext = file['name'].split('.')[-1] if '.' in file['name'] else 'unknown'
            icon_name = "file"
            if file_ext in ['mp3', 'wav', 'ogg']:
                icon_name = "music-note"
            elif file_ext in ['mp4', 'avi', 'mkv']:
                icon_name = "video"
            elif file_ext in ['txt', 'pdf', 'doc', 'docx']:
                icon_name = "file-document"
            
            item.add_widget(IconLeftWidget(icon=icon_name))
            
            # Add checkbox for selection
            check = MDCheckbox(active=file['selected'])
            check.bind(active=lambda checkbox, value, file=file: self.toggle_file_selection(file, value))
            right_icon = IconRightWidget(widget=check)
            item.add_widget(right_icon)
            
            file_list.add_widget(item)
        
        # Add the list to a scroll view
        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView()
        scroll.add_widget(file_list)
        content.add_widget(scroll)
        
        # Create the dialog
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        
        self.content_dialog = MDDialog(
            title="Выберите файлы для загрузки",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x: self.content_dialog.dismiss()
                ),
                MDFlatButton(
                    text="ЗАГРУЗИТЬ",
                    on_release=self.start_download
                ),
            ],
        )
        
        self.content_dialog.open()
    
    def toggle_file_selection(self, file, value):
        """Toggle file selection"""
        file['selected'] = value
    
    def start_download(self, *args):
        """Start downloading selected files"""
        # Here you would start the actual download process
        # For now, we'll just close the dialog and add a mock file to the list
        self.content_dialog.dismiss()
        
        # Add a new mock file to the list
        new_file = {
            'name': 'new_download.mp4',
            'size': '45.8 mb',
            'type': 'mp4',
            'download_speed': '0mb/s',
            'upload_speed': '0mb/s',
            'blocks': [0] * 20
        }
        
        self.files.append(new_file)
        self.update_file_list()

    def remove_torrent(self, index=None):
        """Remove a torrent"""
        if index is not None and 0 <= index < len(self.files):
            # Remove the file at the specified index
            del self.files[index]
            # Update the file list to reflect the changes
            self.update_file_list()

class TorrentInnoApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "BlueGray"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Light"
        
        return super().build()

        """ [DEPRECATED] 
        This part of code cause doublicationg of blocks
        as in https://stackoverflow.com/questions/62752997/all-elements-rendering-twice-in-kivy-kivymd
        """ 
        # root = Builder.load_file('torrentinno.kv')
        # return root

        # screen manager and add it to the root widget

if __name__ == '__main__':
    TorrentInnoApp().run()