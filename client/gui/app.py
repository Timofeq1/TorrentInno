from kivymd.app import MDApp
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ListProperty, StringProperty, NumericProperty
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
import torrent_manager
from os.path import expanduser

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
        blocks_data = kwargs.pop('blocks', [0] * 1)
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
        """Delete this item and remove the physical file if it exists"""
        # Close the dialog
        self.dialog.dismiss()
        
        # Get the app instance and main screen
        app = MDApp.get_running_app()
        main_screen = app.root.get_screen('main')
        
        # Get the file name from the current item
        file_name = self.file_name
        
        # Try to delete the physical file if it exists
        try:
            # Assume the file is in the Downloads folder
            from os.path import expanduser, join
            import os
            
            # Get the default download path
            download_path = expanduser("~/Downloads")
            file_path = join(download_path, file_name)
            
            # Check if file exists and delete it
            if os.path.exists(file_path):
                os.remove(file_path)
                from kivymd.toast import toast
                toast(f"Файл {file_name} успешно удален")
        except PermissionError:
            # Handle permission error
            from kivymd.toast import toast
            toast(f"Недостаточно прав для удаления файла {file_name}")
        except Exception as e:
            # Handle other errors
            from kivymd.toast import toast
            toast(f"Ошибка при удалении файла: {str(e)}")
        
        # Call the remove_torrent method of MainScreen to update the UI and torrent_state.json
        main_screen.remove_torrent(self.index)

