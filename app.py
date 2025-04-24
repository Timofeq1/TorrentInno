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
        
    def on_touch_down(self, touch):
        """Handle touch down event"""
        if self.collide_point(*touch.pos):
            # Start a clock to detect long press
            touch.ud['long_press'] = Clock.schedule_once(lambda dt: self.on_long_press(touch), 0.5)  # 500ms for long press
        return super(TorrentFileItem, self).on_touch_down(touch)
    
    def on_touch_up(self, touch):
        """Handle touch up event"""
        if 'long_press' in touch.ud:
            # Cancel the long press clock if touch is released
            Clock.unschedule(touch.ud['long_press'])
        return super(TorrentFileItem, self).on_touch_up(touch)
    
    def on_long_press(self, touch):
        """Handle long press event"""
        if self.collide_point(*touch.pos):
            # Show options menu
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
        pass  # this would open a file picker or URL input dialog

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