class MainScreen(Screen):
    """Main screen of the application showing the list of torrent files"""
    files = ListProperty([])
    
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        # Инициализируем менеджер торрентов
        torrent_manager.initialize()
        # Получаем список файлов из менеджера торрентов
        self.files = torrent_manager.get_files()
        # Start the clock to update download progress every second
        Clock.schedule_interval(self.update_progress, 1)
    
    def on_kv_post(self, base_widget):
        """Called after the kv file is loaded"""
        self.update_file_list()
    
    def update_progress(self, dt):
        """Update the download progress of files"""
        self.files = torrent_manager.update_files()
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
        """Handle back button press - exit the application"""
        # Получаем экземпляр приложения и завершаем его работу
        app = MDApp.get_running_app()
        app.stop()
    
    def show_info(self):
        """Show app information - open GitHub repository"""
        import webbrowser
        webbrowser.open('https://github.com/Timofeq1/TorrentInno')
    
    def show_menu(self):
        """Show app menu"""
        pass  # this would show a menu
    
    def add_torrent(self):
        """Add a new torrent"""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivy.metrics import dp
        
        # Create a custom content for the dialog
        self.dialog_content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            adaptive_height=True
        )
        
        # Add a label with instructions
        self.dialog_content.add_widget(MDLabel(
            text="Выберите действие:",
            size_hint_y=None,
            height=dp(48)
        ))
        
        # Create the dialog
        self.add_dialog = MDDialog(
            title="Добавить торрент",
            type="custom",
            content_cls=self.dialog_content,
            buttons=[
                MDFlatButton(
                    text="ВЫГРУЗИТЬ",
                    on_release=self.open_upload_file_manager
                ),
                MDFlatButton(
                    text="ЗАГРУЗИТЬ",
                    on_release=self.open_download_dialog
                ),
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x: self.add_dialog.dismiss()
                ),
            ],
        )
        
        # Show the dialog
        self.add_dialog.open()
    
    def open_upload_file_manager(self, *args):
        """Open file manager to select a file to share"""
        from kivymd.uix.filemanager import MDFileManager
        
        # Initialize file manager
        self.file_manager = MDFileManager(
            exit_manager=self.exit_file_manager,
            select_path=self.select_file_to_share,
            preview=True,
        )
        
        # Set the starting path to user's home directory
        home_dir = expanduser("~")
        self.add_dialog.dismiss()
        self.file_manager.show(home_dir)
    
    def open_download_dialog(self, *args):
        """Open dialog to download a torrent"""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.filemanager import MDFileManager
        
        # Dismiss the previous dialog
        self.add_dialog.dismiss()
        
        # Create a custom content for the dialog
        self.download_content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            adaptive_height=True
        )
        
        # Add a text field for JSON input
        self.json_field = MDTextField(
            hint_text="Вставьте JSON метаданные",
            multiline=True,
            size_hint_y=None,
            height=dp(100)
        )
        self.download_content.add_widget(self.json_field)
        
        # Create the dialog
        self.download_dialog = MDDialog(
            title="Загрузить торрент",
            type="custom",
            content_cls=self.download_content,
            buttons=[
                MDFlatButton(
                    text="ВЫБРАТЬ JSON ФАЙЛ",
                    on_release=self.open_json_file_manager
                ),
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x: self.download_dialog.dismiss()
                ),
                MDFlatButton(
                    text="ЗАГРУЗИТЬ",
                    on_release=self.process_json_input
                ),
            ],
        )
        
        # Initialize file manager for JSON selection
        self.json_file_manager = MDFileManager(
            exit_manager=self.exit_json_file_manager,
            select_path=self.select_json_file,
            preview=True,
        )
        
        # Show the dialog
        self.download_dialog.open()
    
    def exit_file_manager(self, *args):
        """Close the file manager"""
        self.file_manager.close()
    
    def exit_json_file_manager(self, *args):
        """Close the JSON file manager"""
        self.json_file_manager.close()
    
    def select_file_to_share(self, path):
        """Handle file selection for sharing"""
        self.file_manager.close()
        
        # Save the selected file path
        self.selected_file_path = path
        
        # Show dialog to enter comment and name
        self.show_resource_creation_dialog(path)
    
    def show_resource_creation_dialog(self, file_path):
        """Show dialog to enter comment and name for resource creation"""
        import os
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        
        # Get the file name
        file_name = os.path.basename(file_path)
        
        # Create content for the dialog
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(200)
        )
        
        # Add fields for comment and name
        content.add_widget(MDLabel(
            text="Введите комментарий к файлу:",
            size_hint_y=None,
            height=dp(30)
        ))
        
        self.comment_field = MDTextField(
            hint_text="Комментарий",
            text="",
            size_hint_y=None,
            height=dp(48)
        )
        content.add_widget(self.comment_field)
        
        content.add_widget(MDLabel(
            text="Введите имя файла (оставьте пустым для использования исходного имени):",
            size_hint_y=None,
            height=dp(30)
        ))
        
        self.name_field = MDTextField(
            hint_text="Имя файла",
            text=file_name,
            size_hint_y=None,
            height=dp(48)
        )
        content.add_widget(self.name_field)
        
        # Create the dialog
        self.resource_dialog = MDDialog(
            title="Создание ресурса",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x: self.resource_dialog.dismiss()
                ),
                MDFlatButton(
                    text="СОЗДАТЬ",
                    on_release=self.create_and_share_resource
                ),
            ],
        )
        
        self.resource_dialog.open()
    
    def open_json_file_manager(self, *args):
        """Open file manager to select a JSON file"""
        home_dir = expanduser("~")
        # Установка фильтров для отображения JSON файлов
        self.json_file_manager.ext = [".json"]
        self.json_file_manager.show(home_dir)
    
    def select_json_file(self, path):
        """Handle JSON file selection"""
        self.json_file_manager.close()
        
        # Check if the file is a JSON file
        if path.endswith('.json'):
            try:
                import json
                with open(path, 'r') as f:
                    json_data = json.load(f)
                    self.json_field.text = json.dumps(json_data, indent=2)
            except Exception as e:
                from kivymd.toast import toast
                toast(f"Ошибка при чтении JSON файла: {str(e)}")
        else:
            from kivymd.toast import toast
            toast("Выбранный файл не является JSON файлом")
    
    def process_json_input(self, *args):
        """Process the JSON input and start download"""
        import json
        from kivymd.toast import toast
        
        json_text = self.json_field.text.strip()
        if not json_text:
            toast("Введите JSON метаданные или выберите файл")
            return
        
        try:
            # Parse the JSON
            resource_json = json.loads(json_text)
            
            # Show dialog to select save path
            self.show_save_path_dialog(resource_json)
        except json.JSONDecodeError:
            toast("Некорректный формат JSON")
    
    def show_save_path_dialog(self, resource_json):
        """Show dialog to select save path"""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        
        # Dismiss the previous dialog
        self.download_dialog.dismiss()
        
        # Create content for the dialog
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(100)
        )
        
        # Add a label for save path
        content.add_widget(MDLabel(
            text="Путь для сохранения файла:",
            size_hint_y=None,
            height=dp(30)
        ))
        
        self.save_path_field = MDTextField(
            text=expanduser("~/Downloads/") + resource_json.get("name", "downloaded_file"),
            size_hint_y=None,
            height=dp(48)
        )
        content.add_widget(self.save_path_field)
        
        # Create the dialog
        self.save_path_dialog = MDDialog(
            title="Выберите путь сохранения",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="ОТМЕНА",
                    on_release=lambda x: self.save_path_dialog.dismiss()
                ),
                MDFlatButton(
                    text="ЗАГРУЗИТЬ",
                    on_release=lambda x: self.start_download_with_resource(resource_json)
                ),
            ],
        )
        
        self.save_path_dialog.open()
    
    def create_and_share_resource(self, *args):
        """Create resource from file and start sharing"""
        import os
        import json
        from kivymd.toast import toast
        
        # Get the values from fields
        comment = self.comment_field.text
        name = self.name_field.text if self.name_field.text else None
        file_path = self.selected_file_path
        
        try:
            # Create resource JSON
            resource_json = torrent_manager.create_resource_from_file(file_path, comment, name)
            
            # Start sharing the file
            file_info = torrent_manager.start_sharing_file(file_path, resource_json)
            
            # Close the dialog
            self.resource_dialog.dismiss()
            
            # Show dialog to save or copy the resource JSON
            self.show_resource_save_dialog(resource_json, file_path)
            
            # Update the file list
            self.files = torrent_manager.get_files()
            self.update_file_list()
        except Exception as e:
            toast(f"Ошибка при создании ресурса: {str(e)}")
            self.resource_dialog.dismiss()
    
    def show_resource_save_dialog(self, resource_json, file_path):
        """Show dialog to save or copy the resource JSON"""
        import os
        import json
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        from kivymd.uix.textfield import MDTextField
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.label import MDLabel
        from kivy.uix.scrollview import ScrollView
        
        # Create content for the dialog
        content = MDBoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None,
            height=dp(300)
        )
        
        # Add a label with instructions
        content.add_widget(MDLabel(
            text="Ресурс успешно создан. Вы можете скопировать JSON или сохранить его в файл:",
            size_hint_y=None,
            height=dp(40)
        ))
        
        # Add a text field with the JSON
        json_text = json.dumps(resource_json, indent=2)
        json_field = MDTextField(
            text=json_text,
            multiline=True,
            readonly=True,
            size_hint_y=None,
            height=dp(200)
        )
        
        # Add the text field to a scroll view
        scroll = ScrollView()
        scroll.add_widget(json_field)
        content.add_widget(scroll)
        
        # Generate default save path
        file_name = os.path.basename(file_path)
        default_save_path = os.path.splitext(file_path)[0] + "_meta.json"
        
        # Add a text field for save path
        self.json_save_path = MDTextField(
            hint_text="Путь для сохранения JSON",
            text=default_save_path,
            size_hint_y=None,
            height=dp(48)
        )
        content.add_widget(self.json_save_path)
        
        # Create the dialog
        self.resource_save_dialog = MDDialog(
            title="Сохранение ресурса",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="КОПИРОВАТЬ",
                    on_release=lambda x: self.copy_to_clipboard(json_text)
                ),
                MDFlatButton(
                    text="СОХРАНИТЬ",
                    on_release=lambda x: self.save_resource_json(resource_json)
                ),
                MDFlatButton(
                    text="ЗАКРЫТЬ",
                    on_release=lambda x: self.resource_save_dialog.dismiss()
                ),
            ],
        )
        
        self.resource_save_dialog.open()
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        from kivy.core.clipboard import Clipboard
        from kivymd.toast import toast
        
        Clipboard.copy(text)
        toast("JSON скопирован в буфер обмена")
    
    def save_resource_json(self, resource_json):
        """Save resource JSON to file"""
        import json
        from kivymd.toast import toast
        
        save_path = self.json_save_path.text
        try:
            with open(save_path, 'w') as f:
                json.dump(resource_json, f, indent=4)
            toast(f"JSON сохранен в {save_path}")
            self.resource_save_dialog.dismiss()
        except Exception as e:
            toast(f"Ошибка при сохранении JSON: {str(e)}")
    
    def start_download_with_resource(self, resource_json):
        """Start downloading file with resource JSON"""
        from kivymd.toast import toast
        
        # Get the save path
        save_path = self.save_path_field.text
        
        try:
            # Start downloading the file
            file_info = torrent_manager.start_download_file(save_path, resource_json)
            
            # Close the dialog
            self.save_path_dialog.dismiss()
            
            # Update the file list
            self.files = torrent_manager.get_files()
            self.update_file_list()
            
            toast(f"Начата загрузка файла {resource_json.get('name', 'unknown')}")
        except Exception as e:
            toast(f"Ошибка при загрузке файла: {str(e)}")
            self.save_path_dialog.dismiss()

    def remove_torrent(self, index=None):
        """Remove a torrent and save changes to torrent_state.json"""
        if index is not None and 0 <= index < len(self.files):
            # Получаем имя файла для удаления
            file_name = self.files[index]['name']
            # Удаляем торрент через менеджер
            torrent_manager.remove_torrent(file_name)
            # Обновляем локальный список файлов
            self.files = torrent_manager.get_files()
            # Обновляем отображение
            self.update_file_list()
            # Сохраняем изменения в torrent_state.json
            torrent_manager.shutdown()

class TorrentInnoApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "BlueGray"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Light"
        
        return super().build()
    
    def on_stop(self):
        """Вызывается при закрытии приложения"""
        # Сохраняем состояние торрентов
        torrent_manager.shutdown()

        """ [DEPRECATED] 
        This part of code cause doublicationg of blocks
        as in https://stackoverflow.com/questions/62752997/all-elements-rendering-twice-in-kivy-kivymd
        """ 
        # root = Builder.load_file('torrentinno.kv')
        # return root

        # screen manager and add it to the root widget

if __name__ == '__main__':
    TorrentInnoApp().run()